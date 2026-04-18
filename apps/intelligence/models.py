from django.db import models
from django.conf import settings
from django.core.cache import cache


class Memory(models.Model):
    """
    Three-tier memory store for a single user.

    * **user_snapshot** – profile data kept in sync via signals.
    * **short_term**   – recent session distillations (Tier 2).
    * **long_term**    – consolidated user knowledge profile (Tier 3).
    * **version**      – optimistic-locking counter for safe concurrent writes.

    Tier 1 (Working Memory) lives only in Redis — see ``working.py``.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memory",
    )

    # ── Tier 3: Long-Term Memory ─────────────────────────────────────
    # Consolidated, deduplicated knowledge about the user.
    # Structure: {"health": [...], "diet": [...], "goals": [...], ...}
    long_term = models.JSONField(default=dict, blank=True)

    # ── Tier 2: Short-Term Memory ────────────────────────────────────
    # Recent session fact distillations.
    # Structure: [{"ts": "...", "facts": [...], "session_id": "..."}, ...]
    short_term = models.JSONField(default=list, blank=True)

    # ── User Profile Snapshot ────────────────────────────────────────
    user_snapshot = models.JSONField(default=dict, blank=True)

    # ── Consolidation Bookkeeping ────────────────────────────────────
    sessions_since_consolidation = models.PositiveIntegerField(default=0)
    last_consolidation_at = models.DateTimeField(null=True, blank=True)

    # ── Optimistic Locking ───────────────────────────────────────────
    version = models.PositiveIntegerField(default=0)

    # ── Deprecated ───────────────────────────────────────────────────
    # Kept temporarily for rollback safety. Will be removed in a
    # follow-up migration after 2 weeks.
    data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Memory"
        verbose_name_plural = "Memories"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Memory for {self.user} (v{self.version})"

    def save(self, *args, **kwargs):
        # On creation, populate user_snapshot from the related User.
        if not self.pk:
            self.user_snapshot = self._build_user_snapshot()

        super().save(*args, **kwargs)

        # Invalidate cached memory so next read refetches.
        cache.delete(f"user_memory_{self.user_id}")

    # ── Helpers ──────────────────────────────────────────────────────

    def _build_user_snapshot(self) -> dict:
        u = self.user
        return {
            "id": u.id,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "bio": getattr(u, "bio", ""),
            "gender": getattr(u, "gender", ""),
            "city": getattr(u, "city", ""),
            "state": getattr(u, "state", ""),
            "country": getattr(u, "country", ""),
            "birth_date": (
                str(u.birth_date) if getattr(u, "birth_date", None) else None
            ),
        }