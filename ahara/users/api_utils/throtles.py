from rest_framework.throttling import AnonRateThrottle
from rest_framework.throttling import SimpleRateThrottle


class SignupThrottle(AnonRateThrottle):
    scope = "signup"


class LoginIPThrottle(AnonRateThrottle):
    scope = "login"  # per-IP


class LoginUserThrottle(SimpleRateThrottle):
    scope = "login_user"  # per-email (to slow attacks on a single account)

    def get_cache_key(self, request, view):
        if request.method != "POST":
            return None
        email = (request.data.get("email") or "").lower().strip()
        if not email:
            return None
        return f"throttle_login_user:{email}"



class VerifyOtpIPThrottle(AnonRateThrottle):
    """
    Per-IP throttle for OTP verification attempts.
    Rate configured by DEFAULT_THROTTLE_RATES['verify_otp'].
    """
    scope = "verify_otp"


class VerifyOtpUserThrottle(SimpleRateThrottle):
    """
    Per-email throttle for OTP verification attempts.
    Rate configured by DEFAULT_THROTTLE_RATES['verify_otp_user'].
    """
    scope = "verify_otp_user"

    def get_cache_key(self, request, view):
        # read email from body or query; fall back to IP (extra safety)
        email = (request.data.get("email")
                 or request.query_params.get("email")
                 or self.get_ident(request))
        if not email:
            return None
        ident = str(email).lower().strip()
        return self.cache_format % {"scope": self.scope, "ident": ident}