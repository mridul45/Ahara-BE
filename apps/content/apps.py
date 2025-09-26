# ahara/content/apps.py
from django.apps import AppConfig


class ContentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.content"

    def ready(self):
        # Import signal handlers so they get registered
        from . import signals  # noqa