"""
Content ViewSet — unified API for all content models.

Follows the action-map pattern established by the existing ContentViewSet:
per-action serializer, permission, authentication, and queryset maps.

All endpoints return the standardised ``api_response`` envelope.
"""

import hashlib
import json
import re
from datetime import date

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from utilities.response import api_response

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
    BreathworkExercise,
    AmbientSound,
    SearchConfig,
)
from .serializers import (
    CategoryReadSerializer,
    CategoryWriteSerializer,
    DailyTipReadSerializer,
    DailyTipWriteSerializer,
    DealReadSerializer,
    DealWriteSerializer,
    PlaylistPatchSerializer,
    PlaylistReadSerializer,
    PlaylistWriteSerializer,
    RecipeReadSerializer,
    RecipeWriteSerializer,
    SessionReadSerializer,
    SessionWriteSerializer,
    UserDailyStatSerializer,
    UserPlanItemReadSerializer,
    UserPlanItemWriteSerializer,
    VideoReadSerializer,
    BreathworkExerciseSerializer,
    AmbientSoundSerializer,
    SearchConfigSerializer,
)


ETAG_SPLIT_RE = re.compile(r"\s*,\s*")


class ContentViewSet(viewsets.GenericViewSet):
    """
    Content ViewSet with per-action maps for serializer, permissions,
    authentication, throttles, and queryset.
    """

    # ---- Defaults ----
    serializer_class = PlaylistReadSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = []
    throttle_classes = []

    # ---- Per-action serializer map ----
    serializer_action_classes = {
        # Playlists
        "playlist": PlaylistReadSerializer,
        "playlist_create": PlaylistWriteSerializer,
        "playlist_retrieve": PlaylistReadSerializer,
        "playlist_update": PlaylistPatchSerializer,
        "playlist_delete": PlaylistReadSerializer,
        "playlist_click": PlaylistReadSerializer,
        "playlist_rate": PlaylistReadSerializer,
        "playlist_ratings_reset": PlaylistReadSerializer,
        "playlist_impressions_reset": PlaylistReadSerializer,
        "featured_playlists": PlaylistReadSerializer,
        # Videos
        "videos": VideoReadSerializer,
        "video_retrieve": VideoReadSerializer,
        # Sessions
        "sessions": SessionReadSerializer,
        "session_retrieve": SessionReadSerializer,
        "session_create": SessionWriteSerializer,
        # Recipes
        "recipes": RecipeReadSerializer,
        "recipe_retrieve": RecipeReadSerializer,
        "recipe_create": RecipeWriteSerializer,
        # Deals
        "deals": DealReadSerializer,
        "deal_retrieve": DealReadSerializer,
        "deal_create": DealWriteSerializer,
        # Daily Tip
        "daily_tip": DailyTipReadSerializer,
        "daily_tip_create": DailyTipWriteSerializer,
        # Categories
        "categories": CategoryReadSerializer,
        "category_create": CategoryWriteSerializer,
        # User stats
        "stats_today": UserDailyStatSerializer,
        "stats_update": UserDailyStatSerializer,
        # User plan
        "plan_today": UserPlanItemReadSerializer,
        "plan_item_done": UserPlanItemWriteSerializer,
        "plan_create": UserPlanItemWriteSerializer,
        # New
        "stats_weekly": UserDailyStatSerializer,
        "breathwork": BreathworkExerciseSerializer,
        "ambient_sounds": AmbientSoundSerializer,
        "search_config": SearchConfigSerializer,
    }

    # ---- Per-action permission map ----
    permission_action_classes = {
        "playlist": [IsAuthenticated],
        "playlist_create": [IsAuthenticated],
        "playlist_retrieve": [IsAuthenticated],
        "playlist_update": [IsAuthenticated],
        "playlist_delete": [IsAuthenticated],
        "playlist_click": [IsAuthenticated],
        "playlist_rate": [IsAuthenticated],
        "playlist_ratings_reset": [IsAuthenticated],
        "playlist_impressions_reset": [IsAuthenticated],
        "featured_playlists": [IsAuthenticated],
        "videos": [IsAuthenticated],
        "video_retrieve": [IsAuthenticated],
        "sessions": [IsAuthenticated],
        "session_retrieve": [IsAuthenticated],
        "session_create": [IsAuthenticated],
        "recipes": [IsAuthenticated],
        "recipe_retrieve": [IsAuthenticated],
        "recipe_create": [IsAuthenticated],
        "deals": [IsAuthenticated],
        "deal_retrieve": [IsAuthenticated],
        "deal_create": [IsAuthenticated],
        "daily_tip": [IsAuthenticated],
        "daily_tip_create": [IsAuthenticated],
        "categories": [IsAuthenticated],
        "category_create": [IsAuthenticated],
        "stats_today": [IsAuthenticated],
        "stats_update": [IsAuthenticated],
        "plan_today": [IsAuthenticated],
        "plan_item_done": [IsAuthenticated],
        "plan_create": [IsAuthenticated],
        "stats_weekly": [IsAuthenticated],
        "breathwork": [IsAuthenticated],
        "ambient_sounds": [IsAuthenticated],
        "search_config": [IsAuthenticated],
    }

    # ---- Per-action authentication map ----
    authentication_action_classes = {k: [JWTAuthentication] for k in permission_action_classes}

    # ---- Per-action throttle map ----
    throttle_action_classes = {k: [] for k in permission_action_classes}

    # ---- Per-action queryset map ----
    queryset_action_classes = {
        "playlist": lambda self, r: Playlist.objects.all().order_by("-updated_at"),
        "playlist_retrieve": lambda self, r: Playlist.objects.all(),
        "playlist_update": lambda self, r: Playlist.objects.all(),
        "playlist_delete": lambda self, r: Playlist.objects.all(),
        "playlist_click": lambda self, r: Playlist.objects.all(),
        "playlist_rate": lambda self, r: Playlist.objects.all(),
        "playlist_ratings_reset": lambda self, r: Playlist.objects.all(),
        "playlist_impressions_reset": lambda self, r: Playlist.objects.all(),
        "videos": lambda self, r: Video.objects.filter(is_published=True).order_by("-created_at"),
        "video_retrieve": lambda self, r: Video.objects.filter(is_published=True),
        "sessions": lambda self, r: Session.objects.filter(is_published=True).order_by("order", "-created_at"),
        "session_retrieve": lambda self, r: Session.objects.filter(is_published=True),
        "recipes": lambda self, r: Recipe.objects.filter(is_published=True).order_by("-created_at"),
        "recipe_retrieve": lambda self, r: Recipe.objects.filter(is_published=True),
        "deals": lambda self, r: Deal.objects.filter(is_active=True).order_by("-created_at"),
        "deal_retrieve": lambda self, r: Deal.objects.filter(is_active=True),
        "categories": lambda self, r: Category.objects.filter(is_active=True).order_by("order", "name"),
        "plan_today": lambda self, r: UserPlanItem.objects.filter(
            user=r.user, date=date.today()
        ).order_by("order", "time"),
        "stats_weekly": lambda self, r: UserDailyStat.objects.filter(
            user=r.user
        ).order_by("-date")[:7],
        "breathwork": lambda self, r: BreathworkExercise.objects.filter(is_active=True).order_by("order"),
        "ambient_sounds": lambda self, r: AmbientSound.objects.filter(is_active=True).order_by("order"),
        "search_config": lambda self, r: SearchConfig.objects.filter(is_active=True),
    }

    # ── Map helpers ─────────────────────────────────────────────────

    def initialize_request(self, request, *args, **kwargs):
        if not hasattr(self, "action"):
            action_map = getattr(self, "action_map", None)
            if action_map:
                self.action = action_map.get(request.method.lower())
        return super().initialize_request(request, *args, **kwargs)

    def get_serializer_class(self):
        action = getattr(self, "action", None)
        return self.serializer_action_classes.get(action, self.serializer_class)

    def get_permissions(self):
        action = getattr(self, "action", None)
        classes = self.permission_action_classes.get(action, self.permission_classes)
        return [cls() for cls in classes]

    def get_authenticators(self):
        action = getattr(self, "action", None)
        classes = self.authentication_action_classes.get(action, self.authentication_classes)
        return [cls() for cls in classes]

    def get_throttles(self):
        action = getattr(self, "action", None)
        classes = self.throttle_action_classes.get(action, self.throttle_classes)
        return [cls() for cls in classes]

    def get_queryset(self):
        action = getattr(self, "action", None)
        builder = self.queryset_action_classes.get(action)
        if builder:
            return builder(self, self.request)
        return Playlist.objects.none()

    # ════════════════════════════════════════════════════════════════
    # PLAYLIST ENDPOINTS (existing, preserved as-is)
    # ════════════════════════════════════════════════════════════════

    @action(detail=False, methods=["get"], url_path="playlist", url_name="playlist")
    def playlist(self, request, *args, **kwargs):
        qs = self.get_queryset()
        ser = self.get_serializer(qs, many=True, context={"request": request})
        return api_response(request, data={"items": ser.data, "count": qs.count()},
                            status_code=status.HTTP_200_OK, message="Playlists fetched successfully")

    @action(detail=False, methods=["post"], url_path="playlist-create", url_name="playlist_create")
    def playlist_create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        read_ser = PlaylistReadSerializer(obj, context={"request": request})
        return api_response(request, data=read_ser.data,
                            status_code=status.HTTP_201_CREATED, message="Playlist created successfully")

    @action(detail=False, methods=["get"], url_path=r"playlist/(?P<pk>\d+)", url_name="playlist_retrieve")
    def playlist_retrieve(self, request, pk=None, *args, **kwargs):
        obj = self.get_queryset().filter(pk=pk).first()
        if not obj:
            return api_response(request, status_code=status.HTTP_404_NOT_FOUND,
                                errors={"detail": "Playlist not found"})
        obj.inc_impression(when=timezone.now())
        obj.refresh_from_db(fields=["impressions", "last_impressed_at"])
        ser = self.get_serializer(obj, context={"request": request})
        return api_response(request, data=ser.data, status_code=status.HTTP_200_OK,
                            message="Playlist fetched successfully")

    @action(detail=False, methods=["delete"], url_path=r"playlist_delete/(?P<pk>\d+)", url_name="playlist_delete")
    def playlist_delete(self, request, pk=None, *args, **kwargs):
        obj = self.get_queryset().filter(pk=pk).first()
        if not obj:
            return api_response(request, status_code=status.HTTP_404_NOT_FOUND,
                                errors={"detail": "Playlist not found"})
        obj.delete()
        return api_response(request, status_code=status.HTTP_204_NO_CONTENT,
                            message="Playlist deleted successfully")

    @action(detail=False, methods=["post"], url_path=r"playlist/(?P<pk>\d+)/click", url_name="playlist_click")
    def playlist_click(self, request, pk=None, *args, **kwargs):
        obj = self.get_queryset().filter(pk=pk).first()
        if not obj:
            return api_response(request, status_code=status.HTTP_404_NOT_FOUND,
                                errors={"detail": "Playlist not found"})
        obj.inc_click(when=timezone.now())
        obj.refresh_from_db(fields=["clicks", "last_clicked_at"])
        return api_response(request, data={"id": obj.pk, "clicks": obj.clicks,
                            "last_clicked_at": obj.last_clicked_at},
                            status_code=status.HTTP_200_OK, message="Click recorded successfully")

    @action(detail=False, methods=["post"], url_path=r"playlist/(?P<pk>\d+)/rate", url_name="playlist_rate")
    def playlist_rate(self, request, pk=None, *args, **kwargs):
        obj = self.get_queryset().filter(pk=pk).first()
        if not obj:
            return api_response(request, status_code=status.HTTP_404_NOT_FOUND,
                                errors={"detail": "Playlist not found"})
        try:
            stars = int(request.data.get("stars"))
        except (TypeError, ValueError):
            return api_response(request, status_code=status.HTTP_400_BAD_REQUEST,
                                errors={"stars": "Stars must be an integer between 1 and 5"})
        if stars < 1 or stars > 5:
            return api_response(request, status_code=status.HTTP_400_BAD_REQUEST,
                                errors={"stars": "Stars must be between 1 and 5 inclusive"})
        obj.add_rating(stars)
        obj.refresh_from_db(fields=["rating_count", "rating_sum"])
        return api_response(request, status_code=status.HTTP_200_OK, message="Rating recorded",
                            data={"id": obj.pk, "stars": stars, "rating_count": obj.rating_count,
                                  "rating_sum": obj.rating_sum, "average_rating": obj.average_rating})

    @action(detail=False, methods=["get"], url_path=r"playlist/(?P<pk>\d+)/ratings/reset",
            url_name="playlist_ratings_reset")
    def playlist_ratings_reset(self, request, pk=None, *args, **kwargs):
        qs = self.get_queryset()
        if not qs.filter(pk=pk).exists():
            return api_response(request, status_code=status.HTTP_404_NOT_FOUND,
                                errors={"detail": "Playlist not found"})
        qs.filter(pk=pk).update(rating_count=0, rating_sum=0)
        obj = qs.only("id", "rating_count", "rating_sum").get(pk=pk)
        return api_response(request, status_code=status.HTTP_200_OK, message="Ratings reset",
                            data={"id": obj.pk, "rating_count": obj.rating_count,
                                  "rating_sum": obj.rating_sum, "average_rating": 0.0})

    @action(detail=False, methods=["get"], url_path=r"playlist/(?P<pk>\d+)/impressions/reset",
            url_name="playlist_impressions_reset")
    def playlist_impressions_reset(self, request, pk=None, *args, **kwargs):
        qs = self.get_queryset()
        obj = qs.filter(pk=pk).first()
        if not obj:
            return api_response(request, status_code=status.HTTP_404_NOT_FOUND,
                                errors={"detail": "Playlist not found"})
        qs.filter(pk=pk).update(impressions=0, last_impressed_at=None, ctr=0)
        obj.refresh_from_db(fields=["impressions", "last_impressed_at", "ctr"])
        return api_response(request, status_code=status.HTTP_200_OK,
                            message="Impressions reset successfully",
                            data={"id": obj.pk, "impressions": obj.impressions,
                                  "last_impressed_at": obj.last_impressed_at, "ctr": float(obj.ctr)})

    @action(detail=False, methods=["get"], url_path=r"playlist/featured", url_name="featured_playlists")
    def featured_playlists(self, request, *args, **kwargs):
        blob = cache.get(settings.FEATURED_KEY)
        if not blob:
            resp = api_response(request, data={"items": []},
                                status_code=status.HTTP_404_NOT_FOUND,
                                message="Featured playlists not present in cache")
            resp["Cache-Control"] = "public, max-age=60, stale-while-revalidate=60"
            return resp

        payload = {"data": blob}
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        etag_value = hashlib.md5(raw).hexdigest()
        etag_quoted = f'W/"{etag_value}"'

        inm = request.headers.get("If-None-Match", "")
        candidates = [t.strip() for t in ETAG_SPLIT_RE.split(inm) if t.strip()]
        candidates_normalized = {t.strip('W/w"') for t in candidates}

        if etag_value in candidates_normalized or etag_quoted in candidates:
            resp = api_response(request, data=None,
                                status_code=status.HTTP_304_NOT_MODIFIED, message="Not Modified")
            resp["ETag"] = etag_quoted
            resp["Cache-Control"] = "public, max-age=300, stale-while-revalidate=120"
            return resp

        resp = api_response(request, data=payload["data"],
                            status_code=status.HTTP_200_OK,
                            message="Featured playlists fetched successfully")
        resp["ETag"] = etag_quoted
        resp["Cache-Control"] = "public, max-age=300, stale-while-revalidate=120"
        return resp

    # ════════════════════════════════════════════════════════════════
    # VIDEO ENDPOINTS
    # ════════════════════════════════════════════════════════════════

    @action(detail=False, methods=["get"], url_path="videos", url_name="videos")
    def videos(self, request, *args, **kwargs):
        qs = self.get_queryset()
        genre = request.query_params.get("genre")
        lang = request.query_params.get("language")
        if genre:
            qs = qs.filter(content_genre__iexact=genre)
        if lang:
            qs = qs.filter(language__iexact=lang)
        ser = self.get_serializer(qs, many=True, context={"request": request})
        return api_response(request, data={"items": ser.data, "count": len(ser.data)},
                            status_code=status.HTTP_200_OK, message="Videos fetched successfully")

    @action(detail=False, methods=["get"], url_path=r"videos/(?P<pk>\d+)", url_name="video_retrieve")
    def video_retrieve(self, request, pk=None, *args, **kwargs):
        obj = self.get_queryset().filter(pk=pk).first()
        if not obj:
            return api_response(request, status_code=status.HTTP_404_NOT_FOUND,
                                errors={"detail": "Video not found"})
        ser = self.get_serializer(obj, context={"request": request})
        return api_response(request, data=ser.data, status_code=status.HTTP_200_OK,
                            message="Video fetched successfully")

    # ════════════════════════════════════════════════════════════════
    # SESSION ENDPOINTS
    # ════════════════════════════════════════════════════════════════

    @action(detail=False, methods=["get"], url_path="sessions", url_name="sessions")
    def sessions(self, request, *args, **kwargs):
        qs = self.get_queryset()
        cat = request.query_params.get("category")
        diff = request.query_params.get("difficulty")
        if cat:
            qs = qs.filter(category__iexact=cat)
        if diff:
            qs = qs.filter(difficulty__iexact=diff)
        ser = self.get_serializer(qs, many=True, context={"request": request})
        return api_response(request, data={"items": ser.data, "count": len(ser.data)},
                            status_code=status.HTTP_200_OK, message="Sessions fetched successfully")

    @action(detail=False, methods=["get"], url_path=r"sessions/(?P<pk>\d+)", url_name="session_retrieve")
    def session_retrieve(self, request, pk=None, *args, **kwargs):
        obj = self.get_queryset().filter(pk=pk).first()
        if not obj:
            return api_response(request, status_code=status.HTTP_404_NOT_FOUND,
                                errors={"detail": "Session not found"})
        ser = self.get_serializer(obj, context={"request": request})
        return api_response(request, data=ser.data, status_code=status.HTTP_200_OK,
                            message="Session fetched successfully")

    # ════════════════════════════════════════════════════════════════
    # RECIPE ENDPOINTS
    # ════════════════════════════════════════════════════════════════

    @action(detail=False, methods=["get"], url_path="recipes", url_name="recipes")
    def recipes(self, request, *args, **kwargs):
        qs = self.get_queryset()
        meal = request.query_params.get("meal_type")
        diet = request.query_params.get("diet_tag")
        q = request.query_params.get("q")
        if meal:
            qs = qs.filter(meal_type__iexact=meal)
        if diet:
            qs = qs.filter(diet_tag__iexact=diet)
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
        ser = self.get_serializer(qs, many=True, context={"request": request})
        return api_response(request, data={"items": ser.data, "count": len(ser.data)},
                            status_code=status.HTTP_200_OK, message="Recipes fetched successfully")

    @action(detail=False, methods=["get"], url_path=r"recipes/(?P<pk>\d+)", url_name="recipe_retrieve")
    def recipe_retrieve(self, request, pk=None, *args, **kwargs):
        obj = self.get_queryset().filter(pk=pk).first()
        if not obj:
            return api_response(request, status_code=status.HTTP_404_NOT_FOUND,
                                errors={"detail": "Recipe not found"})
        ser = self.get_serializer(obj, context={"request": request})
        return api_response(request, data=ser.data, status_code=status.HTTP_200_OK,
                            message="Recipe fetched successfully")

    # ════════════════════════════════════════════════════════════════
    # DEAL ENDPOINTS
    # ════════════════════════════════════════════════════════════════

    @action(detail=False, methods=["get"], url_path="deals", url_name="deals")
    def deals(self, request, *args, **kwargs):
        qs = self.get_queryset()
        cat = request.query_params.get("category")
        if cat:
            qs = qs.filter(category__icontains=cat)
        ser = self.get_serializer(qs, many=True, context={"request": request})
        return api_response(request, data={"items": ser.data, "count": len(ser.data)},
                            status_code=status.HTTP_200_OK, message="Deals fetched successfully")

    @action(detail=False, methods=["get"], url_path=r"deals/(?P<pk>\d+)", url_name="deal_retrieve")
    def deal_retrieve(self, request, pk=None, *args, **kwargs):
        obj = self.get_queryset().filter(pk=pk).first()
        if not obj:
            return api_response(request, status_code=status.HTTP_404_NOT_FOUND,
                                errors={"detail": "Deal not found"})
        ser = self.get_serializer(obj, context={"request": request})
        return api_response(request, data=ser.data, status_code=status.HTTP_200_OK,
                            message="Deal fetched successfully")

    # ════════════════════════════════════════════════════════════════
    # DAILY TIP ENDPOINT
    # ════════════════════════════════════════════════════════════════

    @action(detail=False, methods=["get"], url_path="daily-tip", url_name="daily_tip")
    def daily_tip(self, request, *args, **kwargs):
        """Return today's tip: scheduled for today, or random from active pool."""
        today = date.today()
        tip = DailyTip.objects.filter(scheduled_date=today, is_active=True).first()
        if not tip:
            tip = DailyTip.objects.filter(is_active=True, scheduled_date__isnull=True).order_by("?").first()
        if not tip:
            return api_response(request, data=None, status_code=status.HTTP_200_OK,
                                message="No tips available")
        ser = self.get_serializer(tip, context={"request": request})
        return api_response(request, data=ser.data, status_code=status.HTTP_200_OK,
                            message="Daily tip fetched successfully")

    # ════════════════════════════════════════════════════════════════
    # CATEGORY ENDPOINTS
    # ════════════════════════════════════════════════════════════════

    @action(detail=False, methods=["get"], url_path="categories", url_name="categories")
    def categories(self, request, *args, **kwargs):
        qs = self.get_queryset()
        ser = self.get_serializer(qs, many=True, context={"request": request})
        return api_response(request, data={"items": ser.data, "count": len(ser.data)},
                            status_code=status.HTTP_200_OK, message="Categories fetched successfully")

    # ════════════════════════════════════════════════════════════════
    # USER DAILY STATS ENDPOINTS
    # ════════════════════════════════════════════════════════════════

    @action(detail=False, methods=["get"], url_path="stats/today", url_name="stats_today")
    def stats_today(self, request, *args, **kwargs):
        """Get or create today's stats for the authenticated user."""
        stat, _ = UserDailyStat.objects.get_or_create(
            user=request.user, date=date.today(),
        )
        ser = self.get_serializer(stat, context={"request": request})
        return api_response(request, data=ser.data, status_code=status.HTTP_200_OK,
                            message="Today's stats fetched successfully")

    @action(detail=False, methods=["patch"], url_path="stats/update", url_name="stats_update")
    def stats_update(self, request, *args, **kwargs):
        """Update today's stats (partial update)."""
        stat, _ = UserDailyStat.objects.get_or_create(
            user=request.user, date=date.today(),
        )
        ser = self.get_serializer(stat, data=request.data, partial=True,
                                  context={"request": request})
        ser.is_valid(raise_exception=True)
        ser.save()
        return api_response(request, data=ser.data, status_code=status.HTTP_200_OK,
                            message="Stats updated successfully")

    # ════════════════════════════════════════════════════════════════
    # USER PLAN ENDPOINTS
    # ════════════════════════════════════════════════════════════════

    @action(detail=False, methods=["get"], url_path="plan/today", url_name="plan_today")
    def plan_today(self, request, *args, **kwargs):
        """Get today's plan items for the authenticated user."""
        qs = self.get_queryset()
        ser = UserPlanItemReadSerializer(qs, many=True, context={"request": request})
        return api_response(request, data={"items": ser.data, "count": len(ser.data)},
                            status_code=status.HTTP_200_OK,
                            message="Today's plan fetched successfully")

    @action(detail=False, methods=["patch"], url_path=r"plan/(?P<pk>\d+)/done",
            url_name="plan_item_done")
    def plan_item_done(self, request, pk=None, *args, **kwargs):
        """Toggle a plan item's done status."""
        item = UserPlanItem.objects.filter(pk=pk, user=request.user).first()
        if not item:
            return api_response(request, status_code=status.HTTP_404_NOT_FOUND,
                                errors={"detail": "Plan item not found"})
        item.is_done = not item.is_done
        item.save(update_fields=["is_done", "updated_at"])
        ser = UserPlanItemReadSerializer(item, context={"request": request})
        return api_response(request, data=ser.data, status_code=status.HTTP_200_OK,
                            message="Plan item updated")

    @action(detail=False, methods=["post"], url_path="plan/create", url_name="plan_create")
    def plan_create(self, request, *args, **kwargs):
        """Create a new plan item for the authenticated user."""
        ser = self.get_serializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        ser.save(user=request.user)
        return api_response(request, data=ser.data, status_code=status.HTTP_201_CREATED,
                            message="Plan item created")

    # ════════════════════════════════════════════════════════════════
    # NEW ENDPOINTS FOR UI DYNAMIC DATA
    # ════════════════════════════════════════════════════════════════

    @action(detail=False, methods=["get"], url_path="stats/weekly", url_name="stats_weekly")
    def stats_weekly(self, request, *args, **kwargs):
        """Get stats for the last 7 days for the authenticated user."""
        qs = self.get_queryset()
        ser = self.get_serializer(qs, many=True, context={"request": request})
        return api_response(request, data={"items": ser.data, "count": len(ser.data)},
                            status_code=status.HTTP_200_OK,
                            message="Weekly stats fetched successfully")

    @action(detail=False, methods=["get"], url_path="breathwork", url_name="breathwork")
    def breathwork(self, request, *args, **kwargs):
        """Get list of breathwork exercises."""
        qs = self.get_queryset()
        ser = self.get_serializer(qs, many=True, context={"request": request})
        return api_response(request, data={"items": ser.data, "count": len(ser.data)},
                            status_code=status.HTTP_200_OK,
                            message="Breathwork exercises fetched successfully")

    @action(detail=False, methods=["get"], url_path="ambient-sounds", url_name="ambient_sounds")
    def ambient_sounds(self, request, *args, **kwargs):
        """Get list of ambient sounds."""
        qs = self.get_queryset()
        ser = self.get_serializer(qs, many=True, context={"request": request})
        return api_response(request, data={"items": ser.data, "count": len(ser.data)},
                            status_code=status.HTTP_200_OK,
                            message="Ambient sounds fetched successfully")

    @action(detail=False, methods=["get"], url_path="search-config", url_name="search_config")
    def search_config(self, request, *args, **kwargs):
        """Get global search configuration."""
        qs = self.get_queryset()
        config = qs.first()
        if not config:
            # Return some defaults if not found in the database
            data = {
                "popular_searches": [
                    "Pranayama techniques", "High protein Indian meals",
                    "Morning yoga routine", "Calorie deficit recipes"
                ],
                "filter_chips": ["All", "Yoga", "Nutrition", "Meditation", "Recipes", "Fitness", "Sleep"]
            }
        else:
            ser = self.get_serializer(config, context={"request": request})
            data = ser.data
            
        return api_response(request, data=data,
                            status_code=status.HTTP_200_OK,
                            message="Search configuration fetched successfully")