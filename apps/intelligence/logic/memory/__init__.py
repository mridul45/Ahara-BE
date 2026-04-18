"""
MemoryManager — Enterprise facade for the 3-tier memory system.

This is the **only** class that ``views.py`` should interact with.
It orchestrates Working Memory ↔ Distillation ↔ Short-Term ↔
Consolidation ↔ Long-Term behind simple methods:

* ``build_prompt_context(user)`` — read all tiers, return token-budgeted
  context string.
* ``record_interaction(user, user_msg, model_response)`` — append to
  Working Memory and trigger distillation / consolidation when thresholds
  are crossed.
* ``end_session(user)`` — flush remaining Working Memory at session end
  and distill into persistent storage.
"""

from __future__ import annotations

import logging

from django.contrib.auth import get_user_model

from .assembler import PromptAssembler
from .config import mem_cfg
from .consolidator import MemoryConsolidator
from .distiller import MemoryDistiller
from .long_term import LongTermStore
from .session_flush import SessionFlusher
from .short_term import ShortTermStore
from .working import WorkingMemoryBuffer

logger = logging.getLogger("memory")

User = get_user_model()


class MemoryManager:
    """
    Public API for the memory system.

    All methods are safe to call — failures are logged and handled
    internally without raising to the caller.
    """

    # ── Read Path ────────────────────────────────────────────────────

    @staticmethod
    def build_prompt_context(user) -> str:
        """
        Read all memory tiers and return a token-budgeted system context
        string ready for prompt injection.

        Returns an empty string for anonymous users.
        """
        if not user or not user.is_authenticated:
            return "User is anonymous (no memory context)."

        try:
            return PromptAssembler.build(user.id)
        except Exception:
            logger.exception(
                "memory user=%s action=build_context_failed", user.id,
            )
            return ""

    # ── Write Path ───────────────────────────────────────────────────

    @staticmethod
    def record_interaction(
        user,
        user_msg: str,
        model_response: str,
    ) -> None:
        """
        Record a conversation turn and handle memory lifecycle.

        This runs **after** the streaming response is delivered to the
        client (post-yield), so any latency here is invisible to the user.

        Lifecycle:
        0. If user is returning after idle → auto-flush old session first.
        1. Append to Working Memory buffer.
        2. If buffer exceeds threshold → evict oldest turns → distill.
        3. If distilled sessions cross consolidation threshold → consolidate.
        """
        if not user or not user.is_authenticated:
            return

        user_id = user.id

        try:
            # ── Step 0: Auto-flush stale session on return ───────────
            if WorkingMemoryBuffer.is_stale_session(user_id):
                logger.info(
                    "memory user=%s action=auto_flush_stale trigger=return_after_idle",
                    user_id,
                )
                SessionFlusher.flush_user(user_id, trigger="auto_return")

            # ── Step 1: Append to Working Memory ─────────────────────
            buffer_len = WorkingMemoryBuffer.append(user_id, user_msg, model_response)

            # ── Step 2: Evict + Distill if needed ────────────────────
            if WorkingMemoryBuffer.needs_eviction(user_id):
                evicted = WorkingMemoryBuffer.evict(user_id)
                if evicted:
                    session_id = WorkingMemoryBuffer.get_session_id(user_id)
                    existing_ltm = LongTermStore.load(user_id)

                    MemoryDistiller.distill(
                        user_id=user_id,
                        turns=evicted,
                        session_id=session_id,
                        existing_ltm=existing_ltm,
                    )

                    # ── Step 3: Consolidate if threshold crossed ─────
                    if ShortTermStore.needs_consolidation(user_id):
                        MemoryConsolidator.consolidate(user_id)

        except Exception:
            # Never let memory processing crash the request lifecycle
            logger.exception(
                "memory user=%s action=record_interaction_failed", user_id,
            )

    # ── Session Lifecycle ────────────────────────────────────────────

    @staticmethod
    def end_session(user) -> dict:
        """
        Flush remaining Working Memory and distill into persistent storage.

        Called by:
        - ``POST /api/intelligence/end-session/`` (mobile app on exit)
        - ``manage.py memory_flush_stale`` (periodic sweep)

        Returns
        -------
        dict
            ``{"flushed": bool, "turns": int, "facts_count": int}``
        """
        if not user or not user.is_authenticated:
            return {"flushed": False, "turns": 0, "facts_count": 0}

        try:
            return SessionFlusher.flush_user(user.id, trigger="end_session")
        except Exception:
            logger.exception(
                "memory user=%s action=end_session_failed", user.id,
            )
            return {"flushed": False, "turns": 0, "facts_count": 0}


__all__ = ["MemoryManager"]

