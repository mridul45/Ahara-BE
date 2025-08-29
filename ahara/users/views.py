# ahara/users/views.py
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import UserCredsSerializer,LoginSerializer,UserDetailSerializer
from .api_utils.throtles import SignupThrottle,LoginIPThrottle,LoginUserThrottle  # your file name/spelling
from utilities.response import api_response

User = get_user_model()


class AuthViewSet(viewsets.GenericViewSet):
    """
    ViewSet using per-action maps for serializer, permissions, auth, and throttles.
    Routes (via router under /users/):
      POST /users/auth/register/  -> public signup (throttled) + returns JWTs
    """
    queryset = User._default_manager.all()

    # ---- Defaults (applied when an action isn't in the maps) ----
    serializer_class = UserCredsSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    throttle_classes = []

    # ---- Per-action maps ----
    serializer_action_classes = {
        "register": UserCredsSerializer,
        "login": LoginSerializer,
        "me": UserDetailSerializer,
    }
    permission_action_classes = {
        "register": [AllowAny],
        "login": [AllowAny],
        "me": [IsAuthenticated],
    }
    authentication_action_classes = {
        "register": [],  # open endpoint (skip JWT/Session parsing)
        "login": [],  # open endpoint (skip JWT/Session parsing)
        "me": [JWTAuthentication],  # require JWT for this endpoint
    }
    throttle_action_classes = {
        "register": [SignupThrottle],  # rate uses DEFAULT_THROTTLE_RATES['signup']
        "login": [LoginIPThrottle, LoginUserThrottle],  # rate uses DEFAULT_THROTTLE_RATES['login']
        "me": [],  # no throttling for this endpoint
    }

    # Ensure self.action is available before DRF asks for authenticators/permissions.
    def initialize_request(self, request, *args, **kwargs):
        if not hasattr(self, "action"):
            action_map = getattr(self, "action_map", None)  # set by the router
            if action_map:
                self.action = action_map.get(request.method.lower())
        return super().initialize_request(request, *args, **kwargs)

    # Safe helpers that read the maps using the (now early-set) action
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

    # ---- Actions ----
    @action(detail=False, methods=["post"], url_path="register", url_name="register")
    @transaction.atomic
    def register(self, request, *args, **kwargs):
        """
        Body: {"email": "...", "password": "..."}
        Creates the user and returns access/refresh tokens.
        """
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        payload = {
            "id": str(user.pk),
            "username": user.username,
            "email": user.email,
            "date_joined": user.date_joined,
            "tokens": {"refresh": str(refresh), "access": str(access)},
        }
        return api_response(
            request,
            data=payload,
            status_code=status.HTTP_201_CREATED,
            message="User registered",
        )
    

    @action(detail=False, methods=["post"], url_path="login", url_name="login")
    def login(self, request, *args, **kwargs):
        """
        Body: {"email": "...", "password": "..."}
        Validates credentials and returns a new JWT pair.
        """
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        payload = {
            "id": str(user.pk),
            "username": user.username,
            "email": user.email,
            "tokens": {"refresh": str(refresh), "access": str(access)},
        }
        return api_response(request, data=payload, status_code=status.HTTP_200_OK, message="Logged in")
    


    @action(detail=False, methods=["get"], url_path="me", url_name="me")
    def me(self, request, *args, **kwargs):
        """
        Requires: Authorization: Bearer <access-token>
        Returns authenticated user's profile data.
        """
        ser = self.get_serializer(request.user, context={"request": request})
        return api_response(
            request,
            data=ser.data,
            status_code=status.HTTP_200_OK,
            message="Current user",
        )