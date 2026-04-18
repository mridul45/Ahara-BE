"""
Centralized configuration for the 3-tier memory system.

Every tunable parameter is sourced from Django settings (``MEMORY_CONFIG``)
with sensible defaults so the system works out-of-the-box without any
extra settings entry.

Usage::

    from apps.intelligence.logic.memory.config import mem_cfg
    max_pairs = mem_cfg("WORKING_BUFFER_MAX_PAIRS")
"""

from django.conf import settings

_DEFAULTS = {
    # ── Tier 1: Working Memory ───────────────────────────────────────
    "WORKING_BUFFER_MAX_PAIRS": 12,       # Max user/model message pairs in buffer
    "WORKING_BUFFER_EVICT_COUNT": 6,      # Pairs to evict when buffer is full
    "WORKING_MEMORY_TTL": 7200,           # Redis TTL in seconds (2 hours)
    "SESSION_IDLE_TIMEOUT": 1800,         # 30 min idle → new session

    # ── Tier 2: Short-Term Memory ────────────────────────────────────
    "MAX_SESSION_SUMMARIES": 5,           # Keep last N session distillations
    "DISTILLATION_MODEL": "models/gemini-2.0-flash",  # Cheap, fast
    "DISTILLATION_TIMEOUT": 10,           # Seconds before giving up

    # ── Tier 3: Long-Term Memory ─────────────────────────────────────
    "CONSOLIDATION_THRESHOLD": 3,         # Consolidate after N new sessions
    "CONSOLIDATION_MODEL": "models/gemini-2.0-flash",
    "LTM_MAX_TOKENS_TARGET": 500,         # Target size for LTM document

    # ── Prompt Assembly Token Budgets ────────────────────────────────
    "TOKEN_BUDGET_SYSTEM": 200,
    "TOKEN_BUDGET_USER_PROFILE": 150,
    "TOKEN_BUDGET_LTM": 500,
    "TOKEN_BUDGET_STM": 800,
    "TOKEN_BUDGET_WORKING": 2500,

    # ── Session Lifecycle ─────────────────────────────────────────────
    "SESSION_FLUSH_MIN_TURNS": 1,      # Min turns in buffer before flushing (skip trivial)
    "STALE_BUFFER_THRESHOLD": 1800,    # Seconds idle before a buffer is considered stale (30 min)

    # ── Observability ────────────────────────────────────────────────
    "ENABLE_MEMORY_LOGGING": True,
}


def mem_cfg(key: str):
    """
    Return ``settings.MEMORY_CONFIG[key]`` if present,
    otherwise fall back to the built-in default.
    """
    overrides = getattr(settings, "MEMORY_CONFIG", {})
    try:
        return overrides[key]
    except KeyError:
        return _DEFAULTS[key]
