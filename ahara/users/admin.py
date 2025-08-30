from allauth.account.decorators import secure_admin_login
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .forms import UserAdminChangeForm
from .forms import UserAdminCreationForm
from .models import User,Otp

if getattr(settings, "DJANGO_ADMIN_FORCE_ALLAUTH", False):
    admin.autodiscover()
    admin.site.login = secure_admin_login(admin.site.login)  # type: ignore[method-assign]


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = UserAdminCreationForm
    form = UserAdminChangeForm
    model = User

    list_display = (
        "email",
        "username",
        "full_name_col",
        "avatar_preview",  # thumbnail
        "is_staff",
        "is_superuser",
        "date_joined",
        "bio",
        "gender",
        "state",
        "country",
        "birth_date",
    )
    list_filter = (
        "is_staff",
        "is_superuser",
        "is_active",
        "gender",
        "state",
        "country",
        "birth_date",
    )
    ordering = ("-date_joined",)
    search_fields = (
        "email",
        "username",
        "first_name",
        "last_name",
        "gender",
        "state",
        "country",
        "birth_date",
    )

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        (
            _("Personal info"),
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "bio",
                    "gender",
                    "state",
                    "country",
                ),
            },
        ),
        (
            _("Avatar"),
            {
                "fields": ("avatar", "avatar_preview", "imagekit_file_id"),
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined", "birth_date")}),
    )

    # allow avatar upload when creating a user too
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "username",
                    "first_name",
                    "last_name",
                    "password1",
                    "password2",
                    "avatar",  # <--- added here
                    "is_active",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )

    # metadata/preview read-only
    readonly_fields = (
        "date_joined",
        "full_name_readonly",
        "imagekit_file_id",
        "avatar_preview",
    )

    @admin.display(ordering="first_name", description="Full name")
    def full_name_col(self, obj: User):
        return obj.full_name

    @admin.display(description="Full name")
    def full_name_readonly(self, obj: User):
        return obj.full_name

    @admin.display(description="Avatar")
    def avatar_preview(self, obj: User):
        """
        Renders a small round thumbnail linking to a larger image.
        Respects IMAGEKIT_SIGNED_URLS if you keep files private.
        """
        if not obj or not getattr(obj, "avatar", None):
            return "-"

        try:
            signed = bool(getattr(settings, "IMAGEKIT_SIGNED_URLS", False))
            thumb = obj.avatar_url(64, 64, signed=signed)
            full = obj.avatar_url(256, 256, signed=signed)
        except Exception:
            return "-"

        if not thumb:
            return "-"

        return format_html(
            '<a href="{}" target="_blank" rel="noopener">'
            '<img src="{}" style="width:40px;height:40px;border-radius:50%;object-fit:cover;" />'
            "</a>",
            full or thumb,
            thumb,
        )


@admin.register(Otp)
class OtpAdmin(admin.ModelAdmin):
    list_display = ("user", "otp", "created_at")