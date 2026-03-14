from django.apps import AppConfig


class IntelligenceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.intelligence'

    def ready(self):
        try:
            import apps.intelligence.signals  # noqa F401
        except ImportError:
            pass

