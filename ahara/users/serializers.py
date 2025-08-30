# ahara/users/serializers.py
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.validators import UniqueValidator
from .models import Otp

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
    otp = serializers.IntegerField()

    def validate(self, attrs):
        email = attrs.get("email")
        otp = attrs.get("otp")

        try:
            user = User._default_manager.get(email__iexact=email)
        except User.DoesNotExist:
            raise AuthenticationFailed("Invalid credentials.")

        try:
            otp_instance = Otp.objects.filter(user=user).latest('created_at')
        except Otp.DoesNotExist:
            raise AuthenticationFailed("OTP not found for this user.")

        # Check if OTP is older than 10 minutes
        if otp_instance.created_at < timezone.now() - timezone.timedelta(minutes=10):
            otp_instance.delete()
            raise AuthenticationFailed("OTP has expired.")

        if otp_instance.otp != otp:
            raise AuthenticationFailed("Invalid OTP.")

        attrs["user"] = user
        attrs["otp_instance"] = otp_instance
        return attrs