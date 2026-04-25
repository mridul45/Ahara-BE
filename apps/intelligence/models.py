import uuid

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


# ═══════════════════════════════════════════════════════════════════════
# Chat History — Persistent conversation sessions for browse & resume.
#
# This is fully decoupled from the 3-tier Memory system.  Memory stores
# *distilled facts* for AI context; ChatSession / ChatMessage store the
# *raw conversation log* so users can revisit and continue past chats.
# ═══════════════════════════════════════════════════════════════════════

class ChatSession(models.Model):
    """
    Persistent record of a single chat conversation.

    Uses a UUID primary key so the mobile app can generate session IDs
    locally (offline-friendly) and sync them to the server later.
    """

    # ── Configuration ────────────────────────────────────────────────
    MAX_TITLE_LENGTH = 120
    MAX_SESSIONS_PER_USER = 50  # Retention limit for Render free tier

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
        db_index=True,
    )
    title = models.CharField(
        max_length=MAX_TITLE_LENGTH,
        blank=True,
        default="",
        help_text="Auto-generated from the first user message if left blank.",
    )
    is_archived = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Soft-delete flag. Archived sessions are hidden from the UI.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Chat Session"
        verbose_name_plural = "Chat Sessions"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(
                fields=["user", "-updated_at"],
                name="idx_chatsession_user_updated",
            ),
        ]

    def __str__(self):
        title = self.title or "Untitled"
        return f"[{self.user}] {title} ({self.id.hex[:8]})"

    def generate_title_from_message(self, message_text: str) -> None:
        """
        Auto-generate a session title from the first user message.

        Only sets the title if it is currently blank.  Truncates at the
        last word boundary within ``MAX_TITLE_LENGTH`` characters.
        """
        if self.title:
            return

        text = message_text.strip()
        if not text:
            self.title = "New Chat"
            return

        # Truncate at word boundary
        if len(text) <= self.MAX_TITLE_LENGTH:
            self.title = text
        else:
            truncated = text[: self.MAX_TITLE_LENGTH].rsplit(" ", 1)[0]
            self.title = truncated if truncated else text[: self.MAX_TITLE_LENGTH]

    @classmethod
    def enforce_retention(cls, user_id: int) -> int:
        """
        Archive the oldest sessions beyond the per-user retention limit.

        Returns the number of sessions archived.
        """
        active_ids = list(
            cls.objects.filter(user_id=user_id, is_archived=False)
            .order_by("-updated_at")
            .values_list("id", flat=True)[: cls.MAX_SESSIONS_PER_USER]
        )
        archived_count = (
            cls.objects.filter(user_id=user_id, is_archived=False)
            .exclude(id__in=active_ids)
            .update(is_archived=True)
        )
        return archived_count


class ChatMessage(models.Model):
    """
    Individual message within a ChatSession.

    Stores the raw user prompt or assistant response with its role and
    timestamp, preserving the full conversation for resumption.
    """

    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Chat Message"
        verbose_name_plural = "Chat Messages"
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["session", "created_at"],
                name="idx_chatmsg_session_created",
            ),
        ]

    def __str__(self):
        preview = self.content[:60].replace("\n", " ")
        return f"[{self.role}] {preview}..."