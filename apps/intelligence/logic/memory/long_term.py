"""
Tier 3 — Long-Term Memory Store.

Reads and writes the ``Memory.long_term`` JSONField, which holds the
consolidated, deduplicated knowledge profile about the user.

Structure::

    {
        "health":      [{"fact": "...", "since": "YYYY-MM-DD"}, ...],
        "diet":        [...],
        "goals":       [...],
        "lifestyle":   [...],
        "preferences": [...]
    }
"""

from __future__ import annotations

import json
import logging

from django.db.models import F

from apps.intelligence.models import Memory
from .config import mem_cfg

logger = logging.getLogger("memory.ltm")

_CATEGORIES = ("health", "diet", "goals", "lifestyle", "preferences")


class LongTermStore:
    """Read / write operations for Tier-3 consolidated knowledge."""

    # ── Read ─────────────────────────────────────────────────────────

    @staticmethod
    def load(user_id: int) -> dict:
        """Return the current LTM dict, or an empty structure."""
        try:
            mem = Memory.objects.get(user_id=user_id)
        except Memory.DoesNotExist:
            return {}
        return mem.long_term if isinstance(mem.long_term, dict) else {}

    # ── Write ────────────────────────────────────────────────────────

    @staticmethod
    def save(user_id: int, ltm: dict) -> None:
        """Persist a new long-term memory profile."""
        updated = Memory.objects.filter(user_id=user_id).update(
            long_term=ltm,
            version=F("version") + 1,
        )
        if not updated:
            mem, _ = Memory.objects.get_or_create(user_id=user_id)
            mem.long_term = ltm
            mem.save(update_fields=["long_term", "version", "updated_at"])

        if mem_cfg("ENABLE_MEMORY_LOGGING"):
            total_facts = sum(
                len(v) for v in ltm.values() if isinstance(v, list)
            )
            logger.info(
                "memory.ltm user=%s action=save total_facts=%d",
                user_id,
                total_facts,
            )

    # ── Prompt Formatting ────────────────────────────────────────────

    @staticmethod
    def format_for_prompt(user_id: int) -> str:
        """Render LTM as a compact text block for prompt injection."""
        ltm = LongTermStore.load(user_id)
        if not ltm:
            return ""

        lines: list[str] = []
        for category in _CATEGORIES:
            facts = ltm.get(category, [])
            if not facts:
                continue
            lines.append(f"{category.title()}:")
            for f in facts:
                fact_text = f.get("fact", "") if isinstance(f, dict) else str(f)
                lines.append(f"  - {fact_text}")
        return "\n".join(lines)
