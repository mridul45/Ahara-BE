from datetime import timezone
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Case, ExpressionWrapper, F, FloatField, Value, When
from django.db.models.functions import Cast
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

    # DEPRECATED — nothing currently writes to this field.
    # Either implement a nightly analytics rollup task (see FURTHER_OPTIMIZATIONS §7.1)
    # or remove this field and its migration in the next cleanup pass.
    breakdown = models.JSONField(
        null=True, blank=True,
        help_text=_("Cached breakdown by device/geo. Currently unpopulated — reserved for future rollup task.")
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
            # Single-column indexes so filter(playlist_type=...) or filter(language=...)
            # alone can use an index without needing the composite prefix.
            models.Index(fields=("playlist_type",), name="playlist_type_idx"),
            models.Index(fields=("language",), name="playlist_language_idx"),
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
        """Increment total_watch_seconds and recompute avg_watch_seconds in one UPDATE.

        Uses a CASE WHEN expression so the average is computed at the DB level —
        no refresh_from_db, no second UPDATE, no race window.
        """
        seconds = max(0, int(seconds or 0))
        new_total = F("total_watch_seconds") + seconds
        self.__class__.objects.filter(pk=self.pk).update(
            total_watch_seconds=new_total,
            avg_watch_seconds=Case(
                When(
                    starts__gt=0,
                    then=ExpressionWrapper(
                        Cast(new_total, FloatField()) / Cast(F("starts"), FloatField()),
                        output_field=FloatField(),
                    ),
                ),
                default=Value(0.0),
                output_field=FloatField(),
            ),
        )

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


# ═══════════════════════════════════════════════════════════════════════
# Session — A structured yoga/meditation/workout practice
# ═══════════════════════════════════════════════════════════════════════

class Session(models.Model):
    """A guided practice session (yoga, meditation, breathwork, etc.)."""

    class DifficultyChoice(models.TextChoices):
        BEGINNER = "beginner", _("Beginner")
        INTERMEDIATE = "intermediate", _("Intermediate")
        ADVANCED = "advanced", _("Advanced")
        ALL_LEVELS = "all_levels", _("All Levels")

    class SessionCategory(models.TextChoices):
        YOGA = "yoga", _("Yoga")
        MEDITATION = "meditation", _("Meditation")
        BREATHWORK = "breathwork", _("Breathwork")
        CARDIO = "cardio", _("Cardio")
        STRENGTH = "strength", _("Strength")
        FLEXIBILITY = "flexibility", _("Flexibility")
        RELAXATION = "relaxation", _("Relaxation")
        PRANAYAMA = "pranayama", _("Pranayama")

    title = models.CharField(_("Title"), max_length=255)
    subtitle = models.CharField(_("Subtitle"), max_length=255, blank=True, default="",
                                help_text=_("e.g. 'Yoga • Flexibility'"))
    description = models.TextField(_("Description"), blank=True, default="")
    category = models.CharField(_("Category"), max_length=30, choices=SessionCategory.choices)
    difficulty = models.CharField(_("Difficulty"), max_length=20,
                                  choices=DifficultyChoice.choices, default=DifficultyChoice.ALL_LEVELS)

    duration_minutes = models.PositiveIntegerField(_("Duration (minutes)"), default=15)
    calories_estimate = models.PositiveIntegerField(_("Estimated Calories"), default=0)

    icon_name = models.CharField(_("Icon Name"), max_length=100, blank=True, default="SelfImprovement",
                                 help_text=_("Material icon name for the Android app."))
    color_hex = models.CharField(_("Color Hex"), max_length=9, default="#4A7C59",
                                 help_text=_("Hex color for card UI."))

    thumbnail = models.ImageField(_("Thumbnail"), storage=ImageKitStorage(),
                                  upload_to="content/sessions/thumbnails",
                                  max_length=1000, null=True, blank=True)
    thumbnail_file_id = models.CharField(max_length=1000, null=True, blank=True, editable=False)

    benefits = models.JSONField(_("Benefits"), default=list, blank=True,
                                help_text=_('JSON array of strings, e.g. ["Improves flexibility"]'))
    instructions = models.JSONField(_("Instructions"), default=list, blank=True,
                                    help_text=_('JSON array of step strings.'))

    video = models.ForeignKey(Video, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="sessions",
                              help_text=_("Optional linked video for guided playback."))

    is_published = models.BooleanField(_("Published"), default=False, db_index=True)
    is_featured = models.BooleanField(_("Featured"), default=False, db_index=True)
    order = models.PositiveIntegerField(_("Display Order"), default=0, db_index=True)

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Session")
        verbose_name_plural = _("Sessions")
        ordering = ["order", "-created_at"]
        indexes = [
            models.Index(fields=["category", "is_published"]),
            models.Index(fields=["difficulty"]),
        ]

    def __str__(self):
        return self.title


# ═══════════════════════════════════════════════════════════════════════
# Recipe — Structured recipe with ingredients, steps, and nutrition
# ═══════════════════════════════════════════════════════════════════════

class Recipe(models.Model):
    """A nutritional recipe with structured ingredients, steps, and macros."""

    class MealType(models.TextChoices):
        BREAKFAST = "breakfast", _("Breakfast")
        LUNCH = "lunch", _("Lunch")
        DINNER = "dinner", _("Dinner")
        SNACK = "snack", _("Snack")
        BEVERAGE = "beverage", _("Beverage")
        DESSERT = "dessert", _("Dessert")

    class DietTag(models.TextChoices):
        VEGETARIAN = "vegetarian", _("Vegetarian")
        VEGAN = "vegan", _("Vegan")
        GLUTEN_FREE = "gluten_free", _("Gluten Free")
        KETO = "keto", _("Keto")
        PALEO = "paleo", _("Paleo")
        HIGH_PROTEIN = "high_protein", _("High Protein")
        LOW_CARB = "low_carb", _("Low Carb")
        AYURVEDIC = "ayurvedic", _("Ayurvedic")
        SATTVIC = "sattvic", _("Sattvic")

    title = models.CharField(_("Title"), max_length=255)
    description = models.TextField(_("Description"), blank=True, default="")
    meal_type = models.CharField(_("Meal Type"), max_length=20, choices=MealType.choices)
    diet_tag = models.CharField(_("Diet Tag"), max_length=20, choices=DietTag.choices,
                                null=True, blank=True)
    cuisine = models.CharField(_("Cuisine"), max_length=100, blank=True, default="Indian")

    prep_time_minutes = models.PositiveIntegerField(_("Prep Time (min)"), default=10)
    cook_time_minutes = models.PositiveIntegerField(_("Cook Time (min)"), default=15)
    servings = models.PositiveSmallIntegerField(_("Servings"), default=1)
    difficulty = models.CharField(_("Difficulty"), max_length=20,
                                  choices=Session.DifficultyChoice.choices,
                                  default=Session.DifficultyChoice.BEGINNER)

    calories = models.PositiveIntegerField(_("Calories (kcal)"), default=0)

    icon_name = models.CharField(_("Icon Name"), max_length=100, blank=True, default="Restaurant")
    color_hex = models.CharField(_("Color Hex"), max_length=9, default="#E07A5F")

    thumbnail = models.ImageField(_("Thumbnail"), storage=ImageKitStorage(),
                                  upload_to="content/recipes/thumbnails",
                                  max_length=1000, null=True, blank=True)
    thumbnail_file_id = models.CharField(max_length=1000, null=True, blank=True, editable=False)

    ingredients = models.JSONField(_("Ingredients"), default=list, blank=True,
                                   help_text=_('[{"item":"Oats","quantity":"1","unit":"cup"}, ...]'))
    steps = models.JSONField(_("Steps"), default=list, blank=True,
                             help_text=_('[{"order":1,"instruction":"Soak oats..."}, ...]'))
    nutrition_facts = models.JSONField(_("Nutrition Facts"), default=dict, blank=True,
                                       help_text=_('{"protein":"12g","carbs":"45g","fat":"8g",...}'))
    tags = models.JSONField(_("Tags"), default=list, blank=True,
                            help_text=_('["high-fiber","quick","budget-friendly"]'))

    is_published = models.BooleanField(_("Published"), default=False, db_index=True)
    is_featured = models.BooleanField(_("Featured"), default=False, db_index=True)

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Recipe")
        verbose_name_plural = _("Recipes")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["meal_type", "is_published"]),
            models.Index(fields=["diet_tag"]),
        ]

    def __str__(self):
        return self.title

    @property
    def total_time_minutes(self):
        return (self.prep_time_minutes or 0) + (self.cook_time_minutes or 0)


# ═══════════════════════════════════════════════════════════════════════
# Deal — Local wellness market deals
# ═══════════════════════════════════════════════════════════════════════

class Deal(models.Model):
    """A local wellness/nutrition market deal or promotion."""

    item_name = models.CharField(_("Item Name"), max_length=255)
    emoji = models.CharField(_("Emoji"), max_length=10, default="🥬")
    category = models.CharField(_("Category"), max_length=100, blank=True, default="")
    description = models.TextField(_("Description"), blank=True, default="")

    price = models.CharField(_("Price"), max_length=50, help_text=_("e.g. ₹20/bunch"))
    original_price = models.CharField(_("Original Price"), max_length=50, blank=True, default="")
    location = models.CharField(_("Location"), max_length=255, blank=True, default="")
    available_at = models.CharField(_("Available At"), max_length=255, blank=True, default="",
                                    help_text=_("e.g. 'Mon–Sat, 7 AM – 1 PM'"))
    color_hex = models.CharField(_("Color Hex"), max_length=9, default="#FFB300")

    benefits = models.JSONField(_("Benefits"), default=list, blank=True)
    nutrition_facts = models.JSONField(_("Nutrition Facts"), default=dict, blank=True)

    is_active = models.BooleanField(_("Active"), default=True, db_index=True)
    expires_at = models.DateTimeField(_("Expires At"), null=True, blank=True)

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Deal")
        verbose_name_plural = _("Deals")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "-created_at"]),
            # Supports "active deals" filter (expires_at > NOW()) and cleanup tasks.
            models.Index(fields=["expires_at"], name="deal_expires_at_idx"),
        ]

    def __str__(self):
        return f"{self.emoji} {self.item_name}"


# ═══════════════════════════════════════════════════════════════════════
# DailyTip — Rotating tips, quotes, and affirmations
# ═══════════════════════════════════════════════════════════════════════

class DailyTip(models.Model):
    """A wellness tip, quote, or affirmation shown once daily."""

    class TipCategory(models.TextChoices):
        TIP = "tip", _("Tip")
        QUOTE = "quote", _("Quote")
        AFFIRMATION = "affirmation", _("Affirmation")
        AYURVEDA = "ayurveda", _("Ayurveda Wisdom")

    text = models.TextField(_("Text"))
    attribution = models.CharField(_("Attribution"), max_length=255, blank=True, default="",
                                   help_text=_("e.g. '— B.K.S. Iyengar'"))
    category = models.CharField(_("Category"), max_length=20, choices=TipCategory.choices,
                                default=TipCategory.TIP)

    scheduled_date = models.DateField(_("Scheduled Date"), null=True, blank=True, unique=True,
                                      help_text=_("If set, shown on this specific date. Otherwise random pool."))
    is_active = models.BooleanField(_("Active"), default=True, db_index=True)

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Daily Tip")
        verbose_name_plural = _("Daily Tips")
        ordering = ["-created_at"]

    def __str__(self):
        return self.text[:60]


# ═══════════════════════════════════════════════════════════════════════
# Category — Browsable wellness categories for search/explore
# ═══════════════════════════════════════════════════════════════════════

class Category(models.Model):
    """A browsable wellness category shown in the search/explore screen."""

    name = models.CharField(_("Name"), max_length=100, unique=True)
    icon_name = models.CharField(_("Icon Name"), max_length=100, default="SelfImprovement")
    color_hex = models.CharField(_("Color Hex"), max_length=9, default="#4A7C59")
    description = models.TextField(_("Description"), blank=True, default="")

    item_count = models.PositiveIntegerField(_("Item Count"), default=0,
                                             help_text=_("Cached count of items in this category."))

    is_active = models.BooleanField(_("Active"), default=True, db_index=True)
    order = models.PositiveIntegerField(_("Display Order"), default=0, db_index=True)

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


# ═══════════════════════════════════════════════════════════════════════
# UserDailyStat — Per-user, per-day health stats and streaks
# ═══════════════════════════════════════════════════════════════════════

class UserDailyStat(models.Model):
    """Daily health stats tracked per user — calories, water, heart rate, streaks."""

    user = models.ForeignKey("users.User", on_delete=models.CASCADE,
                             related_name="daily_stats")
    date = models.DateField(_("Date"))

    calories_consumed = models.PositiveIntegerField(_("Calories Consumed"), default=0)
    calories_burned = models.PositiveIntegerField(_("Calories Burned"), default=0)
    water_glasses = models.PositiveSmallIntegerField(_("Water Glasses"), default=0)
    water_goal = models.PositiveSmallIntegerField(_("Water Goal"), default=8)
    heart_rate_avg = models.PositiveSmallIntegerField(_("Avg Heart Rate (bpm)"), null=True, blank=True)
    steps = models.PositiveIntegerField(_("Steps"), default=0)
    sleep_hours = models.DecimalField(_("Sleep Hours"), max_digits=4, decimal_places=1,
                                      null=True, blank=True)
    streak_days = models.PositiveIntegerField(_("Streak Days"), default=0)

    practice_minutes = models.PositiveIntegerField(_("Practice Minutes"), default=0,
                                                    help_text=_("Total yoga/meditation/workout minutes."))

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("User Daily Stat")
        verbose_name_plural = _("User Daily Stats")
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["user", "date"], name="unique_user_daily_stat"),
        ]
        indexes = [models.Index(fields=["user", "-date"])]

    def __str__(self):
        return f"{self.user} — {self.date}"


# ═══════════════════════════════════════════════════════════════════════
# UserPlanItem — Per-user daily schedule items
# ═══════════════════════════════════════════════════════════════════════

class UserPlanItem(models.Model):
    """A single item in a user's daily wellness plan/timeline."""

    user = models.ForeignKey("users.User", on_delete=models.CASCADE,
                             related_name="plan_items")
    date = models.DateField(_("Date"))

    time = models.TimeField(_("Scheduled Time"))
    title = models.CharField(_("Title"), max_length=255)
    subtitle = models.CharField(_("Subtitle"), max_length=255, blank=True, default="")
    description = models.TextField(_("Description"), blank=True, default="")
    tips = models.JSONField(_("Tips"), default=list, blank=True)

    icon_name = models.CharField(_("Icon Name"), max_length=100, default="SelfImprovement")
    color_hex = models.CharField(_("Color Hex"), max_length=9, default="#4A7C59")

    is_done = models.BooleanField(_("Done"), default=False)
    order = models.PositiveIntegerField(_("Display Order"), default=0)

    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="plan_items",
                                help_text=_("Optional linked session for quick navigation."))

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("User Plan Item")
        verbose_name_plural = _("User Plan Items")
        ordering = ["date", "order", "time"]
        indexes = [
            # (user, date) is preserved as a prefix — all existing filter(user, date)
            # queries still use this index. is_done extends it to cover the natural
            # "show incomplete items for today" query without a second index.
            models.Index(fields=["user", "date", "is_done"], name="planitem_user_date_done_idx"),
            # Covers "all plan items for user X tied to session Y" analytics queries.
            models.Index(fields=["user", "session"], name="planitem_user_session_idx"),
        ]

    def __str__(self):
        return f"{self.time:%H:%M} — {self.title}"
# ═══════════════════════════════════════════════════════════════════════
# BreathworkExercise — UI configurations for breathwork
# ═══════════════════════════════════════════════════════════════════════

class BreathworkExercise(models.Model):
    title = models.CharField(_("Title"), max_length=100)
    pattern = models.CharField(_("Pattern"), max_length=100)
    duration = models.CharField(_("Duration"), max_length=50)
    color_hex = models.CharField(_("Color Hex"), max_length=9, default="#4A7C59")
    icon_name = models.CharField(_("Icon Name"), max_length=100, default="Air")
    
    order = models.PositiveIntegerField(_("Display Order"), default=0)
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Breathwork Exercise")
        verbose_name_plural = _("Breathwork Exercises")
        ordering = ["order"]

    def __str__(self):
        return self.title


# ═══════════════════════════════════════════════════════════════════════
# AmbientSound — UI configurations for ambient sounds
# ═══════════════════════════════════════════════════════════════════════

class AmbientSound(models.Model):
    name = models.CharField(_("Name"), max_length=100)
    emoji = models.CharField(_("Emoji"), max_length=10)
    color_hex = models.CharField(_("Color Hex"), max_length=9, default="#4A7C59")
    
    order = models.PositiveIntegerField(_("Display Order"), default=0)
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Ambient Sound")
        verbose_name_plural = _("Ambient Sounds")
        ordering = ["order"]

    def __str__(self):
        return self.name


# ═══════════════════════════════════════════════════════════════════════
# SearchConfig — Global configurations for search screen
# ═══════════════════════════════════════════════════════════════════════

class SearchConfig(models.Model):
    popular_searches = models.JSONField(_("Popular Searches"), default=list)
    filter_chips = models.JSONField(_("Filter Chips"), default=list)
    
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Search Configuration")
        verbose_name_plural = _("Search Configurations")

    def __str__(self):
        return "Search Config"
