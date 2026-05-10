"""
Resilient Redis cache backend with automatic fallback.

Tries the configured Redis backend for every operation.
If Redis is unreachable (ConnectionError, TimeoutError, etc.),
it transparently falls back to Django's built-in LocMemCache
and periodically retries Redis using a configurable cooldown.

Usage in settings.py:
    CACHES = {
        "default": {
            "BACKEND": "utilities.cache_backend.FallbackCache",
            "LOCATION": "<redis-url>",
            "OPTIONS": { ... },       # passed to the Redis backend
            "KEY_PREFIX": "ahara",
            "FALLBACK_COOLDOWN": 60,   # seconds before retrying Redis (default 60)
        }
    }
"""

import logging
import threading
import time

from django.core.cache.backends.locmem import LocMemCache

logger = logging.getLogger("utilities.cache_backend")

# ── Lazy-import redis exceptions so the module loads even when
#    redis / django-redis are not installed (unlikely, but safe).
_REDIS_EXC: tuple = ()


def _get_redis_exceptions() -> tuple:
    """Collect all Redis-related exception classes that indicate a down server."""
    global _REDIS_EXC  # noqa: PLW0603
    if _REDIS_EXC:
        return _REDIS_EXC

    exceptions = [ConnectionError, TimeoutError, OSError]

    try:
        import redis as _redis
        exceptions.extend([
            _redis.ConnectionError,
            _redis.TimeoutError,
            _redis.RedisError,
        ])
    except ImportError:
        pass

    try:
        from django_redis.exceptions import ConnectionInterrupted
        exceptions.append(ConnectionInterrupted)
    except ImportError:
        pass

    _REDIS_EXC = tuple(set(exceptions))
    return _REDIS_EXC


class FallbackCache:
    """
    A thin proxy that delegates to ``django_redis.cache.RedisCache``
    but catches connection-level failures and replays the same operation
    against a per-process ``LocMemCache`` fallback.

    This is **not** a Django cache backend subclass — it implements the
    same public interface via ``__getattr__`` delegation so that every
    current and future cache method is automatically supported.
    """

    def __init__(self, location: str, params: dict):
        from django_redis.cache import RedisCache

        self._location = location
        self._params = params

        # Cooldown in seconds before retrying a failed Redis connection.
        self._cooldown: int = int(params.get("FALLBACK_COOLDOWN", 60))

        # Primary: Redis
        self._redis = RedisCache(location, params)

        # Fallback: in-process memory cache (created lazily, shared for life of process)
        self._locmem = LocMemCache(
            name="fallback-locmem",
            params={
                "OPTIONS": {"MAX_ENTRIES": 5000},
            },
        )

        # State
        self._using_fallback = False
        self._last_failure: float = 0.0

        # Hit/miss counters (thread-safe via lock).
        self._lock = threading.Lock()
        self._hits: int = 0
        self._misses: int = 0

    # ──────────────────────────────────────────────
    #  Internal helpers
    # ──────────────────────────────────────────────

    def _should_retry_redis(self) -> bool:
        """Return True if enough time has elapsed since the last failure."""
        if not self._using_fallback:
            return False
        return (time.monotonic() - self._last_failure) >= self._cooldown

    def _mark_redis_down(self, exc: Exception) -> None:
        if not self._using_fallback:
            logger.warning(
                "Redis cache unavailable (%s). Falling back to in-memory cache.",
                exc,
            )
            # Attempt Sentry capture if available.
            try:
                import sentry_sdk
                sentry_sdk.capture_message(
                    f"Redis cache unavailable: {exc}",
                    level="warning",
                )
            except Exception:
                pass
        self._using_fallback = True
        self._last_failure = time.monotonic()

    def _mark_redis_up(self) -> None:
        if self._using_fallback:
            logger.info("Redis cache is back online — switching from fallback.")
        self._using_fallback = False
        self._last_failure = 0.0

    def _try_redis(self, method_name: str, *args, **kwargs):
        """
        Attempt an operation on Redis.  On success, return the result.
        On a connection-level failure, mark Redis as down and return a
        sentinel ``_MISS`` to signal the caller to use LocMem instead.
        """
        try:
            result = getattr(self._redis, method_name)(*args, **kwargs)
            # If we were in fallback mode and this succeeded, Redis is back.
            if self._using_fallback:
                self._mark_redis_up()
            return result
        except _get_redis_exceptions() as exc:
            self._mark_redis_down(exc)
            return _MISS

    # ──────────────────────────────────────────────
    #  Public cache API — explicit for the hot-path
    # ──────────────────────────────────────────────

    def get(self, key, default=None, version=None):
        if self._using_fallback:
            if self._should_retry_redis():
                result = self._try_redis("get", key, default=default, version=version)
                if result is not _MISS:
                    self._record_hit()
                    return result
            value = self._locmem.get(key, default=default, version=version)
        else:
            result = self._try_redis("get", key, default=default, version=version)
            if result is not _MISS:
                self._record_hit()
                return result
            value = self._locmem.get(key, default=default, version=version)

        if value is None or value == default:
            self._record_miss()
        else:
            self._record_hit()
        return value

    def _record_hit(self):
        with self._lock:
            self._hits += 1

    def _record_miss(self):
        with self._lock:
            self._misses += 1

    @property
    def stats(self) -> dict:
        """Return current hit/miss counters for monitoring."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total, 4) if total else 0.0,
                "using_fallback": self._using_fallback,
            }

    def set(self, key, value, timeout=None, version=None):
        # Always write to locmem so fallback reads work.
        self._locmem.set(key, value, timeout=timeout, version=version)

        if self._using_fallback:
            if self._should_retry_redis():
                result = self._try_redis("set", key, value, timeout=timeout, version=version)
                if result is not _MISS:
                    return result
            return  # locmem write is enough
        
        result = self._try_redis("set", key, value, timeout=timeout, version=version)
        if result is not _MISS:
            return result

    def delete(self, key, version=None):
        self._locmem.delete(key, version=version)

        if self._using_fallback:
            if self._should_retry_redis():
                result = self._try_redis("delete", key, version=version)
                if result is not _MISS:
                    return result
            return
        
        result = self._try_redis("delete", key, version=version)
        if result is not _MISS:
            return result

    def clear(self):
        self._locmem.clear()

        if self._using_fallback:
            if self._should_retry_redis():
                result = self._try_redis("clear")
                if result is not _MISS:
                    return result
            return

        result = self._try_redis("clear")
        if result is not _MISS:
            return result

    def get_many(self, keys, version=None):
        if self._using_fallback:
            if self._should_retry_redis():
                result = self._try_redis("get_many", keys, version=version)
                if result is not _MISS:
                    return result
            return self._locmem.get_many(keys, version=version)

        result = self._try_redis("get_many", keys, version=version)
        if result is not _MISS:
            return result
        return self._locmem.get_many(keys, version=version)

    def set_many(self, mapping, timeout=None, version=None):
        self._locmem.set_many(mapping, timeout=timeout, version=version)

        if self._using_fallback:
            if self._should_retry_redis():
                result = self._try_redis("set_many", mapping, timeout=timeout, version=version)
                if result is not _MISS:
                    return result
            return

        result = self._try_redis("set_many", mapping, timeout=timeout, version=version)
        if result is not _MISS:
            return result

    def has_key(self, key, version=None):
        if self._using_fallback:
            if self._should_retry_redis():
                result = self._try_redis("has_key", key, version=version)
                if result is not _MISS:
                    return result
            return self._locmem.has_key(key, version=version)

        result = self._try_redis("has_key", key, version=version)
        if result is not _MISS:
            return result
        return self._locmem.has_key(key, version=version)

    def incr(self, key, delta=1, version=None):
        if self._using_fallback:
            if self._should_retry_redis():
                result = self._try_redis("incr", key, delta=delta, version=version)
                if result is not _MISS:
                    return result
            return self._locmem.incr(key, delta=delta, version=version)

        result = self._try_redis("incr", key, delta=delta, version=version)
        if result is not _MISS:
            return result
        return self._locmem.incr(key, delta=delta, version=version)

    def decr(self, key, delta=1, version=None):
        if self._using_fallback:
            if self._should_retry_redis():
                result = self._try_redis("decr", key, delta=delta, version=version)
                if result is not _MISS:
                    return result
            return self._locmem.decr(key, delta=delta, version=version)

        result = self._try_redis("decr", key, delta=delta, version=version)
        if result is not _MISS:
            return result
        return self._locmem.decr(key, delta=delta, version=version)

    def close(self, **kwargs):
        try:
            self._redis.close(**kwargs)
        except Exception:
            pass
        self._locmem.close(**kwargs)

    # ──────────────────────────────────────────────
    #  Catch-all for any cache method not listed above
    # ──────────────────────────────────────────────

    def __getattr__(self, name: str):
        """
        Proxy every other attribute/method to the active backend.
        This ensures forward-compatibility: if Django adds new cache
        methods, they'll work without touching this class.
        """
        if name.startswith("_"):
            raise AttributeError(name)

        def _proxy(*args, **kwargs):
            if self._using_fallback:
                if self._should_retry_redis():
                    result = self._try_redis(name, *args, **kwargs)
                    if result is not _MISS:
                        return result
                return getattr(self._locmem, name)(*args, **kwargs)

            result = self._try_redis(name, *args, **kwargs)
            if result is not _MISS:
                return result
            return getattr(self._locmem, name)(*args, **kwargs)

        return _proxy

    def __contains__(self, key):
        return self.has_key(key)


# Sentinel object — NOT the same as None (which is a valid cache value).
class _MissSentinel:
    __slots__ = ()
    def __repr__(self):
        return "<MISS>"
    def __bool__(self):
        return False

_MISS = _MissSentinel()
