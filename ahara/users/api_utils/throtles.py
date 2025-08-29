from rest_framework.throttling import AnonRateThrottle,SimpleRateThrottle

class SignupThrottle(AnonRateThrottle):
    scope = "signup"

class LoginIPThrottle(AnonRateThrottle):
    scope = "login"          # per-IP

class LoginUserThrottle(SimpleRateThrottle):
    scope = "login_user"     # per-email (to slow attacks on a single account)

    def get_cache_key(self, request, view):
        if request.method != "POST":
            return None
        email = (request.data.get("email") or "").lower().strip()
        if not email:
            return None
        return f"throttle_login_user:{email}"