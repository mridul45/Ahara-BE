"""
Tier 2 — Short-Term Memory Store.

Persists distilled session summaries in the ``Memory.short_term`` JSONField.
Each entry is::

    {
        "ts":         "2026-04-12T21:30:00+05:30",
        "session_id": "a1b2c3d4e5f6",
        "facts": [
            {"fact": "...", "category": "...", "confidence": "...", "is_temporary": false}
        ]
    }

The store enforces a bounded rotation: only the most recent
``MAX_SESSION_SUMMARIES`` entries are kept.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from django.db.models import F

from apps.intelligence.models import Memory
from .config import mem_cfg

logger = logging.getLogger("memory.stm")


class ShortTermStore:
    """Read / write operations for Tier-2 session distillations."""

    # ── Write ────────────────────────────────────────────────────────

    @staticmethod
    def store(user_id: int, facts: list[dict], session_id: str) -> None:
        """
        Append a new session distillation and enforce the rotation limit.
        Also increments ``sessions_since_consolidation``.
        """
        if not facts:
            logger.info("memory.stm user=%s action=skip_empty session=%s", user_id, session_id)
            return

        entry = {
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "session_id": session_id,
            "facts": facts,
        }

        mem, _ = Memory.objects.get_or_create(user_id=user_id)
        stm: list = mem.short_term if isinstance(mem.short_term, list) else []
        stm.append(entry)

        # Enforce rotation
        max_sessions = mem_cfg("MAX_SESSION_SUMMARIES")
        if len(stm) > max_sessions:
            stm = stm[-max_sessions:]

        mem.short_term = stm
        mem.sessions_since_consolidation = F("sessions_since_consolidation") + 1
        mem.version = F("version") + 1
        mem.save(update_fields=["short_term", "sessions_since_consolidation", "version", "updated_at"])

        # Refresh to get actual values after F() expressions
        mem.refresh_from_db(fields=["sessions_since_consolidation", "version"])

        if mem_cfg("ENABLE_MEMORY_LOGGING"):
            logger.info(
                "memory.stm user=%s action=store session=%s facts=%d total_sessions=%d sessions_since_consolidation=%d",
                user_id,
                session_id,
                len(facts),
                len(stm),
                mem.sessions_since_consolidation,
            )

    # ── Read ─────────────────────────────────────────────────────────

    @staticmethod
    def get_recent(user_id: int, limit: int | None = None) -> list[dict]:
        """Return the ``limit`` most recent session summaries."""
        try:
            mem = Memory.objects.get(user_id=user_id)
        except Memory.DoesNotExist:
            return []

        stm = mem.short_term if isinstance(mem.short_term, list) else []
        if limit is not None:
            stm = stm[-limit:]
        return stm

    @staticmethod
    def needs_consolidation(user_id: int) -> bool:
        """True when enough sessions have accumulated since the last consolidation."""
        try:
            mem = Memory.objects.get(user_id=user_id)
        except Memory.DoesNotExist:
            return False
        return mem.sessions_since_consolidation >= mem_cfg("CONSOLIDATION_THRESHOLD")

    # ── Prompt Formatting ────────────────────────────────────────────

    @staticmethod
    def format_for_prompt(user_id: int) -> str:
        """
        Format recent session facts as a compact text block for prompt injection.
        """
        sessions = ShortTermStore.get_recent(user_id)
        if not sessions:
            return ""

        lines: list[str] = []
        for sess in sessions:
            ts = sess.get("ts", "unknown")
            facts = sess.get("facts", [])
            if not facts:
                continue
            lines.append(f"Session ({ts[:10]}):")
            for f in facts:
                cat = f.get("category", "")
                fact_text = f.get("fact", "")
                lines.append(f"  - [{cat}] {fact_text}")
        return "\n".join(lines)

    # ── Cleanup after consolidation ──────────────────────────────────

    @staticmethod
    def mark_consolidated(user_id: int) -> None:
        """Reset the consolidation counter after a successful merge."""
        Memory.objects.filter(user_id=user_id).update(
            sessions_since_consolidation=0,
            last_consolidation_at=datetime.now(tz=timezone.utc),
            version=F("version") + 1,
        )
