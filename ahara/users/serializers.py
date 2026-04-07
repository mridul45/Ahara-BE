# ahara/users/serializers.py
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.validators import UniqueValidator
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

from rest_framework_simplejwt.serializers import TokenRefreshSerializer

from django.core.cache import cache
from utilities.username_gen import _generate_unique_username

User = get_user_model()


class UserCredsSerializer(serializers.ModelSerializer):
    """
    Minimal signup serializer:
      - input: email, password
      - validates: unique & well-formed email, password via Django validators
      - creates user with a unique, auto-generated username from email local-part
    """

    email = serializers.EmailField(
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                message="A user with this email already exists.",
            ),
        ],
    )
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ("email", "password")

    def validate_email(self, value: str) -> str:
        # Normalize email; BaseUserManager.normalize_email also lowercases domain.
        return value.strip().lower()

    def validate_password(self, value: str) -> str:
        # Run AUTH_PASSWORD_VALIDATORS
        validate_password(value)
        return value

    def create(self, validated_data):
        email = validated_data["email"]
        password = validated_data["password"]

        # Derive username from email local-part to satisfy USERNAME_FIELD='username'
        local_part = email.split("@", 1)[0] if "@" in email else email
        username = _generate_unique_username(local_part)

        # Prefer the manager's create_user if present (handles normalization, etc.)
        if hasattr(User.objects, "create_user"):
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            user.save()

        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        try:
            user = User._default_manager.get(email__iexact=email)
        except User.DoesNotExist:
            raise AuthenticationFailed("Invalid credentials.")

        if not user.is_active:
            raise AuthenticationFailed("User account is disabled.")

        if not user.check_password(password):
            raise AuthenticationFailed("Invalid credentials.")

        attrs["user"] = user
        return attrs


class EmailOnlyLoginSerializer(serializers.Serializer):
    """
    Passwordless login: accepts only an email address.
    If the email exists and the account is active, passes the user forward
    for token generation. No password check is performed.
    """
    email = serializers.EmailField()

    def validate(self, attrs):
        email = attrs.get("email", "").strip().lower()

        try:
            user = User._default_manager.get(email__iexact=email)
        except User.DoesNotExist:
            raise AuthenticationFailed("No account found with this email.")

        if not user.is_active:
            raise AuthenticationFailed("User account is disabled.")

        attrs["user"] = user
        return attrs


class EmailOnlySignupSerializer(serializers.Serializer):
    """
    Passwordless signup: accepts only an email address.
    Rejects the request if the email is already registered.
    Creation is deferred to OTP verification.
    """
    email = serializers.EmailField()

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if User._default_manager.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value


class UserDetailSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        # Include the fields you want to expose (exclude password, is_staff, is_superuser)
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "bio",
            "gender",
            "city",
            "state",
            "country",
            "birth_date",
            "date_joined",
            "is_active",
            "avatar_url",
        ]
        read_only_fields = fields

    def get_avatar_url(self, obj):
        # Uses your model helper; returns None if no avatar
        try:
            return obj.avatar_url()  # you can tune w/h if you like
        except Exception:
            return None


class VerifyOtpSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

    def validate(self, attrs):
        email = attrs.get("email", "").strip().lower()
        otp = attrs.get("otp")

        # 1. Check cache
        cache_key = f"signup_otp_{email}"
        cached_data = cache.get(cache_key)

        if not cached_data:
            raise AuthenticationFailed("OTP has expired or was not sent.")

        if str(cached_data.get("otp")) != str(otp):
            raise AuthenticationFailed("Invalid OTP.")

        # Valid OTP, we will create the user in the view (or skip if exists in other flows).
        attrs["email"] = email
        return attrs
    

class UserUpdateSerializer(serializers.ModelSerializer):
    # Allow avatar upload via multipart/form-data
    avatar = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "bio",
            "gender",
            "city",
            "state",
            "country",
            "birth_date",
            "avatar",
        ]
        extra_kwargs = {
            "username": {"required": False, "allow_null": True, "allow_blank": True},
            "birth_date": {"required": False},
        }

    def validate_username(self, value):
        if not value:
            return value
        qs = User.objects.filter(username=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This username is already taken.")
        return value