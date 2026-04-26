"""
Memory Distiller — Tier 1 → Tier 2 transition.

Takes raw conversation turns that have been evicted from Working Memory
and uses a cheap LLM call (Gemini Flash) to extract only the important,
persistent facts.  Trivial chatter is discarded.

The distiller also detects **contradictions** with existing Long-Term
Memory and patches them immediately — so the user's profile stays
accurate without waiting for the next consolidation cycle.

The distiller is **fail-safe**: if the LLM call times out or returns
invalid JSON, the raw messages are parked in a pending queue for retry.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date
from typing import Any

from django.conf import settings
from google import genai

from .config import mem_cfg
from .long_term import LongTermStore
from .prompts import DISTILLATION_SYSTEM, DISTILLATION_USER
from .short_term import ShortTermStore
from .working import WorkingMemoryBuffer

logger = logging.getLogger("memory.distiller")


class MemoryDistiller:
    """Extract actionable facts from raw conversation turns."""

    @staticmethod
    def distill(
        user_id: int,
        turns: list[dict[str, str]],
        session_id: str,
        existing_ltm: dict | None = None,
    ) -> list[dict]:
        """
        Distill a batch of conversation turns into structured facts.

        Parameters
        ----------
        user_id : int
            Owning user.
        turns : list[dict]
            Each turn is ``{"user": ..., "model": ...}``.
        session_id : str
            Current session identifier.
        existing_ltm : dict, optional
            Current long-term memory (for contradiction detection).

        Returns
        -------
        list[dict]
            Extracted facts, each with keys ``fact``, ``category``,
            ``confidence``, ``is_temporary``.
        """
        if not turns:
            return []

        # ── 1. Also grab any pending messages from a previous failure ─
        pending = WorkingMemoryBuffer.pop_pending(user_id)
        all_turns = pending + turns

        # ── 2. Format conversation for the prompt ─────────────────────
        conv_lines: list[str] = []
        for t in all_turns:
            conv_lines.append(f"User: {t['user']}")
            conv_lines.append(f"Assistant: {t['model']}")
        conversation_text = "\n".join(conv_lines)

        ltm_text = json.dumps(existing_ltm, indent=2) if existing_ltm else "(no existing memory)"

        system_prompt = DISTILLATION_SYSTEM.format(existing_ltm=ltm_text)
        user_prompt = DISTILLATION_USER.format(conversation=conversation_text)

        # ── 3. Call Gemini Flash ──────────────────────────────────────
        start = time.monotonic()
        try:
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            response = client.models.generate_content(
                model=mem_cfg("DISTILLATION_MODEL"),
                contents=f"{system_prompt}\n\n{user_prompt}",
            )

            elapsed_ms = int((time.monotonic() - start) * 1000)
            raw_text = response.text.strip()

            # ── 4. Parse JSON (with retry on failure) ─────────────────
            result = MemoryDistiller._parse_response(raw_text)

            if result is None:
                # Retry once with stricter instructions
                logger.warning(
                    "memory.distiller user=%s action=parse_retry raw_len=%d",
                    user_id,
                    len(raw_text),
                )
                retry_prompt = (
                    f"{system_prompt}\n\n{user_prompt}\n\n"
                    "IMPORTANT: Your previous response was not valid JSON. "
                    "Respond with ONLY the JSON object. No markdown, no explanation."
                )
                response = client.models.generate_content(
                    model=mem_cfg("DISTILLATION_MODEL"),
                    contents=retry_prompt,
                )
                raw_text = response.text.strip()
                result = MemoryDistiller._parse_response(raw_text)

            if result is None:
                raise ValueError(f"Failed to parse distillation output: {raw_text[:200]}")

            facts, contradictions = result

            # ── 5. Apply contradictions to LTM immediately ────────────
            if contradictions and existing_ltm:
                MemoryDistiller._apply_contradictions(
                    user_id, existing_ltm, contradictions,
                )

            # ── 6. Store facts in Short-Term Memory ───────────────────
            ShortTermStore.store(user_id, facts, session_id)

            if mem_cfg("ENABLE_MEMORY_LOGGING"):
                logger.info(
                    "memory.distiller user=%s action=distill input_pairs=%d "
                    "facts_extracted=%d contradictions=%d model=%s latency_ms=%d",
                    user_id,
                    len(all_turns),
                    len(facts),
                    len(contradictions),
                    mem_cfg("DISTILLATION_MODEL"),
                    elapsed_ms,
                )

            return facts

        except Exception:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.exception(
                "memory.distiller user=%s action=distill_failed latency_ms=%d",
                user_id,
                elapsed_ms,
            )
            # Park messages for retry on next interaction
            WorkingMemoryBuffer.store_pending(user_id, all_turns)
            return []

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _parse_response(raw: str) -> tuple[list[dict], list[dict]] | None:
        """
        Parse the LLM output into (facts, contradictions).

        Handles both the new object format and the legacy array format
        for backwards compatibility.

        Returns ``None`` on failure so the caller can decide whether to retry.
        """
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None

        # ── New format: {"facts": [...], "contradictions": [...]}
        if isinstance(parsed, dict) and "facts" in parsed:
            facts = MemoryDistiller._validate_facts(parsed.get("facts", []))
            contradictions = MemoryDistiller._validate_contradictions(
                parsed.get("contradictions", [])
            )
            return (facts, contradictions)

        # ── Legacy format: plain array of facts
        if isinstance(parsed, list):
            facts = MemoryDistiller._validate_facts(parsed)
            return (facts, [])

        return None

    @staticmethod
    def _validate_facts(items: list) -> list[dict]:
        """Validate and normalise a list of fact objects."""
        valid: list[dict] = []
        for item in items:
            if isinstance(item, dict) and "fact" in item and "category" in item:
                valid.append({
                    "fact": str(item["fact"]),
                    "category": str(item.get("category", "context")),
                    "confidence": str(item.get("confidence", "medium")),
                    "is_temporary": bool(item.get("is_temporary", False)),
                })
        return valid

    @staticmethod
    def _validate_contradictions(items: list) -> list[dict]:
        """Validate a list of contradiction objects."""
        valid: list[dict] = []
        for item in items:
            if (
                isinstance(item, dict)
                and "category" in item
                and "old_fact" in item
                and "new_fact" in item
            ):
                valid.append({
                    "category": str(item["category"]),
                    "old_fact": str(item["old_fact"]),
                    "new_fact": str(item["new_fact"]),
                })
        return valid

    @staticmethod
    def _apply_contradictions(
        user_id: int,
        existing_ltm: dict,
        contradictions: list[dict],
    ) -> None:
        """
        Patch LTM by replacing contradicted facts in-place.

        Uses fuzzy matching (substring containment) so the LLM doesn't
        have to reproduce the exact stored text character-for-character.
        """
        patched = False
        today = str(date.today())

        for contradiction in contradictions:
            category = contradiction["category"]
            old_fact_text = contradiction["old_fact"].lower().strip()
            new_fact_text = contradiction["new_fact"]

            facts = existing_ltm.get(category, [])
            replaced = False

            for i, fact_entry in enumerate(facts):
                stored_text = (
                    fact_entry.get("fact", "").lower().strip()
                    if isinstance(fact_entry, dict)
                    else str(fact_entry).lower().strip()
                )

                # Fuzzy match: either the stored text contains the old,
                # or the old contains the stored text
                if old_fact_text in stored_text or stored_text in old_fact_text:
                    facts[i] = {"fact": new_fact_text, "since": today}
                    replaced = True
                    patched = True
                    logger.info(
                        "memory.distiller user=%s action=patch_ltm "
                        "category=%s old='%s' new='%s'",
                        user_id,
                        category,
                        stored_text[:60],
                        new_fact_text[:60],
                    )
                    break

            # If old fact wasn't found, append the new fact anyway
            if not replaced:
                facts.append({"fact": new_fact_text, "since": today})
                existing_ltm[category] = facts
                patched = True
                logger.info(
                    "memory.distiller user=%s action=append_contradicted_fact "
                    "category=%s fact='%s'",
                    user_id,
                    category,
                    new_fact_text[:60],
                )

        if patched:
            LongTermStore.save(user_id, existing_ltm)

