from rest_framework import serializers
from .models import Playlist


class PlaylistReadSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for Playlist model (GET endpoints).
    Includes denormalized analytics counters + safe, human-friendly computed fields.
    """
    # File/image outputs
    thumbnail = serializers.SerializerMethodField()
    thumbnail_file_id = serializers.CharField(read_only=True)

    # Convert Decimals to floats for API consumers
    ctr = serializers.SerializerMethodField()
    completion_rate = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    computed_ctr = serializers.SerializerMethodField()
    computed_completion_rate = serializers.SerializerMethodField()

    class Meta:
        model = Playlist
        fields = [
            # Core
            "id",
            "title",
            "description",
            "playlist_type",
            "language",
            "created_at",
            "updated_at",

            # Artwork
            "thumbnail",
            "thumbnail_file_id",

            # Analytics (stored counters)
            "impressions",
            "clicks",
            "starts",
            "completes",
            "likes",
            "bookmarks",
            "shares",
            "total_watch_seconds",
            "avg_watch_seconds",
            "avg_progress_pct",
            "rating_count",
            "rating_sum",
            "last_impressed_at",
            "last_clicked_at",
            "last_started_at",
            "last_completed_at",
            "last_interaction_at",
            "breakdown",

            # Cached rollups (stored as DecimalFields in DB)
            "ctr",
            "completion_rate",

            # Read-time derived (for accuracy without waiting for nightly rollups)
            "average_rating",
            "computed_ctr",
            "computed_completion_rate",
        ]
        read_only_fields = fields

    # ---------- image/url helpers ----------
    def get_thumbnail(self, obj):
        """
        Return an absolute URL for the thumbnail if present; else None.
        """
        try:
            f = getattr(obj, "thumbnail", None)
            if not f or not getattr(f, "url", None):
                return None
            url = f.url
            request = self.context.get("request")
            # Build absolute URL if it's relative
            if request and not (url.startswith("http://") or url.startswith("https://")):
                return request.build_absolute_uri(url)
            return url
        except Exception:
            return None

    # ---------- method fields for numbers ----------
    def get_ctr(self, obj) -> float:
        try:
            return float(obj.ctr or 0)
        except Exception:
            return 0.0

    def get_completion_rate(self, obj) -> float:
        try:
            return float(obj.completion_rate or 0)
        except Exception:
            return 0.0

    def get_average_rating(self, obj) -> float:
        try:
            return float(getattr(obj, "average_rating", 0.0) or 0.0)
        except Exception:
            return 0.0

    def get_computed_ctr(self, obj) -> float:
        try:
            return float(getattr(obj, "computed_ctr", 0.0) or 0.0)
        except Exception:
            return 0.0

    def get_computed_completion_rate(self, obj) -> float:
        try:
            return float(getattr(obj, "computed_completion_rate", 0.0) or 0.0)
        except Exception:
            return 0.0


class PlaylistWriteSerializer(serializers.ModelSerializer):
    """
    Write serializer for creating/updating playlists.
    Accepts multipart image uploads for 'thumbnail'.
    """
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
    """
    Partial-update serializer for Playlist.
    All fields are optional; use with partial=True.
    Also allows replacing/removing thumbnail.
    """
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
        # Support clearing the existing thumbnail explicitly
        clear = validated_data.pop("clear_thumbnail", False)
        if clear:
            # Delete file from storage but keep instance intact
            f = getattr(instance, "thumbnail", None)
            if f:
                try:
                    f.delete(save=False)
                except Exception:
                    pass
            instance.thumbnail = None

        return super().update(instance, validated_data)
