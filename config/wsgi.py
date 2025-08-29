"""
WSGI config for Ahara project.

This module contains the WSGI application used by Django's development server
and any production WSGI deployments. It should expose a module-level variable
named ``application``. Django's ``runserver`` and ``runfcgi`` commands discover
this application via the ``WSGI_APPLICATION`` setting.

Usually you will have the standard Django WSGI application here, but it also
might make sense to replace the whole Django WSGI application with a custom one
that later delegates to the Django one. For example, you could introduce WSGI
middleware here, or combine a Django application with an application of another
framework.

"""

# config/wsgi.py
import os
import sys
from pathlib import Path
from django.core.wsgi import get_wsgi_application

BASE_DIR = Path(__file__).resolve(strict=True).parent.parent
sys.path.append(str(BASE_DIR / "ahara"))

# If DJANGO_SETTINGS_MODULE is already set (e.g., by Render), do nothing.
if "DJANGO_SETTINGS_MODULE" not in os.environ:
    env = os.environ.get("DJANGO_ENV", "production").lower()
    default_module = "config.settings.base" if env in {"local", "dev", "development"} else "config.settings.production"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", default_module)

application = get_wsgi_application()