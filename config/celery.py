# Celery app — reserved for future use when a paid Render plan supports workers.
# To enable: uncomment, add celery>=5.4,<6 to requirements/base.txt, and
# configure CELERY_* settings in config/settings/base.py.
#
# import os
# from celery import Celery
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
# app = Celery("ahara")
# app.config_from_object("django.conf:settings", namespace="CELERY")
# app.autodiscover_tasks()
