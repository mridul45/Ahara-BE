"""
Centralised cache key factory for all Ahara cache entries.

Import and call these functions instead of building key strings inline.
Consistent naming ensures invalidation signals and view reads always
target the same key, eliminating silent stale-data bugs.

All keys use the "ahara:" prefix so they're easy to locate in Redis:
    redis-cli keys 'ahara:*'

The KEY_PREFIX in settings.CACHES adds a second prefix at the backend
layer; these functions only manage the *logical* key portion.
"""


# ── Daily Tip ──────────────────────────────────────────────────────────

def tip_scheduled(date_str: str) -> str:
    """Scheduled tip for a specific ISO date, e.g. '2026-05-09'."""
    return f"ahara:tip:sched:{date_str}"


def tip_random(date_str: str) -> str:
    """Randomly selected tip for a specific ISO date."""
    return f"ahara:tip:rand:{date_str}"


def tip_pool(date_str: str | None = None) -> str:
    """List of active unscheduled tip IDs for the given ISO date.

    Keyed by date so the pool naturally expires at midnight — new tips
    activated by admin appear on the next day without manual invalidation.
    If date_str is omitted the key for *today* is returned.
    """
    if date_str is None:
        from datetime import date
        date_str = date.today().isoformat()
    return f"ahara:tip:pool:{date_str}"


# ── Content ────────────────────────────────────────────────────────────

def category_list() -> str:
    """Active category list (version pinned via settings.CATEGORY_CACHE_KEY)."""
    from django.conf import settings
    return getattr(settings, "CATEGORY_CACHE_KEY", "ahara:cat:list:v1")


def featured_playlists() -> str:
    """Featured playlist blob (version pinned via settings.FEATURED_KEY)."""
    from django.conf import settings
    return getattr(settings, "FEATURED_KEY", "ahara:pl:featured:v1:default")


def featured_lock() -> str:
    """Mutex lock key used during featured-playlist cache regeneration."""
    return "ahara:pl:featured:lock"


# ── Intelligence / Memory ──────────────────────────────────────────────

def memory_long_term(user_id: int) -> str:
    """Cached long-term memory JSON for a single user."""
    return f"ahara:mem:lt:{user_id}"


def memory_snapshot(user_id: int) -> str:
    """Cached user snapshot stored on the Memory model (legacy key kept for compat)."""
    return f"user_memory_{user_id}"


# ── Search ─────────────────────────────────────────────────────────────

def search_result(resource: str, digest: str) -> str:
    """Cached search/filter result set."""
    return f"ahara:search:{resource}:{digest}"
