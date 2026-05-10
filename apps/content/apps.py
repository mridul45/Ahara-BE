# ahara/content/apps.py
from django.apps import AppConfig


class ContentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.content"

    def ready(self):
        from . import signals  # noqa: F401 — register signal handlers
        self._warm_category_cache()

    @staticmethod
    def _warm_category_cache():
        """Pre-populate the category cache on startup.

        Deferred via on_commit / post_migrate so it never fires during
        makemigrations or before the schema exists.  Wrapped in try/except
        so Redis unavailability never prevents the app from starting.
        """
        from django.db import connection
        from django.db.models.signals import post_migrate
        from django.dispatch import receiver

        @receiver(post_migrate, weak=False)
        def _do_warm(sender, **kwargs):
            # Only run once per process, and only for this app's migrations.
            if sender.name != "apps.content":
                return
            try:
                from django.conf import settings
                from django.core.cache import cache
                from .models import Category
                from .serializers import CategoryReadSerializer

                if cache.get(settings.CATEGORY_CACHE_KEY) is not None:
                    return

                qs = Category.objects.filter(is_active=True).order_by("order", "name")
                items = list(CategoryReadSerializer(qs, many=True).data)
                cache.set(settings.CATEGORY_CACHE_KEY, items, timeout=settings.CATEGORY_CACHE_TTL)
            except Exception:
                pass