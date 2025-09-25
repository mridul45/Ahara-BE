# content/admin.py
from django.contrib import admin,messages
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import Playlist,Video
from django.utils import timezone


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    # ---------- List page ----------
    list_display = (
        "thumb",                    # NEW: tiny thumbnail preview
        "title",
        "playlist_type",
        "language",
        "short_description",
        "impressions",
        "clicks",
        "ctr_percent",             # cached CTR
        "completion_percent",      # cached completions/starts
        "avg_watch_hms",
        "avg_rating_star",
        "updated_at",
        "created_at",
    )
    list_display_links = ("title",)
    list_filter = ("playlist_type", "language", "updated_at", "created_at")
    search_fields = ("title", "description")
    date_hierarchy = "updated_at"
    ordering = ("-updated_at",)
    empty_value_display = "—"

    # ---------- Read-only + layout ----------
    readonly_fields = (
        "_about",
        # previews & file ids
        "thumbnail_preview",       # NEW: big preview on detail page
        "thumbnail_file_id",       # model has editable=False; expose as read-only explicitly
        # core timestamps
        "created_at", "updated_at",
        # counters (keep read-only in admin; mutate via services/tasks)
        "impressions", "clicks", "starts", "completes",
        "likes", "bookmarks", "shares",
        "total_watch_seconds", "avg_watch_seconds", "avg_progress_pct",
        "rating_count", "rating_sum",
        # cached rollups
        "ctr", "completion_rate",
        # derived quick-reads
        "average_rating_admin",
        "computed_ctr_admin",
        "computed_completion_rate_admin",
        # last activity
        "last_impressed_at", "last_clicked_at",
        "last_started_at", "last_completed_at", "last_interaction_at",
    )

    fieldsets = (
        (_("About this model"), {"fields": ("_about",)}),
        (_("Details"), {
            "fields": ("title", "description", "playlist_type", "language"),
        }),
        (_("Artwork"), {  # NEW: thumbnail section
            "fields": (
                "thumbnail",
                "thumbnail_preview",
                "thumbnail_file_id",
            )
        }),
        (_("Analytics – Counters"), {
            "fields": (
                ("impressions", "clicks"),
                ("starts", "completes"),
                ("likes", "bookmarks", "shares"),
                ("total_watch_seconds", "avg_watch_seconds", "avg_progress_pct"),
                ("rating_count", "rating_sum"),
            )
        }),
        (_("Analytics – Rollups & Derived"), {
            "fields": (
                ("ctr", "completion_rate"),
                ("average_rating_admin", "computed_ctr_admin", "computed_completion_rate_admin"),
            )
        }),
        (_("Last Activity"), {
            "fields": (
                "last_impressed_at", "last_clicked_at",
                "last_started_at", "last_completed_at", "last_interaction_at",
            )
        }),
        (_("Snapshot (Breakdown)"), {"fields": ("breakdown",)}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at")}),
    )

    # ---------- Pretty panels ----------
    def _about(self, obj):
        return format_html(
            "<div style='padding:12px; border-radius:10px; "
            "background: var(--darkened-bg); border: 1px solid var(--border-color); color: var(--body-fg);'>"
            "<p style='margin:0 0 6px; font-weight:600;'>{}</p>"
            "<p style='margin:0; font-size:0.9em; line-height:1.4;'>{}</p>"
            "</div>",
            _("What is a Playlist?"),
            _("Playlists are curated sets of lessons or meditations that you can feature "
              "in the app or stitch into multi-day programs like ‘7-Day Sleep Reset’."),
        )
    _about.short_description = ""

    # ---------- Thumbnails ----------
    @admin.display(description=_("Thumbnail"))
    def thumb(self, obj):
        """Small inline preview for list view."""
        if getattr(obj, "thumbnail", None) and getattr(obj.thumbnail, "url", None):
            return format_html(
                "<img src='{}' style='height:36px;width:64px;object-fit:cover;border-radius:6px;border:1px solid var(--border-color);'/>",
                obj.thumbnail.url
            )
        return self.empty_value_display

    @admin.display(description=_("Preview"))
    def thumbnail_preview(self, obj):
        """Large preview on detail view."""
        if getattr(obj, "thumbnail", None) and getattr(obj.thumbnail, "url", None):
            return format_html(
                "<img src='{}' style='max-height:200px;width:auto;border-radius:10px;"
                "box-shadow:0 4px 18px rgba(0,0,0,.25);border:1px solid var(--border-color);'/>",
                obj.thumbnail.url
            )
        return self.empty_value_display

    # ---------- List helpers (compact, human-friendly) ----------
    @admin.display(description=_("Summary"))
    def short_description(self, obj):
        if not obj.description:
            return self.empty_value_display
        s = obj.description.strip()
        return (s[:77] + "…") if len(s) > 80 else s

    @admin.display(description=_("CTR"))
    def ctr_percent(self, obj):
        # prefer cached ctr; fallback to computed on the fly
        val = float(obj.ctr or 0) if obj.ctr is not None else float(getattr(obj, "computed_ctr", 0.0))
        return f"{val * 100:.1f}%"

    @admin.display(description=_("Completion"))
    def completion_percent(self, obj):
        val = float(obj.completion_rate or 0) if obj.completion_rate is not None else float(getattr(obj, "computed_completion_rate", 0.0))
        return f"{val * 100:.1f}%"

    @admin.display(description=_("Avg Watch"))
    def avg_watch_hms(self, obj):
        # convert seconds to H:MM:SS
        sec = int(obj.avg_watch_seconds or 0)
        h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    @admin.display(description=_("Avg ★"))
    def avg_rating_star(self, obj):
        avg = getattr(obj, "average_rating", 0.0) or 0.0
        return f"{avg:.2f}"

    # ---------- Detail helpers (read-only derived) ----------
    @admin.display(description=_("Average rating (derived)"))
    def average_rating_admin(self, obj):
        return f"{getattr(obj, 'average_rating', 0.0):.3f}"

    @admin.display(description=_("Computed CTR (derived)"))
    def computed_ctr_admin(self, obj):
        return f"{getattr(obj, 'computed_ctr', 0.0) * 100:.2f}%"

    @admin.display(description=_("Computed Completion (derived)"))
    def computed_completion_rate_admin(self, obj):
        return f"{getattr(obj, 'computed_completion_rate', 0.0) * 100:.2f}%"

    # ---------- Bulk actions ----------
    actions = ["recompute_rollups_action", "reset_breakdown_action"]

    @admin.action(description=_("Recompute cached CTR/Completion from counters"))
    def recompute_rollups_action(self, request, queryset):
        for obj in queryset:
            obj.recompute_rollups()

    @admin.action(description=_("Clear `breakdown` snapshot"))
    def reset_breakdown_action(self, request, queryset):
        queryset.update(breakdown=None)


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    # -------- List page --------
    list_display = (
        "playlists_display",      # ✅ method instead of raw M2M field
        "title",                  # not editable (linked)
        "content_type",
        "content_genre",
        "difficulty_level",
        "language",
        "instructor",
        "is_published_badge",
        "is_published",
        "is_featured",            # editable
        "requires_subscription",  # editable
        "zen_mode_only",          # editable
        "publish_at",
        "created_at",
    )
    list_display_links = ("title",)
    list_editable = (
        "is_featured",
        "requires_subscription",
        "zen_mode_only",
        "is_published",
        "publish_at",
    )
    search_fields = ("title", "description", "instructor", "playlist__title")
    list_filter = (
        "playlist",               # M2M is OK in filters
        "content_type",
        "content_genre",
        "difficulty_level",
        "language",
        "instructor",
        "is_published",
        "requires_subscription",
        "zen_mode_only",
        "is_featured",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    empty_value_display = "—"
    save_on_top = True

    # nice dual-select UI for M2M in the form
    filter_horizontal = ("playlist",)

    # -------- Detail page --------
    readonly_fields = (
        "_about",
        "video_file_id",
        "thumbnail_file_id",
        "subtitles_file_id",
        "transcript_file_id",
        "created_at",
        "updated_at",
        "thumbnail_preview",
        "video_inline_preview",
        "is_published_badge",
    )

    fieldsets = (
        (_("About this model"), {"fields": ("_about",)}),
        (_("Basic Info"), {"fields": ("playlist", "title", "description", "instructor")}),
        (_("Classification"), {
            "fields": ("content_type", "content_genre", "difficulty_level", "language"),
        }),
        (_("Publishing & Access"), {
            "fields": (
                "is_published_badge",
                "is_published",
                "publish_at",
                "is_featured",
                "requires_subscription",
                "zen_mode_only",
            ),
        }),
        (_("Media Files"), {
            "fields": (
                "video",
                "video_inline_preview",
                "thumbnail",
                "thumbnail_preview",
                "duration_seconds",
            ),
        }),
        (_("Streaming"), {"classes": ("collapse",), "fields": ("hls_manifest_url",)}),
        (_("Captions & Transcript"), {"fields": ("subtitles", "transcript")}),
        (_("AI Metadata"), {"classes": ("collapse",), "fields": ("ai_pose_model_version",)}),
        (_("ImageKit File IDs (auto-managed)"), {
            "classes": ("collapse",),
            "fields": ("video_file_id", "thumbnail_file_id", "subtitles_file_id", "transcript_file_id"),
        }),
        (_("Timestamps"), {"fields": ("created_at", "updated_at")}),
    )

    # -------- Actions --------
    @admin.action(description=_("Publish selected now"))
    def publish_selected(self, request, queryset):
        updated = queryset.update(is_published=True, publish_at=timezone.now())
        messages.success(request, _(f"Published {updated} video(s)."))

    @admin.action(description=_("Unpublish selected"))
    def unpublish_selected(self, request, queryset):
        updated = queryset.update(is_published=False)
        messages.success(request, _(f"Unpublished {updated} video(s)."))

    actions = ["publish_selected", "unpublish_selected"]

    # -------- Helpers --------
    @admin.display(description=_("Playlists"))
    def playlists_display(self, obj):
        """
        Compact, safe representation for list_display.
        Avoids raw M2M which triggers admin.E109.
        """
        qs = obj.playlist.all().only("title")
        names = [p.title or f"#{p.pk}" for p in qs[:3]]
        suffix = " …" if qs.count() > 3 else ""
        return ", ".join(names) + suffix if names else self.empty_value_display

    @admin.display(description=_("Status"))
    def is_published_badge(self, obj):
        color_bg = "#10b981" if obj.is_published else "#ef4444"
        label = _("Published") if obj.is_published else _("Draft")
        return format_html(
            "<span style='padding:2px 8px;border-radius:999px;font-size:11px;"
            "font-weight:600;color:white;background:{}'>{}</span>",
            color_bg, label,
        )

    def _about(self, obj):
        return format_html(
            "<div style='padding:12px;border-radius:10px;"
            "background:var(--darkened-bg);border:1px solid var(--border-color);color:var(--body-fg);'>"
            "<p style='margin:0 0 6px;font-weight:600;'>{}</p>"
            "<p style='margin:0;font-size:0.9em;line-height:1.4;'>{}</p>"
            "</div>",
            _("What is a Video?"),
            _("A Video is a core content unit with optional subtitles/transcript. "
              "Publishing controls visibility; access fields mark subscription or Zen Mode content."),
        )

    @admin.display(description=_("Thumbnail"))
    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return format_html(
                '<img src="{}" style="max-height:60px;border-radius:6px;" />', obj.thumbnail.url
            )
        return self.empty_value_display

    @admin.display(description=_("Preview"))
    def video_inline_preview(self, obj):
        if obj.video:
            return format_html(
                '<video style="max-width:480px;max-height:270px;border-radius:8px;" '
                'controls preload="metadata" src="{}"></video>',
                obj.video.url,
            )
        return self.empty_value_display