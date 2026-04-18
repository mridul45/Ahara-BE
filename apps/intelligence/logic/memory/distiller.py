"""
Memory Distiller — Tier 1 → Tier 2 transition.

Takes raw conversation turns that have been evicted from Working Memory
and uses a cheap LLM call (Gemini Flash) to extract only the important,
persistent facts.  Trivial chatter is discarded.

The distiller is **fail-safe**: if the LLM call times out or returns
invalid JSON, the raw messages are parked in a pending queue for retry.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from django.conf import settings
from google import genai

from .config import mem_cfg
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
            Current long-term memory (so we don't re-extract known facts).

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
            facts = MemoryDistiller._parse_facts(raw_text)

            if facts is None:
                # Retry once with stricter instructions
                logger.warning(
                    "memory.distiller user=%s action=parse_retry raw_len=%d",
                    user_id,
                    len(raw_text),
                )
                retry_prompt = (
                    f"{system_prompt}\n\n{user_prompt}\n\n"
                    "IMPORTANT: Your previous response was not valid JSON. "
                    "Respond with ONLY a JSON array. No markdown, no explanation."
                )
                response = client.models.generate_content(
                    model=mem_cfg("DISTILLATION_MODEL"),
                    contents=retry_prompt,
                )
                raw_text = response.text.strip()
                facts = MemoryDistiller._parse_facts(raw_text)

            if facts is None:
                raise ValueError(f"Failed to parse distillation output: {raw_text[:200]}")

            # ── 5. Store in Short-Term Memory ─────────────────────────
            if facts:
                ShortTermStore.store(user_id, facts, session_id)

            if mem_cfg("ENABLE_MEMORY_LOGGING"):
                logger.info(
                    "memory.distiller user=%s action=distill input_pairs=%d facts_extracted=%d model=%s latency_ms=%d",
                    user_id,
                    len(all_turns),
                    len(facts),
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
    def _parse_facts(raw: str) -> list[dict] | None:
        """
        Attempt to parse the LLM output as a JSON array of fact objects.

        Returns ``None`` on failure so the caller can decide whether to retry.
        """
        # Strip markdown fences if the model wraps output
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None

        if not isinstance(parsed, list):
            return None

        # Validate minimal structure
        valid: list[dict] = []
        for item in parsed:
            if isinstance(item, dict) and "fact" in item and "category" in item:
                valid.append({
                    "fact": str(item["fact"]),
                    "category": str(item.get("category", "context")),
                    "confidence": str(item.get("confidence", "medium")),
                    "is_temporary": bool(item.get("is_temporary", False)),
                })
        return valid
