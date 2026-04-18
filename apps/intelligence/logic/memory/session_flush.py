"""
Session Flusher — centralised end-of-session logic.

Used by all three lifecycle layers:

1. ``POST /api/intelligence/end-session/``  (app-triggered)
2. ``manage.py memory_flush_stale``         (periodic sweep)
3. ``record_interaction()`` auto-flush      (on return after idle)

The flusher is **fail-safe**: if distillation fails, messages are
parked in the pending queue (same as the existing eviction path).
"""

from __future__ import annotations

import logging

from .config import mem_cfg
from .distiller import MemoryDistiller
from .long_term import LongTermStore
from .short_term import ShortTermStore
from .working import WorkingMemoryBuffer

logger = logging.getLogger("memory.flush")


class SessionFlusher:
    """
    Flush working memory → distill → persist to PostgreSQL.

    All methods are safe to call — failures are logged and never raised.
    """

    @staticmethod
    def flush_user(user_id: int, trigger: str = "unknown") -> dict:
        """
        Flush remaining working memory for a user and distill it.

        Parameters
        ----------
        user_id : int
            The user whose session is ending.
        trigger : str
            Why the flush was triggered (for logging).
            One of: 'end_session', 'stale_sweep', 'auto_return'.

        Returns
        -------
        dict
            ``{"flushed": bool, "turns": int, "facts_count": int}``
        """
        result = {"flushed": False, "turns": 0, "facts_count": 0}

        try:
            # ── 1. Check minimum-turns threshold ─────────────────────
            buf = WorkingMemoryBuffer.load(user_id)
            min_turns = mem_cfg("SESSION_FLUSH_MIN_TURNS")

            if len(buf) < min_turns:
                if mem_cfg("ENABLE_MEMORY_LOGGING"):
                    logger.info(
                        "memory.flush user=%s action=skip_below_min "
                        "buffer_size=%d min_turns=%d trigger=%s",
                        user_id, len(buf), min_turns, trigger,
                    )
                # Still clean up Redis even if we skip distillation
                if buf:
                    WorkingMemoryBuffer.flush(user_id)
                return result

            # ── 2. Flush the buffer (clears Redis) ───────────────────
            session_id = WorkingMemoryBuffer.get_session_id(user_id)
            turns = WorkingMemoryBuffer.flush(user_id)

            if not turns:
                return result

            result["turns"] = len(turns)

            if mem_cfg("ENABLE_MEMORY_LOGGING"):
                logger.info(
                    "memory.flush user=%s action=flush_start "
                    "turns=%d session=%s trigger=%s",
                    user_id, len(turns), session_id, trigger,
                )

            # ── 3. Distill into Short-Term Memory ────────────────────
            existing_ltm = LongTermStore.load(user_id)

            facts = MemoryDistiller.distill(
                user_id=user_id,
                turns=turns,
                session_id=session_id,
                existing_ltm=existing_ltm,
            )

            result["facts_count"] = len(facts) if facts else 0
            result["flushed"] = True

            # ── 4. Consolidate if threshold crossed ──────────────────
            if ShortTermStore.needs_consolidation(user_id):
                from .consolidator import MemoryConsolidator
                MemoryConsolidator.consolidate(user_id)

            if mem_cfg("ENABLE_MEMORY_LOGGING"):
                logger.info(
                    "memory.flush user=%s action=flush_complete "
                    "turns=%d facts=%d trigger=%s",
                    user_id, len(turns), result["facts_count"], trigger,
                )

            return result

        except Exception:
            logger.exception(
                "memory.flush user=%s action=flush_failed trigger=%s",
                user_id, trigger,
            )
            return result
