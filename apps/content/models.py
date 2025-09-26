from datetime import timezone
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import F
from django.utils.translation import gettext_lazy as _
from utilities.enums import (ContentGenreEnum,LanguageEnum,CTypeEnum,DifficultyLevelEnum)
from utilities.storages import ImageKitStorage


# Create your models here.
class Playlist(models.Model):
    """A curated, ordered set of lessons/meditations."""

    # ---------- Core ----------
    title = models.CharField(_("Title"), max_length=255, null=True, blank=True,
                             help_text=_("Display name for this playlist (shown to users)."))
    description = models.TextField(_("Description"), null=True, blank=True,
                                   help_text=_("Short summary shown in the app or SEO snippets."))

    playlist_type = models.CharField(
        _("Playlist Type"), max_length=50,
        choices=[(t.name, t.value) for t in ContentGenreEnum],
        null=True, blank=True, help_text=_("Select the category/genre of this playlist.")
    )
    language = models.CharField(
        _("Language"), max_length=50,
        choices=[(l.name, l.value) for l in LanguageEnum],
        null=True, blank=True, help_text=_("Select the main language of this playlist.")
    )

    thumbnail = models.ImageField(
        _("Thumbnail"),
        storage=ImageKitStorage(),
        upload_to="content/playlists/thumbnails",
        max_length=1000,
        null=True,
        blank=True,
        help_text=_("Cover image for this playlist, shown in feeds and listings.")
    )
    thumbnail_file_id = models.CharField(
        _("Thumbnail File ID"),
        max_length=1000,
        null=True,
        blank=True,
        editable=False
    )

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    # ---------- Analytics (denormalized counters & rollups) ----------
    # Exposure & engagement funnel
    impressions = models.PositiveBigIntegerField(default=0, help_text=_("Times shown in feeds/search."))
    clicks = models.PositiveBigIntegerField(default=0, help_text=_("Times opened from an impression."))
    starts = models.PositiveBigIntegerField(default=0, help_text=_("First play started (at least 1s)."))
    completes = models.PositiveBigIntegerField(default=0, help_text=_("Completed all items or 90% avg."))

    # Interaction signals
    likes = models.PositiveBigIntegerField(default=0)
    bookmarks = models.PositiveBigIntegerField(default=0, help_text=_("Saves/‘watch later’."))
    shares = models.PositiveBigIntegerField(default=0)

    # Watch/learn quality
    total_watch_seconds = models.PositiveBigIntegerField(default=0, help_text=_("Sum of watch time across users."))
    avg_watch_seconds = models.FloatField(default=0.0, help_text=_("Rolling average watch seconds per start."))
    avg_progress_pct = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text=_("Average percent completed across viewers.")
    )

    # Ratings (optional quick stars/NPS-style)
    rating_count = models.PositiveBigIntegerField(default=0)
    rating_sum = models.PositiveBigIntegerField(default=0, help_text=_("Sum of 1–5 star ratings for fast avg."))
    # Derived average can be computed via property

    # Health/quality rates (optional persisted rollups to sort/filter quickly)
    ctr = models.DecimalField(  # Click-through rate (clicks / impressions)
        max_digits=6, decimal_places=4, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text=_("Click-through rate; cached rollup [0–1].")
    )
    completion_rate = models.DecimalField(  # completes / starts
        max_digits=6, decimal_places=4, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text=_("Completion rate; cached rollup [0–1].")
    )
    bounce_rate = models.DecimalField(  # (starts with <10s) / starts
        max_digits=6, decimal_places=4, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text=_("Short-view exit fraction; cached rollup [0–1].")
    )

    # Last activity snapshots (useful for admin/UI freshness)
    last_impressed_at = models.DateTimeField(null=True, blank=True)
    last_clicked_at = models.DateTimeField(null=True, blank=True)
    last_started_at = models.DateTimeField(null=True, blank=True)
    last_completed_at = models.DateTimeField(null=True, blank=True)
    last_interaction_at = models.DateTimeField(null=True, blank=True)

    # Optional breakdowns & metadata (Postgres JSONB works great)
    breakdown = models.JSONField(
        null=True, blank=True,
        help_text=_("Small cached breakdowns, e.g., {'device': {'ios': 120, 'android': 300}, 'geo': {...}}")
    )

    class Meta:
        verbose_name = _("Playlist")
        verbose_name_plural = _("Playlists")
        ordering = ("-updated_at",)
        indexes = [
            models.Index(fields=("updated_at",)),
            models.Index(fields=("impressions", "-ctr")),  # fast ranking in feeds
            models.Index(fields=("completion_rate",)),
            models.Index(fields=("language", "playlist_type")),
        ]

    def __str__(self):
        return self.title or f"Playlist {self.pk}"

    # ---------- Derived properties (no extra writes) ----------
    @property
    def average_rating(self) -> float:
        return (self.rating_sum / self.rating_count) if self.rating_count else 0.0

    @property
    def computed_ctr(self) -> float:
        return float(self.clicks) / self.impressions if self.impressions else 0.0

    @property
    def computed_completion_rate(self) -> float:
        return float(self.completes) / self.starts if self.starts else 0.0

    # ---------- Safe atomic updaters (use in services/tasks) ----------
    def inc_impression(self, when=None):
        self.__class__.objects.filter(pk=self.pk).update(
            impressions=F("impressions") + 1,
            last_impressed_at=when or timezone.now(),
        )

    def inc_click(self, when=None):
        self.__class__.objects.filter(pk=self.pk).update(
            clicks=F("clicks") + 1,
            last_clicked_at=when or timezone.now(),
        )

    def inc_start(self, when=None):
        self.__class__.objects.filter(pk=self.pk).update(
            starts=F("starts") + 1,
            last_started_at=when or timezone.now(),
            last_interaction_at=when or timezone.now(),
        )

    def inc_complete(self, when=None):
        self.__class__.objects.filter(pk=self.pk).update(
            completes=F("completes") + 1,
            last_completed_at=when or timezone.now(),
            last_interaction_at=when or timezone.now(),
        )

    def add_watch_time(self, seconds: int):
        """Update total + rolling average safely."""
        seconds = max(0, int(seconds or 0))
        # Update totals
        self.__class__.objects.filter(pk=self.pk).update(
            total_watch_seconds=F("total_watch_seconds") + seconds
        )
        # Optionally refresh small fields for in-process average (cheap read)
        self.refresh_from_db(fields=["total_watch_seconds", "starts"])
        if self.starts:
            new_avg = self.total_watch_seconds / float(self.starts)
            self.__class__.objects.filter(pk=self.pk).update(avg_watch_seconds=new_avg)

    def add_rating(self, stars: int):
        stars = int(stars or 0)
        stars = min(max(stars, 1), 5)
        self.__class__.objects.filter(pk=self.pk).update(
            rating_count=F("rating_count") + 1,
            rating_sum=F("rating_sum") + stars
        )

    def recompute_rollups(self):
        """Call from a nightly task to keep cached rates fresh without hot-path cost."""
        ctr = (self.clicks / self.impressions) if self.impressions else 0.0
        completion = (self.completes / self.starts) if self.starts else 0.0
        # bounce_rate should be computed from event table; keep as is or update here.
        self.__class__.objects.filter(pk=self.pk).update(
            ctr=ctr, completion_rate=completion
        )
    


class Video(models.Model):
    """Video model where all files are stored on ImageKit, classified by type, genre, and language."""

    playlist = models.ManyToManyField(Playlist, related_name="videos", blank=True)
    title = models.CharField(_("Title"), max_length=255)
    description = models.TextField(_("Description"), null=True, blank=True)
    instructor = models.CharField(_("Instructor"), max_length=1000, null=True, blank=True)

    # Classification fields
    content_genre = models.CharField(
        _("Content Genre"),
        max_length=50,
        choices=[(tag.name, tag.value) for tag in ContentGenreEnum],
        null=True,
        blank=True,
        help_text=_("Describes the genre of the content."),
    )
    content_type = models.CharField(
        _("Content Type"),
        max_length=50,
        choices=[(tag.name, tag.value) for tag in CTypeEnum],
        null=True,
        blank=True,
        help_text=_("Describes the form of the content."),
    )
    language = models.CharField(
        _("Language"),
        max_length=50,
        choices=[(tag.name, tag.value) for tag in LanguageEnum],
        default=LanguageEnum.ENGLISH.name,
        help_text=_("Primary language of the content."),
    )
    difficulty_level = models.CharField(
        _("Difficulty Level"),
        max_length=50,
        choices=[(tag.name, tag.value) for tag in DifficultyLevelEnum],
        null=True,
        blank=True,
        help_text=_("Indicates the difficulty level of the content."),
    )

    # Media files
    video = models.FileField(
        _("Video File"),
        storage=ImageKitStorage(),
        upload_to="content/videos",
        max_length=1000,
        null=True,
        blank=True,
    )
    video_file_id = models.CharField(
        _("Video File ID"), max_length=1000, null=True, blank=True, editable=False
    )

    thumbnail = models.ImageField(
        _("Thumbnail"),
        storage=ImageKitStorage(),
        upload_to="content/videos/thumbnails",
        max_length=1000,
        null=True,
        blank=True,
    )
    thumbnail_file_id = models.CharField(
        _("Thumbnail File ID"), max_length=1000, null=True, blank=True, editable=False
    )

    subtitles = models.FileField(
        _("Subtitles"),
        storage=ImageKitStorage(),
        upload_to="content/videos/subtitles",
        max_length=1000,
        null=True,
        blank=True,
    )
    subtitles_file_id = models.CharField(
        _("Subtitles File ID"), max_length=1000, null=True, blank=True, editable=False
    )

    transcript = models.FileField(
        _("Transcript"),
        storage=ImageKitStorage(),
        upload_to="content/videos/transcripts",
        max_length=1000,
        null=True,
        blank=True,
    )
    transcript_file_id = models.CharField(
        _("Transcript File ID"), max_length=1000, null=True, blank=True, editable=False
    )

    # Playback metadata
    duration_seconds = models.PositiveIntegerField(_("Duration (seconds)"), null=True, blank=True)
    hls_manifest_url = models.URLField(_("HLS Manifest URL"), null=True, blank=True)

    # Publishing / access control
    is_published = models.BooleanField(_("Published"), default=False)
    publish_at = models.DateTimeField(_("Publish At"), null=True, blank=True)
    is_featured = models.BooleanField(_("Featured"), default=False)
    requires_subscription = models.BooleanField(_("Requires Subscription"), default=False)
    zen_mode_only = models.BooleanField(_("Zen Mode Only"), default=False)

    # AI metadata
    ai_pose_model_version = models.CharField(_("AI Pose Model Version"), max_length=100, null=True, blank=True)

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Video")
        verbose_name_plural = _("Videos")
        ordering = ["-created_at"]

    def __str__(self):
        return self.title or f"Video {self.pk}"