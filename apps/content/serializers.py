"""
Serializers for the Content app.

Each model has a Read serializer (GET) and optionally a Write serializer
(POST/PATCH).  Read serializers expose computed fields and safe URL
resolution.  Write serializers accept only the fields an admin or client
should be able to set.
"""

from django.utils import timezone
from rest_framework import serializers

from .models import (
    Category,
    DailyTip,
    Deal,
    Playlist,
    Recipe,
    Session,
    UserDailyStat,
    UserPlanItem,
    Video,
)


# ═══════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════

def _thumbnail_url(obj, context):
    """Return an absolute URL for a thumbnail ImageField or None."""
    try:
        f = getattr(obj, "thumbnail", None)
        if not f or not getattr(f, "url", None):
            return None
        url = f.url
        request = context.get("request")
        if request and not url.startswith(("http://", "https://")):
            return request.build_absolute_uri(url)
        return url
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════
# Playlist
# ═══════════════════════════════════════════════════════════════════════

class PlaylistReadSerializer(serializers.ModelSerializer):
    thumbnail = serializers.SerializerMethodField()
    thumbnail_file_id = serializers.CharField(read_only=True)
    ctr = serializers.SerializerMethodField()
    completion_rate = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    computed_ctr = serializers.SerializerMethodField()
    computed_completion_rate = serializers.SerializerMethodField()

    class Meta:
        model = Playlist
        fields = [
            "id", "title", "description", "playlist_type", "language",
            "created_at", "updated_at",
            "thumbnail", "thumbnail_file_id",
            "impressions", "clicks", "starts", "completes",
            "likes", "bookmarks", "shares",
            "total_watch_seconds", "avg_watch_seconds", "avg_progress_pct",
            "rating_count", "rating_sum",
            "last_impressed_at", "last_clicked_at",
            "last_started_at", "last_completed_at", "last_interaction_at",
            "breakdown",
            "ctr", "completion_rate",
            "average_rating", "computed_ctr", "computed_completion_rate",
        ]
        read_only_fields = fields

    def get_thumbnail(self, obj):
        return _thumbnail_url(obj, self.context)

    def get_ctr(self, obj):
        return float(obj.ctr or 0)

    def get_completion_rate(self, obj):
        return float(obj.completion_rate or 0)

    def get_average_rating(self, obj):
        return float(getattr(obj, "average_rating", 0.0) or 0.0)

    def get_computed_ctr(self, obj):
        return float(getattr(obj, "computed_ctr", 0.0) or 0.0)

    def get_computed_completion_rate(self, obj):
        return float(getattr(obj, "computed_completion_rate", 0.0) or 0.0)


class PlaylistWriteSerializer(serializers.ModelSerializer):
    thumbnail = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Playlist
        fields = ["title", "description", "playlist_type", "language", "thumbnail"]
        extra_kwargs = {
            "title": {"required": False, "allow_null": True, "allow_blank": True},
            "description": {"required": False, "allow_null": True, "allow_blank": True},
            "playlist_type": {"required": False, "allow_null": True},
            "language": {"required": False, "allow_null": True},
        }


class PlaylistPatchSerializer(serializers.ModelSerializer):
    thumbnail = serializers.ImageField(required=False, allow_null=True)
    clear_thumbnail = serializers.BooleanField(
        required=False, default=False, help_text="If true, remove existing thumbnail."
    )

    class Meta:
        model = Playlist
        fields = ["title", "description", "playlist_type", "language", "thumbnail", "clear_thumbnail"]
        extra_kwargs = {
            "title": {"required": False, "allow_null": True, "allow_blank": True},
            "description": {"required": False, "allow_null": True, "allow_blank": True},
            "playlist_type": {"required": False, "allow_null": True},
            "language": {"required": False, "allow_null": True},
            "thumbnail": {"required": False, "allow_null": True},
        }

    def update(self, instance, validated_data):
        clear = validated_data.pop("clear_thumbnail", False)
        if clear:
            f = getattr(instance, "thumbnail", None)
            if f:
                try:
                    f.delete(save=False)
                except Exception:
                    pass
            instance.thumbnail = None
        return super().update(instance, validated_data)


# ═══════════════════════════════════════════════════════════════════════
# Video
# ═══════════════════════════════════════════════════════════════════════

class VideoReadSerializer(serializers.ModelSerializer):
    thumbnail = serializers.SerializerMethodField()
    playlists = serializers.PrimaryKeyRelatedField(
        source="playlist", many=True, read_only=True,
    )
    duration_display = serializers.SerializerMethodField()

    class Meta:
        model = Video
        fields = [
            "id", "title", "description", "instructor",
            "content_genre", "content_type", "language", "difficulty_level",
            "thumbnail", "thumbnail_file_id",
            "video", "video_file_id",
            "duration_seconds", "duration_display", "hls_manifest_url",
            "is_published", "is_featured", "requires_subscription", "zen_mode_only",
            "playlists",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_thumbnail(self, obj):
        return _thumbnail_url(obj, self.context)

    def get_duration_display(self, obj):
        """Human-friendly duration, e.g. '12 min' or '1h 5 min'."""
        secs = obj.duration_seconds or 0
        if secs < 60:
            return f"{secs}s"
        mins = secs // 60
        if mins < 60:
            return f"{mins} min"
        return f"{mins // 60}h {mins % 60} min"


# ═══════════════════════════════════════════════════════════════════════
# Session
# ═══════════════════════════════════════════════════════════════════════

class SessionReadSerializer(serializers.ModelSerializer):
    thumbnail = serializers.SerializerMethodField()
    duration_display = serializers.SerializerMethodField()
    calories_display = serializers.SerializerMethodField()

    class Meta:
        model = Session
        fields = [
            "id", "title", "subtitle", "description",
            "category", "difficulty",
            "duration_minutes", "duration_display",
            "calories_estimate", "calories_display",
            "icon_name", "color_hex",
            "thumbnail", "thumbnail_file_id",
            "benefits", "instructions",
            "video",
            "is_published", "is_featured", "order",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_thumbnail(self, obj):
        return _thumbnail_url(obj, self.context)

    def get_duration_display(self, obj):
        return f"{obj.duration_minutes} min"

    def get_calories_display(self, obj):
        return f"{obj.calories_estimate} kcal"


class SessionWriteSerializer(serializers.ModelSerializer):
    thumbnail = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Session
        fields = [
            "title", "subtitle", "description", "category", "difficulty",
            "duration_minutes", "calories_estimate",
            "icon_name", "color_hex", "thumbnail",
            "benefits", "instructions", "video",
            "is_published", "is_featured", "order",
        ]


# ═══════════════════════════════════════════════════════════════════════
# Recipe
# ═══════════════════════════════════════════════════════════════════════

class RecipeReadSerializer(serializers.ModelSerializer):
    thumbnail = serializers.SerializerMethodField()
    total_time_minutes = serializers.IntegerField(read_only=True)
    total_time_display = serializers.SerializerMethodField()
    calories_display = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = [
            "id", "title", "description",
            "meal_type", "diet_tag", "cuisine", "difficulty",
            "prep_time_minutes", "cook_time_minutes",
            "total_time_minutes", "total_time_display",
            "servings", "calories", "calories_display",
            "icon_name", "color_hex",
            "thumbnail", "thumbnail_file_id",
            "ingredients", "steps", "nutrition_facts", "tags",
            "is_published", "is_featured",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_thumbnail(self, obj):
        return _thumbnail_url(obj, self.context)

    def get_total_time_display(self, obj):
        t = obj.total_time_minutes
        return f"{t} min" if t < 60 else f"{t // 60}h {t % 60} min"

    def get_calories_display(self, obj):
        return f"{obj.calories} kcal"


class RecipeWriteSerializer(serializers.ModelSerializer):
    thumbnail = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Recipe
        fields = [
            "title", "description", "meal_type", "diet_tag",
            "cuisine", "difficulty",
            "prep_time_minutes", "cook_time_minutes", "servings",
            "calories", "icon_name", "color_hex", "thumbnail",
            "ingredients", "steps", "nutrition_facts", "tags",
            "is_published", "is_featured",
        ]


# ═══════════════════════════════════════════════════════════════════════
# Deal
# ═══════════════════════════════════════════════════════════════════════

class DealReadSerializer(serializers.ModelSerializer):
    is_expired = serializers.SerializerMethodField()
    discount_text = serializers.SerializerMethodField()

    class Meta:
        model = Deal
        fields = [
            "id", "item_name", "emoji", "category", "description",
            "price", "original_price", "discount_text",
            "location", "available_at", "color_hex",
            "benefits", "nutrition_facts",
            "is_active", "is_expired", "expires_at",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_is_expired(self, obj):
        if obj.expires_at:
            return obj.expires_at < timezone.now()
        return False

    def get_discount_text(self, obj):
        """Try to compute a discount percentage from price strings."""
        if not obj.original_price or not obj.price:
            return ""
        try:
            import re
            orig = float(re.search(r"[\d.]+", obj.original_price).group())
            curr = float(re.search(r"[\d.]+", obj.price).group())
            if orig > 0:
                pct = int(((orig - curr) / orig) * 100)
                return f"{pct}% off"
        except Exception:
            pass
        return ""


class DealWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deal
        fields = [
            "item_name", "emoji", "category", "description",
            "price", "original_price", "location", "available_at",
            "color_hex", "benefits", "nutrition_facts",
            "is_active", "expires_at",
        ]


# ═══════════════════════════════════════════════════════════════════════
# DailyTip
# ═══════════════════════════════════════════════════════════════════════

class DailyTipReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyTip
        fields = [
            "id", "text", "attribution", "category",
            "scheduled_date", "is_active", "created_at",
        ]
        read_only_fields = fields


class DailyTipWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyTip
        fields = ["text", "attribution", "category", "scheduled_date", "is_active"]


# ═══════════════════════════════════════════════════════════════════════
# Category
# ═══════════════════════════════════════════════════════════════════════

class CategoryReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            "id", "name", "icon_name", "color_hex", "description",
            "item_count", "is_active", "order",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class CategoryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            "name", "icon_name", "color_hex", "description",
            "item_count", "is_active", "order",
        ]


# ═══════════════════════════════════════════════════════════════════════
# UserDailyStat
# ═══════════════════════════════════════════════════════════════════════

class UserDailyStatSerializer(serializers.ModelSerializer):
    """Read/write serializer — users update their own stats."""

    water_progress = serializers.SerializerMethodField()

    class Meta:
        model = UserDailyStat
        fields = [
            "id", "date",
            "calories_consumed", "calories_burned",
            "water_glasses", "water_goal", "water_progress",
            "heart_rate_avg", "steps", "sleep_hours",
            "streak_days", "practice_minutes",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "water_progress"]

    def get_water_progress(self, obj):
        """e.g. '3/8'"""
        return f"{obj.water_glasses}/{obj.water_goal}"


# ═══════════════════════════════════════════════════════════════════════
# UserPlanItem
# ═══════════════════════════════════════════════════════════════════════

class UserPlanItemReadSerializer(serializers.ModelSerializer):
    time_display = serializers.SerializerMethodField()

    class Meta:
        model = UserPlanItem
        fields = [
            "id", "date", "time", "time_display",
            "title", "subtitle", "description", "tips",
            "icon_name", "color_hex",
            "is_done", "order", "session",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_time_display(self, obj):
        return f"{obj.time:%H:%M}"


class UserPlanItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPlanItem
        fields = [
            "date", "time", "title", "subtitle", "description",
            "tips", "icon_name", "color_hex",
            "is_done", "order", "session",
        ]
