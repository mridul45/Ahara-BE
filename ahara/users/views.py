# ahara/users/views.py
''' <-------------------------------------- IMPORTS --------------------------------------> '''
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from utilities.response import api_response
from utilities.cookies import _set_refresh_cookie, _clear_refresh_cookie

from django.middleware.csrf import get_token

from .api_utils.throtles import (
    SignupThrottle,
    LoginIPThrottle,
    LoginUserThrottle,
    VerifyOtpIPThrottle,
    VerifyOtpUserThrottle,
)
from .serializers import (
    LoginSerializer,
    EmailOnlyLoginSerializer,
    EmailOnlySignupSerializer,
    UserCredsSerializer,
    UserDetailSerializer,
    VerifyOtpSerializer,
    UserUpdateSerializer,
)
from django.core.cache import cache
from utilities.email import send_otp_email
from utilities.username_gen import _generate_unique_username
from utilities.otp import generate_otp
''' <-------------------------------------- IMPORTS FINISH --------------------------------------> '''

User = get_user_model()


class AuthViewSet(viewsets.GenericViewSet):
    """
    Auth ViewSet with per-action serializer/permission/auth/throttle maps.
    Access token -> returned in JSON (FE stores in memory).
    Refresh token -> HttpOnly cookie (server-set), rotated on /refresh, blacklisted on logout.
    """
    queryset = User._default_manager.all()

    # ---- Defaults ----
    serializer_class = UserCredsSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    throttle_classes = []

    # ---- Per-action maps ----
    serializer_action_classes = {
        "register": UserCredsSerializer,
        "login": LoginSerializer,
        "email_login": EmailOnlyLoginSerializer,
        "email_signup": EmailOnlySignupSerializer,
        "me": UserDetailSerializer,
        "verify_otp": VerifyOtpSerializer,
        # "refresh" and "csrf" are cookie-based/public -> no serializer
    }
    permission_action_classes = {
        "register": [AllowAny],
        "login": [AllowAny],
        "email_login": [AllowAny],
        "email_signup": [AllowAny],
        "me": [IsAuthenticated],
        "verify_otp": [AllowAny],
        "refresh": [AllowAny],
        "logout": [AllowAny],
        "csrf": [AllowAny],
    }
    authentication_action_classes = {
        "register": [],             # open endpoint
        "login": [],                # open endpoint
        "email_login": [],          # passwordless, open endpoint
        "email_signup": [],         # passwordless, open endpoint
        "me": [JWTAuthentication],  # bearer access required
        "verify_otp": [],           # open endpoint
        "refresh": [],              # cookie-based, not access-based
        "logout": [],               # cookie-based
        "csrf": [],                 # public
    }
    throttle_action_classes = {
        "register": [SignupThrottle],
        "login": [LoginIPThrottle, LoginUserThrottle],
        "email_login": [LoginIPThrottle],
        "email_signup": [SignupThrottle],
        "me": [],
        "verify_otp": [VerifyOtpIPThrottle, VerifyOtpUserThrottle],
        # You may add a small throttle for "refresh" if desired
        # "refresh": [SomeRefreshThrottle],
    }

    # Ensure self.action is available before DRF asks for authenticators/permissions.
    def initialize_request(self, request, *args, **kwargs):
        if not hasattr(self, "action"):
            action_map = getattr(self, "action_map", None)
            if action_map:
                self.action = action_map.get(request.method.lower())
        return super().initialize_request(request, *args, **kwargs)

    # Map helpers
    def get_serializer_class(self):
        action = getattr(self, "action", None)
        return self.serializer_action_classes.get(action, self.serializer_class)

    def get_permissions(self):
        action = getattr(self, "action", None)
        classes = self.permission_action_classes.get(action, self.permission_classes)
        return [cls() for cls in classes]

    def get_authenticators(self):
        action = getattr(self, "action", None)
        classes = self.authentication_action_classes.get(action, self.authentication_classes)
        return [cls() for cls in classes]

    def get_throttles(self):
        action = getattr(self, "action", None)
        classes = self.throttle_action_classes.get(action, self.throttle_classes)
        return [cls() for cls in classes]

    # -------------------- Actions --------------------
    @action(detail=False, methods=["get"], url_path="csrf", url_name="csrf")
    @method_decorator(ensure_csrf_cookie)
    def csrf(self, request, *args, **kwargs):
        """
        Public endpoint used by the FE to seed the csrftoken cookie AND to return
        the token value so the FE can send it in X-CSRFToken for cross-site POSTs.
        """
        token = get_token(request)  # <— NEW
        return api_response(
            request,
            data={"ok": True, "csrfToken": token},  # <— include token
            status_code=status.HTTP_200_OK,
            message="CSRF cookie set",
        )

    @action(detail=False, methods=["post"], url_path="register", url_name="register")
    @transaction.atomic
    def register(self, request, *args, **kwargs):
        """
        Body: {"email": "...", "password": "..."}
        Creates the user and sends OTP (no tokens yet).
        """
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()

        payload = {
            "id": str(user.pk),
            "username": user.username,
            "email": user.email,
            "date_joined": user.date_joined,
        }
        return api_response(
            request,
            data=payload,
            status_code=status.HTTP_201_CREATED,
            message="User registered. OTP sent to email.",
        )

    @action(detail=False, methods=["post"], url_path="login", url_name="login")
    def login(self, request, *args, **kwargs):
        """
        Body: {"email": "...", "password": "..."}
        Validates credentials, returns access in JSON, sets refresh in HttpOnly cookie.
        """
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)

        payload = {
            "id": str(user.pk),
            "username": user.username,
            "email": user.email,
            "access": access,  # access ONLY in body
        }
        resp = api_response(
            request,
            data=payload,
            status_code=status.HTTP_200_OK,
            message="Logged in",
        )
        _set_refresh_cookie(resp, refresh)
        return resp

    @action(detail=False, methods=["post"], url_path="email-login", url_name="email_login")
    def email_login(self, request, *args, **kwargs):
        """
        Passwordless login.
        Body: {"email": "..."}
        If the email exists in the DB and the account is active,
        generates short OTP, caches it, and sends via mailjet.
        """
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.validated_data["user"]
        email = user.email.strip().lower()

        otp = generate_otp(4)

        cache_key = f"auth_otp_{email}"
        cache.set(cache_key, {"otp": otp}, timeout=600)  # 10 minutes
        print(f"DEBUG - Storing in cache for login: Key='{cache_key}', Data={{'otp': '{otp}'}}")

        send_otp_email(to_email=email, otp=otp)

        return api_response(
            request,
            data={"email": email},
            status_code=status.HTTP_200_OK,
            message="OTP sent to email for login.",
        )

    @action(detail=False, methods=["post"], url_path="email-signup", url_name="email_signup")
    def email_signup(self, request, *args, **kwargs):
        """
        Passwordless signup.
        Validates email. Generates short OTP, caches it, and sends via mailjet.
        """
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].strip().lower()

        otp = generate_otp(4)

        cache_key = f"auth_otp_{email}"
        cache.set(cache_key, {"otp": otp}, timeout=600)  # 10 minutes
        print(f"DEBUG - Storing in cache for signup: Key='{cache_key}', Data={{'otp': '{otp}'}}")

        send_otp_email(to_email=email, otp=otp)

        return api_response(
            request,
            data={"email": email},
            status_code=status.HTTP_200_OK,
            message="OTP sent to email.",
        )

    @action(detail=False, methods=["get", "patch"], url_path="me", url_name="me")
    def me(self, request, *args, **kwargs):
        """
        GET   -> return current user's profile
        PATCH -> partial update (username, name, bio, location, birth_date, avatar, etc.)
        """
        if request.method == "GET":
            ser = UserDetailSerializer(request.user, context={"request": request})
            return api_response(request, data=ser.data, status_code=status.HTTP_200_OK, message="Current user")

        # PATCH
        ser = UserUpdateSerializer(
            instance=request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        ser.is_valid(raise_exception=True)
        user = ser.save()

        out = UserDetailSerializer(user, context={"request": request}).data
        return api_response(request, data=out, status_code=status.HTTP_200_OK, message="Profile updated")


    @action(detail=False, methods=["post"], url_path="verify-otp", url_name="verify_otp")
    @transaction.atomic
    def verify_otp(self, request, *args, **kwargs):
        """
        Body: {"email": "...", "otp": 1234}
        On success:
          - Validates OTP against cache
          - Creates user if they don't exist
          - issues tokens
        """
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)

        email = ser.validated_data["email"]

        user = User._default_manager.filter(email__iexact=email).first()
        if not user:
            local_part = email.split("@", 1)[0] if "@" in email else email
            username = _generate_unique_username(local_part)
            
            user = User(username=username, email=email)
            user.set_unusable_password()
            user.save()

        # Remove used OTP from cache
        cache.delete(f"auth_otp_{email}")

        # Mint tokens
        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)

        payload = {
            "id": str(user.pk),
            "username": getattr(user, "username", None),
            "email": user.email,
            "verified": True,
            "access": access,
        }

        resp = api_response(
            request,
            data=payload,
            status_code=status.HTTP_200_OK,
            message="Account verified and logged in.",
        )
        _set_refresh_cookie(resp, refresh)
        return resp

    @action(
        detail=False,
        methods=["post"],
        url_path="refresh",
        url_name="refresh",
        permission_classes=[AllowAny],
        authentication_classes=[],  # cookie-based, not access-based
    )
    def refresh(self, request, *args, **kwargs):
        """
        Read refresh from HttpOnly cookie, rotate & blacklist, return new access in JSON,
        set new refresh cookie. Requires CSRF in prod (FE must send X-CSRFToken).
        """
        cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "ahara_rt")
        raw_refresh = request.COOKIES.get(cookie_name)
        if not raw_refresh:
            raise AuthenticationFailed("No refresh cookie present.")

        try:
            old_refresh = RefreshToken(raw_refresh)
        except TokenError:
            raise AuthenticationFailed("Invalid refresh token.")

        user_id = old_refresh.get("user_id")
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise AuthenticationFailed("User no longer exists.")

        # Rotate refresh & issue new access
        new_refresh = RefreshToken.for_user(user)
        new_access = new_refresh.access_token

        # Blacklist the old refresh (requires token_blacklist app)
        try:
            old_refresh.blacklist()
        except Exception:
            pass

        resp = api_response(
            request,
            data={"access": str(new_access)},
            status_code=status.HTTP_200_OK,
            message="Token refreshed",
        )
        _set_refresh_cookie(resp, new_refresh)
        return resp

    @action(detail=False, methods=["post"], url_path="logout", url_name="logout")
    def logout(self, request, *args, **kwargs):
        """
        Blacklist current refresh (if present) and clear cookie.
        """
        cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "ahara_rt")
        raw_refresh = request.COOKIES.get(cookie_name)

        resp = api_response(
            request,
            data={"ok": True},
            status_code=status.HTTP_200_OK,
            message="Logged out",
        )
        if raw_refresh:
            try:
                RefreshToken(raw_refresh).blacklist()
            except Exception:
                pass
        _clear_refresh_cookie(resp)
        return resp