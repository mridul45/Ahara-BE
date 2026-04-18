"""
Memory Consolidator — Tier 2 → Tier 3 transition.

Merges short-term session distillations into the long-term knowledge
profile.  Uses an LLM call to:

* deduplicate repeated facts,
* resolve contradictions (newer wins),
* prune stale/temporary facts, and
* keep the profile compact.

Triggered after ``CONSOLIDATION_THRESHOLD`` new session distillations.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date

from django.conf import settings
from google import genai

from .config import mem_cfg
from .long_term import LongTermStore
from .prompts import CONSOLIDATION_SYSTEM, CONSOLIDATION_USER
from .short_term import ShortTermStore

logger = logging.getLogger("memory.consolidator")


class MemoryConsolidator:
    """Merge short-term session facts into the long-term profile."""

    @staticmethod
    def consolidate(user_id: int) -> bool:
        """
        Run consolidation for a user.

        Returns ``True`` on success, ``False`` on failure.
        """
        # ── 1. Gather inputs ─────────────────────────────────────────
        existing_ltm = LongTermStore.load(user_id)
        recent_sessions = ShortTermStore.get_recent(user_id)

        # Flatten all facts from recent sessions
        new_facts: list[dict] = []
        for sess in recent_sessions:
            new_facts.extend(sess.get("facts", []))

        if not new_facts:
            logger.info(
                "memory.consolidator user=%s action=skip_empty",
                user_id,
            )
            ShortTermStore.mark_consolidated(user_id)
            return True

        # ── 2. Build consolidation prompt ─────────────────────────────
        ltm_text = json.dumps(existing_ltm, indent=2) if existing_ltm else "{}"
        facts_text = json.dumps(new_facts, indent=2)

        system_prompt = CONSOLIDATION_SYSTEM.format(
            max_tokens=mem_cfg("LTM_MAX_TOKENS_TARGET"),
        )
        user_prompt = CONSOLIDATION_USER.format(
            existing_ltm=ltm_text,
            new_facts=facts_text,
            today=date.today().isoformat(),
        )

        # ── 3. Call Gemini Flash ─────────────────────────────────────
        start = time.monotonic()
        try:
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            response = client.models.generate_content(
                model=mem_cfg("CONSOLIDATION_MODEL"),
                contents=f"{system_prompt}\n\n{user_prompt}",
            )

            elapsed_ms = int((time.monotonic() - start) * 1000)
            raw_text = response.text.strip()

            # ── 4. Parse LTM JSON ────────────────────────────────────
            merged_ltm = MemoryConsolidator._parse_ltm(raw_text)

            if merged_ltm is None:
                # Retry once
                logger.warning(
                    "memory.consolidator user=%s action=parse_retry",
                    user_id,
                )
                retry_prompt = (
                    f"{system_prompt}\n\n{user_prompt}\n\n"
                    "IMPORTANT: Your previous response was not valid JSON. "
                    "Respond with ONLY the JSON object. No markdown, no explanation."
                )
                response = client.models.generate_content(
                    model=mem_cfg("CONSOLIDATION_MODEL"),
                    contents=retry_prompt,
                )
                raw_text = response.text.strip()
                merged_ltm = MemoryConsolidator._parse_ltm(raw_text)

            if merged_ltm is None:
                raise ValueError(f"Failed to parse consolidation output: {raw_text[:200]}")

            # ── 5. Persist ────────────────────────────────────────────
            ltm_facts_before = sum(
                len(v) for v in existing_ltm.values() if isinstance(v, list)
            )
            ltm_facts_after = sum(
                len(v) for v in merged_ltm.values() if isinstance(v, list)
            )

            LongTermStore.save(user_id, merged_ltm)
            ShortTermStore.mark_consolidated(user_id)

            if mem_cfg("ENABLE_MEMORY_LOGGING"):
                logger.info(
                    "memory.consolidator user=%s action=consolidate "
                    "sessions_merged=%d ltm_facts_before=%d ltm_facts_after=%d "
                    "model=%s latency_ms=%d",
                    user_id,
                    len(recent_sessions),
                    ltm_facts_before,
                    ltm_facts_after,
                    mem_cfg("CONSOLIDATION_MODEL"),
                    elapsed_ms,
                )
            return True

        except Exception:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.exception(
                "memory.consolidator user=%s action=consolidate_failed latency_ms=%d",
                user_id,
                elapsed_ms,
            )
            # Not fatal — consolidation will retry next threshold crossing
            return False

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _parse_ltm(raw: str) -> dict | None:
        """Parse and validate the LLM's consolidation output."""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None

        if not isinstance(parsed, dict):
            return None

        # Ensure values are lists of fact dicts
        cleaned: dict = {}
        for key, value in parsed.items():
            if isinstance(value, list):
                cleaned[key] = [
                    v if isinstance(v, dict) else {"fact": str(v), "since": "unknown"}
                    for v in value
                ]
            else:
                # Skip malformed entries
                continue

        return cleaned if cleaned else None
