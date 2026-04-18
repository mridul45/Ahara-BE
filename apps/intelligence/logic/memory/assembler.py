"""
Prompt Assembler — reads all three memory tiers + user profile and
builds a single, token-budgeted system context for the chat model.

Token counting uses the heuristic **1 token ≈ 4 characters**, which is
conservative for English and safe for mixed-language (Hindi/English) text.
"""

from __future__ import annotations

import json
import logging

from apps.intelligence.models import Memory
from .config import mem_cfg
from .long_term import LongTermStore
from .prompts import SYSTEM_PERSONA
from .short_term import ShortTermStore
from .working import WorkingMemoryBuffer

logger = logging.getLogger("memory.assembler")


def _estimate_tokens(text: str) -> int:
    """Approximate token count from character length."""
    return max(1, len(text) // 4)


def _truncate_to_budget(text: str, max_tokens: int) -> str:
    """Truncate text to approximately ``max_tokens`` tokens."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...(truncated)"


class PromptAssembler:
    """Build the final system context from all memory tiers."""

    @staticmethod
    def build(user_id: int) -> str:
        """
        Assemble a token-budgeted prompt context string.

        Order (matches attention priority — important stuff at top & bottom)::

            1. System persona           (hardcoded)
            2. User profile snapshot    (from DB)
            3. Long-Term Memory         (Tier 3 — highest value per token)
            4. Short-Term Memory        (Tier 2)
            5. Working Memory           (Tier 1 — most recent raw turns)

        The caller prepends this to the user's query.
        """
        budget_system = mem_cfg("TOKEN_BUDGET_SYSTEM")
        budget_profile = mem_cfg("TOKEN_BUDGET_USER_PROFILE")
        budget_ltm = mem_cfg("TOKEN_BUDGET_LTM")
        budget_stm = mem_cfg("TOKEN_BUDGET_STM")
        budget_wm = mem_cfg("TOKEN_BUDGET_WORKING")

        # ── 1. System persona ────────────────────────────────────────
        persona = _truncate_to_budget(SYSTEM_PERSONA, budget_system)

        # ── 2. User profile ──────────────────────────────────────────
        profile_text = PromptAssembler._format_profile(user_id)
        profile_text = _truncate_to_budget(profile_text, budget_profile)

        # ── 3. Long-Term Memory ──────────────────────────────────────
        ltm_text = LongTermStore.format_for_prompt(user_id)
        ltm_text = _truncate_to_budget(ltm_text, budget_ltm)

        # ── 4. Short-Term Memory ─────────────────────────────────────
        stm_text = ShortTermStore.format_for_prompt(user_id)

        # If LTM or profile are under budget, redistribute to STM
        ltm_savings = budget_ltm - _estimate_tokens(ltm_text)
        profile_savings = budget_profile - _estimate_tokens(profile_text)
        effective_stm_budget = budget_stm + max(0, ltm_savings) + max(0, profile_savings)
        stm_text = _truncate_to_budget(stm_text, effective_stm_budget)

        # ── 5. Working Memory ────────────────────────────────────────
        wm_text = WorkingMemoryBuffer.format_for_prompt(user_id)

        # If STM is under budget, redistribute to WM
        stm_savings = effective_stm_budget - _estimate_tokens(stm_text)
        effective_wm_budget = budget_wm + max(0, stm_savings)
        wm_text = _truncate_to_budget(wm_text, effective_wm_budget)

        # ── Assemble ─────────────────────────────────────────────────
        sections: list[str] = [persona]

        if profile_text:
            sections.append(f"\n## About This User\n{profile_text}")

        if ltm_text:
            sections.append(f"\n## What You Know About Them\n{ltm_text}")

        if stm_text:
            sections.append(f"\n## Recent Session Notes\n{stm_text}")

        if wm_text:
            sections.append(f"\n## Recent Conversation\n{wm_text}")

        context = "\n".join(sections)

        # ── Observability ────────────────────────────────────────────
        if mem_cfg("ENABLE_MEMORY_LOGGING"):
            tokens = {
                "system": _estimate_tokens(persona),
                "profile": _estimate_tokens(profile_text),
                "ltm": _estimate_tokens(ltm_text),
                "stm": _estimate_tokens(stm_text),
                "wm": _estimate_tokens(wm_text),
                "total": _estimate_tokens(context),
            }
            logger.info(
                "memory.assembler user=%s tokens=%s",
                user_id,
                json.dumps(tokens),
            )

        return context

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _format_profile(user_id: int) -> str:
        """Format the user_snapshot as readable key-value lines."""
        try:
            mem = Memory.objects.get(user_id=user_id)
        except Memory.DoesNotExist:
            return ""

        snapshot = mem.user_snapshot or {}
        if not snapshot:
            return ""

        lines: list[str] = []
        for key, value in snapshot.items():
            if value and key != "id":
                label = key.replace("_", " ").title()
                lines.append(f"- {label}: {value}")
        return "\n".join(lines)
