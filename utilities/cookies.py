from django.conf import settings
from datetime import datetime, timezone as dt_timezone
from rest_framework_simplejwt.tokens import RefreshToken

# -------------------- Cookie helpers (read settings.py) --------------------
def _set_refresh_cookie(response, refresh: RefreshToken):
    """Set refresh token in HttpOnly cookie; expiry aligned to token exp."""
    exp_ts = refresh["exp"]
    exp_dt = datetime.fromtimestamp(exp_ts, tz=dt_timezone.utc)
    cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "ahara_rt")
    cookie_kwargs = getattr(
        settings,
        "REFRESH_COOKIE_KWARGS",
        {
            "httponly": True,
            "secure": not getattr(settings, "DEBUG", False),
            "samesite": "Lax" if getattr(settings, "DEBUG", False) else "Strict",
            "path": "/",
        },
    )
    response.set_cookie(
        key=cookie_name,
        value=str(refresh),
        expires=exp_dt,
        **cookie_kwargs,
    )


def _clear_refresh_cookie(response):
    cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "ahara_rt")
    response.delete_cookie(cookie_name, path="/")