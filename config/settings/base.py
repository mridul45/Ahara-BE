# ruff: noqa: ERA001, E501
"""Base settings to build other settings files upon."""

from datetime import timedelta
from pathlib import Path
import os
from urllib.parse import urlparse
from corsheaders.defaults import default_headers
import certifi
import environ
import ssl


BASE_DIR = Path(__file__).resolve(strict=True).parent.parent.parent
APPS_DIR = BASE_DIR / "ahara"
env = environ.Env()

# -------------------- .env loading --------------------
READ_DOT_ENV_FILE = env.bool("DJANGO_READ_DOT_ENV_FILE", default=False)
if READ_DOT_ENV_FILE:
    if env("DJANGO_ENV", default="local") == "production":
        env.read_env(str(BASE_DIR / ".env.production"))
    else:
        env.read_env(str(BASE_DIR / ".env"))

# -------------------- General / Security --------------------
SECRET_KEY = env("SECRET_KEY", default="dev-insecure-key")  # dev only
DEBUG = env.bool("DJANGO_DEBUG", False)

DJANGO_ENV = env("DJANGO_ENV", default=("production" if not DEBUG else "local"))
IS_PROD = DJANGO_ENV == "production"

# Your FE is on GitHub Pages (different site) → cross-site cookies required
CROSS_SITE_COOKIES = env.bool("CROSS_SITE_COOKIES", default=True)

TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"
SITE_ID = 1
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [str(BASE_DIR / "locale")]

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# Auto add Render’s external URL/hostname
external_url = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if external_url:
    parsed = urlparse(external_url if "://" in external_url else f"https://{external_url}")
    host = parsed.netloc or parsed.path
    if host and host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)
    origin = f"{parsed.scheme or 'https'}://{host}"
    if origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# CSRF cookie must be readable by JS to send X-CSRFToken from SPA
CSRF_COOKIE_HTTPONLY = False
# For cross-site XHR, CSRF cookie needs SameSite=None
CSRF_COOKIE_SAMESITE = "None" if CROSS_SITE_COOKIES else ("Lax" if not IS_PROD else "Lax")

# -------------------- DB --------------------
DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres:///ahara"),
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -------------------- URLS / WSGI --------------------
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# -------------------- Apps --------------------
DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
    "django.forms",
]
THIRD_PARTY_APPS = [
    "crispy_forms",
    "crispy_bootstrap5",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "allauth.socialaccount",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
]
LOCAL_APPS = [
    "ahara.users",
    "apps.content",
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# -------------------- Auth --------------------
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
AUTH_USER_MODEL = "users.User"
LOGIN_REDIRECT_URL = "users:redirect"
LOGIN_URL = "account_login"

# -------------------- Passwords --------------------
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 5}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -------------------- Middleware --------------------
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

# -------------------- CORS --------------------
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "https://mridul45.github.io",  # GitHub Pages FE
]
CORS_ALLOW_CREDENTIALS = True

# Also trust FE for CSRF
if "https://mridul45.github.io" not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append("https://mridul45.github.io")

if "http://localhost:5173" not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append("http://localhost:5173")

CORS_ALLOW_HEADERS = list(default_headers) + [
    "x-csrftoken",
    "if-none-match",
    "if-modified-since",
]

# -------------------- Static / Media --------------------
STATIC_ROOT = str(BASE_DIR / "staticfiles")
STATIC_URL = "/static/"
STATICFILES_DIRS = [str(APPS_DIR / "static")]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_ROOT = str(APPS_DIR / "media")
MEDIA_URL = "/media/"

# -------------------- Templates --------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [str(APPS_DIR / "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "ahara.users.context_processors.allauth_settings",
            ],
        },
    },
]
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

# -------------------- Crispy / Compressor --------------------
CRISPY_TEMPLATE_PACK = "bootstrap5"
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
INSTALLED_APPS += ["compressor"]
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "compressor.finders.CompressorFinder",
]

# -------------------- Email --------------------
EMAIL_BACKEND = env("DJANGO_EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_TIMEOUT = 5

# -------------------- Admin --------------------
ADMIN_URL = "admin/"
ADMINS = [("Mridul Singhal", "mridulsingha474@gmail.com")]
MANAGERS = ADMINS
DJANGO_ADMIN_FORCE_ALLAUTH = env.bool("DJANGO_ADMIN_FORCE_ALLAUTH", default=False)

# -------------------- Logging --------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"verbose": {"format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s"}},
    "handlers": {"console": {"level": "DEBUG", "class": "logging.StreamHandler", "formatter": "verbose"}},
    "root": {"level": "INFO", "handlers": ["console"]},
}


CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        # Note the scheme is now "redis://"
        "LOCATION": "redis://default:cNW1X7M0LKV7pjZcZODbJ09gRSLgC1v6@redis-10090.crce206.ap-south-1-1.ec2.cloud.redislabs.com:10090/0",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SERIALIZER": "django_redis.serializers.json.JSONSerializer",
            # Connection parameters are lowercase
            "ssl": True,
            "ssl_cert_reqs": "required", # Good practice for security
        },
        "KEY_PREFIX": "ahara", 
    }
}

# -------------------- Redis --------------------
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
REDIS_SSL = REDIS_URL.startswith("rediss://")

# -------------------- allauth --------------------
ACCOUNT_ALLOW_REGISTRATION = env.bool("DJANGO_ACCOUNT_ALLOW_REGISTRATION", True)
ACCOUNT_LOGIN_METHODS = {"username"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_ADAPTER = "ahara.users.adapters.AccountAdapter"
ACCOUNT_FORMS = {"signup": "ahara.users.forms.UserSignupForm"}
SOCIALACCOUNT_ADAPTER = "ahara.users.adapters.SocialAccountAdapter"
SOCIALACCOUNT_FORMS = {"signup": "ahara.users.forms.UserSocialSignupForm"}

# -------------------- DRF / JWT --------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/min",
        "user": "1000/min",
        "signup": "5/min",
        "login": "10/min",
        "login_user": "5/min",
        "verify_otp": "5/min",
        "verify_otp_user": "5/min",
    },
    "EXCEPTION_HANDLER": "utilities.response.unified_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=10),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",
    "JTI_CLAIM": "jti",
    "LEEWAY": 30,
    "UPDATE_LAST_LOGIN": True,
}

# -------------------- Refresh cookie (centralized) --------------------
REFRESH_COOKIE_NAME = "ahara_rt"
REFRESH_COOKIE_KWARGS = {
    "httponly": True,
    # Cross-site requires Secure=True + SameSite=None (GitHub Pages ↔ Render)
    "secure": True if (IS_PROD or CROSS_SITE_COOKIES) else False,
    "samesite": "None" if CROSS_SITE_COOKIES else ("Strict" if IS_PROD else "Lax"),
    "path": "/",
}

# -------------------- Your stuff --------------------
IMAGEKIT_PUBLIC_KEY = env("IMAGEKIT_PUBLIC_KEY")
IMAGEKIT_PRIVATE_KEY = env("IMAGEKIT_PRIVATE_KEY")
IMAGEKIT_URL_ENDPOINT = env("IMAGEKIT_URL_ENDPOINT")


FEATURED_KEY = env("FEATURED_KEY", default="ahara:pl:featured:v1:default")
FEATURED_TTL = env.int("FEATURED_TTL", default=60 * 60 * 6)