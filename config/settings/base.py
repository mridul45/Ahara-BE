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
    "drf_spectacular",
]
LOCAL_APPS = [
    "ahara.users",
    "apps.content",
    "apps.intelligence",
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

if "https://ahara-be.onrender.com" not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append("https://ahara-be.onrender.com")

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
        "BACKEND": "utilities.cache_backend.FallbackCache",
        "LOCATION": env("REDIS_URL", default="redis://default:ZdenAdAKhMnYTRGJHqZWEtWYfmsWyR4v@redis-16980.c305.ap-south-1-1.ec2.cloud.redislabs.com:16980/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SERIALIZER": "django_redis.serializers.json.JSONSerializer",
            # Connection parameters are lowercase
            "ssl": True,
            "ssl_cert_reqs": "required",  # Good practice for security
        },
        "KEY_PREFIX": "ahara",
        "FALLBACK_COOLDOWN": 60,  # seconds before retrying Redis after failure
    }
}

# -------------------- Redis --------------------
REDIS_URL = env("REDIS_URL", default="redis://default:ZdenAdAKhMnYTRGJHqZWEtWYfmsWyR4v@redis-16980.c305.ap-south-1-1.ec2.cloud.redislabs.com:16980/0")
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
    "DEFAULT_SCHEMA_CLASS": "utilities.schema.AppGroupAutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Ahara API Documentation",
    "DESCRIPTION": """
# ✨ Welcome to the Ahara API! 

This page is your playground! It’s an interactive documentation site where you can not only see what links (endpoints) exist in the backend, but you can also test them out by sending data directly from here. 

---

## 🔒 Step 1: How to Login & Get Access
Most of the actions in this app (like rating a playlist or asking the AI) require you to prove who you are. We do this using a **Login Token** (JWT).

**Here is exactly how to get one:**
1. Scroll down to the **Users** section and find the `POST /users/auth/login/` (or similar login endpoint).
2. Click on the row to expand it, then click the **"Try it out"** button.
3. Fill in your email/username and password in the JSON box. Wait, what's a JSON box? It's just a text format for sending data. Example:
   ```json
   {
     "username": "mridul",
     "password": "mypassword123"
   }
   ```
4. Click the big **Execute** button.
5. If your login is correct, scroll down to the "Server response" box. You will see a long string of random letters and numbers called `"access"`. Copy that whole string (without quotes).
6. Now, scroll all the way back to the very top of this page and click the white **"Authorize"** button next to the lock icon.
7. In the box that pops up, type the word `Bearer`, press space, and paste your token. Example:
   `Bearer eyJhbGciOiJIUzI1Ni...`
8. Click **Authorize** and then **Close**. You are now logged in! Every endpoint will now automatically attach your "ID card" to prove who you are.

---

## 📖 Step 2: Understanding the Endpoints

An "endpoint" is just a specific web address that does a specific job. Here is what each one does in simple English:

### 👤 Users (Your Account)
- `POST /users/auth/login/` - **Log In**: Tell the app who you are to get your access token.
- `GET /users/auth/me/` - **My Profile**: Just returns your name, email, and user details if you are successfully logged in. 

### 🎵 Content (Playlists & Therapy)
This section handles all the wellness playlists, music, and content recommendations.

- `GET /api/content/playlist/` - **Get Recommended Playlists**: Fetches playlists meant for you. Simply hit "Execute" to try it. No extra data needed.
- `POST /api/content/playlist-create/` - **Create a Playlist**: Allows an admin to create a new playlist by sending a title and tracks.
- `GET /api/content/playlist/{id}/` - **Get Specific Playlist**: Enter the ID of a specific playlist in the box, and it will fetch the details for just that one.
- `POST /api/content/playlist/{id}/click/` - **Record a Click**: Every time a user clicks a playlist in your app, call this. It tells the backend "Hey, the user showed interest in this!" so we can recommend better things later. No payload needed, just the ID.
- `GET /api/content/playlist/{id}/impressions/reset/` - **Reset Views**: Clears out the view history count for a given playlist. 
- `POST /api/content/playlist/{id}/rate/` - **Add a Rating**: Lets the user give 1-5 stars and a comment. You must send data like this:
  ```json
  {
    "rating": 5,
    "comment": "This sound therapy really helped me sleep!"
  }
  ```
- `GET /api/content/playlist/{id}/ratings/reset/` - **Clear Ratings**: Danger! Deletes all ratings on a specific playlist.
- `GET /api/content/playlist/featured/` - **Get Featured Content**: Fetches the hand-picked, top-level playlists for the home screen (doesn't need an ID).
- `DELETE /api/content/playlist_delete/{id}/` - **Delete Playlist**: Completely removes the playlist from the database. Enter the ID to delete.

### 🧠 Intelligence (AI Assistant)
This is where the magic happens and the backend talks to the Gemini AI.

- `POST /api/intelligence/ask/` - **Ask Ahara AI**: This is how you send a question to the AI engine. You must provide a "prompt". Example data to send:
  ```json
  {
    "prompt": "I'm feeling very stressed right now and I have a slight headache. What sound frequency should I listen to?"
  }
  ```
  The AI will respond back with advice, generated entirely on the fly based on your prompt!

---
*If you get a "401 Unauthorized" error at any point, it means your token expired. Just go back to Step 1 and log in again to get a fresh one!*
""",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
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
    "path": "/",
    # Industry standard: Only require HTTPS if not in DEBUG mode
    "secure": not DEBUG, 
    # Lax is the standard for same-site local development
    "samesite": "Lax" if DEBUG else "None", 
}

CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG

# -------------------- Your stuff --------------------
IMAGEKIT_PUBLIC_KEY = env("IMAGEKIT_PUBLIC_KEY")
IMAGEKIT_PRIVATE_KEY = env("IMAGEKIT_PRIVATE_KEY")
IMAGEKIT_URL_ENDPOINT = env("IMAGEKIT_URL_ENDPOINT")


FEATURED_KEY = env("FEATURED_KEY", default="ahara:pl:featured:v1:default")
FEATURED_TTL = env.int("FEATURED_TTL", default=60 * 60 * 6)

GEMINI_API_KEY = env("GEMINI_API_KEY", default="YOUR API KEY HERE....")