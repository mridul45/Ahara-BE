from django.utils import timezone
from rest_framework import viewsets,status
from .models import (
    Playlist
)
from .serializers import (
    PlaylistReadSerializer,
    PlaylistWriteSerializer,
    PlaylistPatchSerializer,
)
from rest_framework.permissions import IsAuthenticated,AllowAny
from utilities.response import api_response
from rest_framework.decorators import action
from django.conf import settings
from django.core.cache import cache
import hashlib
import json
import re



ETAG_SPLIT_RE = re.compile(r'\s*,\s*')

# Create your views here.


class ContentViewSet(viewsets.GenericViewSet):
    """
    Content ViewSet with per-action maps for:
      - serializer
      - permissions
      - authentication
      - throttles
      - queryset (via callables so it can depend on request if needed)
    """
    # ---- Defaults ----
    serializer_class = PlaylistReadSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = []
    throttle_classes = []

    # ---- Per-action maps (your existing pattern) ----
    serializer_action_classes = {
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
        # "featured_playlists": PlaylistReadSerializer,
        # "recent_playlists": PlaylistReadSerializer,
    }
    permission_action_classes = {
        "playlist": [AllowAny],
        "playlist_create": [AllowAny],
        "playlist_retrieve": [AllowAny],
        "playlist_update": [AllowAny],
        "playlist_delete": [AllowAny],
        "playlist_click": [AllowAny],
        "playlist_rate": [AllowAny],
        "playlist_ratings_reset": [AllowAny],
        "playlist_impressions_reset": [AllowAny],
        "featured_playlists": [AllowAny],
        # "featured_playlists": [AllowAny],
        # "recent_playlists": [AllowAny],
    }
    authentication_action_classes = {
        "playlist": [],
        "playlist_create": [],
        "playlist_retrieve": [],
        "playlist_update": [],
        "playlist_delete": [],
        "playlist_click": [],
        "playlist_rate": [],
        "playlist_ratings_reset": [],
        "playlist_impressions_reset": [],
        "featured_playlists": [],
    }
    throttle_action_classes = {
        "playlist": [],
        "playlist_create": [],
        "playlist_retrieve": [],
        "playlist_update": [],
        "playlist_delete": [],
        "playlist_click": [],
        "playlist_rate": [],
        "playlist_ratings_reset": [],
        "playlist_impressions_reset": [],
        "featured_playlists": [],
        # "featured_playlists": [],
        # "recent_playlists": [],
    }

    # ---- NEW: Per-action queryset map (callables) ----
    # Each value is a function: (self, request) -> QuerySet
    queryset_action_classes = {
        "playlist": lambda self, request: Playlist.objects.all().order_by("-updated_at"),
        "playlist_retrieve": lambda self, request: Playlist.objects.all(),
        "playlist_update":   lambda self, request: Playlist.objects.all(),
        "playlist_delete":   lambda self, request: Playlist.objects.all(),
        "playlist_click":    lambda self, request: Playlist.objects.all(),
        "playlist_rate":     lambda self, request: Playlist.objects.all(),
        "playlist_ratings_reset": lambda self, request: Playlist.objects.all(),
        "playlist_impressions_reset": lambda self, request: Playlist.objects.all(),
        # Examples you can enable later:
        # "featured_playlists": lambda self, request: Playlist.objects.filter(is_featured=True).order_by("-updated_at"),
        # "recent_playlists": lambda self, request: Playlist.objects.filter(
        #     updated_at__gte=timezone.now() - timezone.timedelta(days=7)
        # ).order_by("-updated_at"),
    }

    # ---- Ensure self.action is set early (like your AuthViewSet) ----
    def initialize_request(self, request, *args, **kwargs):
        if not hasattr(self, "action"):
            action_map = getattr(self, "action_map", None)
            if action_map:
                self.action = action_map.get(request.method.lower())
        return super().initialize_request(request, *args, **kwargs)

    # ---- Map helpers ----
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

    # ---- Use the per-action queryset map ----
    def get_queryset(self):
        action = getattr(self, "action", None)
        builder = self.queryset_action_classes.get(action)
        if builder:
            return builder(self, self.request)
        # Fallback if an action forgets to define a queryset
        return Playlist.objects.none()

    # ---------------- Actions ----------------
    @action(detail=False, methods=["get"], url_path="playlist", url_name="playlist")
    def playlist(self, request, *args, **kwargs):
        """
        GET /content/playlist/
        Returns all playlists.
        """
        qs = self.get_queryset()
        ser = self.get_serializer(qs, many=True, context={"request": request})
        return api_response(
            request,
            data={"items": ser.data, "count": qs.count()},
            status_code=status.HTTP_200_OK,
            message="Playlists fetched successfully",
        )
    
    
    @action(detail=False, methods=["post"], url_path="playlist-create", url_name="playlist_create")
    def playlist_create(self, request, *args, **kwargs):
        """POST /content/playlist-create/ → create new playlist (auth required)."""
        ser = self.get_serializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        read_ser = PlaylistReadSerializer(obj, context={"request": request})
        return api_response(
            request,
            data=read_ser.data,
            status_code=status.HTTP_201_CREATED,
            message="Playlist created successfully",
        )
    

    @action(
    detail=False,
    methods=["get"],
    url_path=r"playlist/(?P<pk>\d+)",
    url_name="playlist_retrieve",
    )
    def playlist_retrieve(self, request, pk=None, *args, **kwargs):
        """
        GET /content/playlist/<id>
        Returns a single playlist by primary key.
        """
        qs = self.get_queryset()  # uses queryset_action_classes['playlist_retrieve']
        obj = qs.filter(pk=pk).first()
        if not obj:
            return api_response(
                request,
                status_code=status.HTTP_404_NOT_FOUND,
                errors={"detail": "Playlist not found"},
            )
        ser = self.get_serializer(obj, context={"request": request})
        return api_response(
            request,
            data=ser.data,
            status_code=status.HTTP_200_OK,
            message="Playlist fetched successfully",
        )
    

    @action(
        detail=False,
        methods=["get"],
        url_path=r"playlist/(?P<pk>\d+)",
        url_name="playlist_retrieve",
    )
    def playlist_retrieve(self, request, pk=None, *args, **kwargs):
        qs = self.get_queryset()
        obj = qs.filter(pk=pk).first()
        if not obj:
            return api_response(
                request,
                status_code=status.HTTP_404_NOT_FOUND,
                errors={"detail": "Playlist not found"},
            )

        # 👇 count a view (impression) for this detail load
        obj.inc_impression(when=timezone.now())

        # (optional) show updated numbers in this response
        obj.refresh_from_db(fields=["impressions", "last_impressed_at"])

        ser = self.get_serializer(obj, context={"request": request})
        return api_response(
            request,
            data=ser.data,
            status_code=status.HTTP_200_OK,
            message="Playlist fetched successfully",
        )
    
    
    @action(
    detail=False,
    methods=["delete"],
    url_path=r"playlist_delete/(?P<pk>\d+)",
    url_name="playlist_delete",
    )
    def playlist_delete(self, request, pk=None, *args, **kwargs):
        """
        DELETE /api/content/playlist/<id>
        Deletes a playlist by primary key.
        """
        qs = self.get_queryset()  # uses queryset_action_classes['playlist_delete']
        obj = qs.filter(pk=pk).first()
        if not obj:
            return api_response(
                request,
                status_code=status.HTTP_404_NOT_FOUND,
                errors={"detail": "Playlist not found"},
            )

        obj.delete()
        return api_response(
            request,
            status_code=status.HTTP_204_NO_CONTENT,
            message="Playlist deleted successfully",
        )
    

    ''' Miscellaneous actions you can enable later'''
    @action(
        detail=False,
        methods=["post"],
        url_path=r"playlist/(?P<pk>\d+)/click",
        url_name="playlist_click",
    )
    def playlist_click(self, request, pk=None, *args, **kwargs):
        """
        POST /content/playlist/<id>/click
        Increments click counter for a playlist.
        """
        qs = self.get_queryset()  # uses queryset_action_classes if defined
        obj = qs.filter(pk=pk).first()
        if not obj:
            return api_response(
                request,
                status_code=status.HTTP_404_NOT_FOUND,
                errors={"detail": "Playlist not found"},
            )

        # bump click count
        obj.inc_click(when=timezone.now())

        # optional: fetch updated value so response shows the latest number
        obj.refresh_from_db(fields=["clicks", "last_clicked_at"])

        return api_response(
            request,
            data={"id": obj.pk, "clicks": obj.clicks, "last_clicked_at": obj.last_clicked_at},
            status_code=status.HTTP_200_OK,
            message="Click recorded successfully",
        )
    


    @action(
    detail=False,
    methods=["post"],
    url_path=r"playlist/(?P<pk>\d+)/rate",
    url_name="playlist_rate",
    )
    def playlist_rate(self, request, pk=None, *args, **kwargs):
        """
        POST /content/playlist/<id>/rate
        Body: { "stars": 1..5 }
        Adds a rating to rating_count/rating_sum (no per-user uniqueness).
        """
        qs = self.get_queryset()
        obj = qs.filter(pk=pk).first()
        if not obj:
            return api_response(
                request,
                status_code=status.HTTP_404_NOT_FOUND,
                errors={"detail": "Playlist not found"},
            )

        try:
            stars = int(request.data.get("stars"))
        except (TypeError, ValueError):
            return api_response(
                request,
                status_code=status.HTTP_400_BAD_REQUEST,
                errors={"stars": "Stars must be an integer between 1 and 5"},
            )

        # ✅ enforce valid range
        if stars < 1 or stars > 5:
            return api_response(
                request,
                status_code=status.HTTP_400_BAD_REQUEST,
                errors={"stars": "Stars must be between 1 and 5 inclusive"},
            )

        # safe increment
        obj.add_rating(stars)

        # refresh and compute average
        obj.refresh_from_db(fields=["rating_count", "rating_sum"])
        avg = obj.average_rating

        return api_response(
            request,
            status_code=status.HTTP_200_OK,
            message="Rating recorded",
            data={
                "id": obj.pk,
                "stars": stars,
                "rating_count": obj.rating_count,
                "rating_sum": obj.rating_sum,
                "average_rating": avg,
            },
        )
    

    @action(
        detail=False,
        methods=["get"],
        url_path=r"playlist/(?P<pk>\d+)/ratings/reset",
        url_name="playlist_ratings_reset",
    )
    def playlist_ratings_reset(self, request, pk=None, *args, **kwargs):
        qs = self.get_queryset()
        exists = qs.filter(pk=pk).exists()
        if not exists:
            return api_response(request, status_code=status.HTTP_404_NOT_FOUND,
                                errors={"detail": "Playlist not found"})

        qs.filter(pk=pk).update(rating_count=0, rating_sum=0)
        obj = qs.only("id", "rating_count", "rating_sum").get(pk=pk)

        return api_response(
            request,
            status_code=status.HTTP_200_OK,
            message="Ratings reset",
            data={
                "id": obj.pk,
                "rating_count": obj.rating_count,
                "rating_sum": obj.rating_sum,
                "average_rating": 0.0,
            },
        )
    

    @action(
    detail=False,
    methods=["get"],
    url_path=r"playlist/(?P<pk>\d+)/impressions/reset",
    url_name="playlist_impressions_reset",
    )
    def playlist_impressions_reset(self, request, pk=None, *args, **kwargs):
        """
        POST /content/playlist/<id>/impressions/reset
        Resets impressions counter and related fields for a playlist.
        """
        qs = self.get_queryset()
        obj = qs.filter(pk=pk).first()
        if not obj:
            return api_response(
                request,
                status_code=status.HTTP_404_NOT_FOUND,
                errors={"detail": "Playlist not found"},
            )

        # reset impressions + last_impressed_at + ctr
        qs.filter(pk=pk).update(impressions=0, last_impressed_at=None, ctr=0)

        # fetch fresh values
        obj.refresh_from_db(fields=["impressions", "last_impressed_at", "ctr"])

        return api_response(
            request,
            status_code=status.HTTP_200_OK,
            message="Impressions reset successfully",
            data={
                "id": obj.pk,
                "impressions": obj.impressions,
                "last_impressed_at": obj.last_impressed_at,
                "ctr": float(obj.ctr),
            },
        )



    @action(
        detail=False,
        methods=["get"],
        url_path=r"playlist/featured",
        url_name="featured_playlists",
    )
    def featured_playlists(self, request, *args, **kwargs):
        """
        GET /content/playlist/featured/
        Returns 4 featured playlists ONLY if present in Redis.

        If the cache key is missing, DO NOT compute/write.
        """
        blob = cache.get(settings.FEATURED_KEY)

        # ❌ Not present in cache → pick ONE behavior:
        if not blob:
            # (A) Keep your current 404 behavior:
            resp = api_response(
                request,
                data={"items": []},
                status_code=status.HTTP_404_NOT_FOUND,
                message="Featured playlists not present in cache",
            )
            resp["Cache-Control"] = "public, max-age=60, stale-while-revalidate=60"
            # If cross-origin: make sure CORS_EXPOSE_HEADERS includes ETag (settings.py)
            return resp

            # (B) Or, prefer 200 empty to avoid FE error states:
            # resp = api_response(request, data={"items": []}, status_code=status.HTTP_200_OK,
            #                     message="Featured playlists not present in cache")
            # resp["Cache-Control"] = "public, max-age=60, stale-while-revalidate=60"
            # resp["ETag"] = 'W/"featured:empty"'
            # return resp

        # ✅ Present in cache
        payload = {"data": blob}

        # Compute a stable (weak) ETag over the JSON payload
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        etag_value = hashlib.md5(raw).hexdigest()
        etag_quoted = f'W/"{etag_value}"'  # weak is fine for list resources

        # Parse If-None-Match, which can be a list: ETag, "ETag", W/"ETag", etc.
        inm = request.headers.get("If-None-Match", "")
        candidates = [t.strip() for t in ETAG_SPLIT_RE.split(inm) if t.strip()]
        candidates_normalized = {t.strip('W/w"') for t in candidates}  # remove quotes + leading W/
        current_normalized = etag_value

        if current_normalized in candidates_normalized or etag_quoted in candidates:
            # 304 Not Modified (no body)
            resp = api_response(
                request,
                data=None,
                status_code=status.HTTP_304_NOT_MODIFIED,
                message="Not Modified",
            )
            # Send ETag on 304 as well (good practice)
            resp["ETag"] = etag_quoted
            resp["Cache-Control"] = "public, max-age=300, stale-while-revalidate=120"
            return resp

        # 200 with body
        resp = api_response(
            request,
            data=payload["data"],
            status_code=status.HTTP_200_OK,
            message="Featured playlists fetched successfully",
        )
        resp["ETag"] = etag_quoted
        resp["Cache-Control"] = "public, max-age=300, stale-while-revalidate=120"
        return resp