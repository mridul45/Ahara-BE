"""
Tier 1 — Working Memory Buffer.

A sliding-window of recent conversation turns stored in Redis (via Django's
cache framework).  The buffer is ephemeral and session-scoped — if the user
goes idle for ``WORKING_MEMORY_TTL`` seconds the buffer expires automatically.

All public methods are **fail-safe**: if Redis is down the operation degrades
to in-process memory via the existing ``FallbackCache`` backend.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from django.core.cache import cache

from .config import mem_cfg

logger = logging.getLogger("memory.working")


# ── Redis key helpers ────────────────────────────────────────────────

def _buffer_key(user_id: int) -> str:
    return f"wm:buf:{user_id}"


def _session_key(user_id: int) -> str:
    return f"wm:sess:{user_id}"


def _pending_key(user_id: int) -> str:
    """Messages awaiting distillation after a previous failure."""
    return f"wm:pending:{user_id}"


def _activity_key(user_id: int) -> str:
    """Timestamp of the user's last chat interaction."""
    return f"wm:activity:{user_id}"


# Key for the set of user IDs with active working memory buffers.
_ACTIVE_USERS_KEY = "wm:active_users"


# ── Public API ───────────────────────────────────────────────────────

class WorkingMemoryBuffer:
    """
    Manages the Tier-1 sliding window of recent conversation turns.

    Each *turn* is a dict ``{"user": str, "model": str}``.
    """

    # ------------------------------------------------------------------ read
    @staticmethod
    def load(user_id: int) -> list[dict[str, str]]:
        """Return the current buffer (list of turn dicts), or ``[]``."""
        raw = cache.get(_buffer_key(user_id))
        if raw is None:
            return []
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return []
        return raw  # already a list (JSON serializer)

    # -------------------------------------------------------------- session
    @staticmethod
    def get_session_id(user_id: int) -> str:
        """Return (or create) the current session UUID."""
        key = _session_key(user_id)
        session_id = cache.get(key)
        if session_id is None:
            session_id = uuid.uuid4().hex[:12]
            cache.set(key, session_id, timeout=mem_cfg("WORKING_MEMORY_TTL"))
        return session_id

    # ----------------------------------------------------------------- write
    @staticmethod
    def append(user_id: int, user_msg: str, model_msg: str) -> int:
        """
        Append a user/model turn and return the new buffer length.

        Also refreshes the TTL so the buffer stays alive while the user
        is active.
        """
        ttl = mem_cfg("WORKING_MEMORY_TTL")
        buf = WorkingMemoryBuffer.load(user_id)
        buf.append({"user": user_msg, "model": model_msg})
        cache.set(_buffer_key(user_id), buf, timeout=ttl)

        # Keep session alive too
        cache.set(
            _session_key(user_id),
            WorkingMemoryBuffer.get_session_id(user_id),
            timeout=ttl,
        )

        # Track this user as having an active buffer + update activity ts
        WorkingMemoryBuffer._register_active(user_id)
        WorkingMemoryBuffer._touch_activity(user_id, ttl)

        if mem_cfg("ENABLE_MEMORY_LOGGING"):
            max_pairs = mem_cfg("WORKING_BUFFER_MAX_PAIRS")
            logger.info(
                "memory.working user=%s action=append buffer_size=%d/%d",
                user_id,
                len(buf),
                max_pairs,
            )
        return len(buf)

    # --------------------------------------------------------------- eviction
    @staticmethod
    def needs_eviction(user_id: int) -> bool:
        return len(WorkingMemoryBuffer.load(user_id)) > mem_cfg("WORKING_BUFFER_MAX_PAIRS")

    @staticmethod
    def evict(user_id: int) -> list[dict[str, str]]:
        """
        Pop the oldest ``WORKING_BUFFER_EVICT_COUNT`` turns from the buffer
        and return them (for distillation).

        The remaining turns stay in the buffer.
        """
        buf = WorkingMemoryBuffer.load(user_id)
        evict_count = mem_cfg("WORKING_BUFFER_EVICT_COUNT")

        if len(buf) <= evict_count:
            # Edge case: buffer is smaller than evict count — evict all
            evicted = buf[:]
            buf = []
        else:
            evicted = buf[:evict_count]
            buf = buf[evict_count:]

        ttl = mem_cfg("WORKING_MEMORY_TTL")
        cache.set(_buffer_key(user_id), buf, timeout=ttl)

        if mem_cfg("ENABLE_MEMORY_LOGGING"):
            logger.info(
                "memory.working user=%s action=evict evicted=%d remaining=%d trigger=buffer_full",
                user_id,
                len(evicted),
                len(buf),
            )
        return evicted

    # ----------------------------------------------------------------- flush
    @staticmethod
    def flush(user_id: int) -> list[dict[str, str]]:
        """
        Return *all* messages and clear the buffer.

        Used at session-end to distill everything remaining.
        """
        buf = WorkingMemoryBuffer.load(user_id)
        cache.delete(_buffer_key(user_id))
        cache.delete(_session_key(user_id))
        cache.delete(_activity_key(user_id))

        # Remove from active-users set
        WorkingMemoryBuffer._unregister_active(user_id)

        if mem_cfg("ENABLE_MEMORY_LOGGING") and buf:
            logger.info(
                "memory.working user=%s action=flush messages=%d trigger=session_end",
                user_id,
                len(buf),
            )
        return buf

    # -------------------------------------------------------------- pending
    @staticmethod
    def store_pending(user_id: int, messages: list[dict[str, str]]) -> None:
        """
        Park messages that failed distillation so they can be retried later.
        """
        existing = cache.get(_pending_key(user_id)) or []
        existing.extend(messages)
        cache.set(
            _pending_key(user_id),
            existing,
            timeout=mem_cfg("WORKING_MEMORY_TTL") * 3,  # longer TTL for retry window
        )
        logger.warning(
            "memory.working user=%s action=store_pending count=%d",
            user_id,
            len(messages),
        )

    @staticmethod
    def pop_pending(user_id: int) -> list[dict[str, str]]:
        """Retrieve and clear any pending-distillation messages."""
        key = _pending_key(user_id)
        pending = cache.get(key) or []
        if pending:
            cache.delete(key)
            logger.info(
                "memory.working user=%s action=pop_pending count=%d",
                user_id,
                len(pending),
            )
        return pending

    # -------------------------------------------------------------- prompt
    @staticmethod
    def format_for_prompt(user_id: int) -> str:
        """
        Return the buffer formatted as conversation turns for prompt injection.
        """
        buf = WorkingMemoryBuffer.load(user_id)
        if not buf:
            return ""

        lines: list[str] = []
        for turn in buf:
            lines.append(f"User: {turn['user']}")
            lines.append(f"Assistant: {turn['model']}")
        return "\n".join(lines)

    # ─────────────────────────────────────────────── session lifecycle

    @staticmethod
    def is_stale_session(user_id: int) -> bool:
        """
        Return True if the user has an existing buffer whose last activity
        is older than ``SESSION_IDLE_TIMEOUT`` seconds.

        This means the user left and came back — the old session should
        be flushed before starting a fresh one.
        """
        last_active = cache.get(_activity_key(user_id))
        if last_active is None:
            return False  # No activity recorded → no stale session

        idle_seconds = time.time() - float(last_active)
        threshold = mem_cfg("SESSION_IDLE_TIMEOUT")

        if idle_seconds > threshold:
            buf = WorkingMemoryBuffer.load(user_id)
            if buf:  # Only stale if there's actually data to flush
                if mem_cfg("ENABLE_MEMORY_LOGGING"):
                    logger.info(
                        "memory.working user=%s action=stale_detected "
                        "idle_seconds=%d threshold=%d buffer_size=%d",
                        user_id, int(idle_seconds), threshold, len(buf),
                    )
                return True
        return False

    @staticmethod
    def get_active_user_ids() -> set[int]:
        """Return the set of user IDs that have active working memory buffers."""
        raw = cache.get(_ACTIVE_USERS_KEY)
        if raw is None:
            return set()
        if isinstance(raw, list):
            return {int(uid) for uid in raw}
        return set()

    # ─────────────────────────────────────────── internal housekeeping

    @staticmethod
    def _register_active(user_id: int) -> None:
        """Add user to the active-users set (no TTL — cleaned on flush)."""
        active = WorkingMemoryBuffer.get_active_user_ids()
        active.add(user_id)
        cache.set(_ACTIVE_USERS_KEY, list(active), timeout=None)

    @staticmethod
    def _unregister_active(user_id: int) -> None:
        """Remove user from the active-users set."""
        active = WorkingMemoryBuffer.get_active_user_ids()
        active.discard(user_id)
        if active:
            cache.set(_ACTIVE_USERS_KEY, list(active), timeout=None)
        else:
            cache.delete(_ACTIVE_USERS_KEY)

    @staticmethod
    def _touch_activity(user_id: int, ttl: int | None = None) -> None:
        """Record the current time as the user's last activity."""
        if ttl is None:
            ttl = mem_cfg("WORKING_MEMORY_TTL")
        cache.set(_activity_key(user_id), time.time(), timeout=ttl)
