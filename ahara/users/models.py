# ahara/users/models.py
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.utils import timezone
from .managers import UserManager
from django.utils.translation import gettext_lazy as _
from utilities.enums import GenderEnum, StateEnum
from utilities.storages import ImageKitStorage   # <-- add
from utilities.imagekit_client import imagekit   # <-- for helper method
import posixpath
from django.conf import settings


username_validator = UnicodeUsernameValidator()

class User(AbstractBaseUser, PermissionsMixin):

    ''' Default Fields in custom user model '''
    email = models.EmailField(unique=True)
    username = models.CharField(
        max_length=150,
        unique=True,
        null=True,
        blank=True,
        validators=[username_validator],
        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
    )
    first_name = models.CharField(max_length=150, blank=True)
    last_name  = models.CharField(max_length=150, blank=True)
    is_staff   = models.BooleanField(default=False)
    is_active  = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    ''' Custom Fields '''

    bio = models.TextField(_("Biography"),null=True, blank=True)
    gender = models.CharField(_("Gender"), max_length=17, choices=[(tag.value, tag.value) for tag in GenderEnum], null=True, blank=True)
    city = models.CharField(_("City of Residence"),max_length=100, null=True, blank=True)
    state = models.CharField(_("Current State"), max_length=42, choices=[(tag.value, tag.value) for tag in StateEnum], null=True, blank=True)
    country = models.CharField(_("Country of Residence"), max_length=100, default="India", null=True, blank=True)
    birth_date = models.DateField(_("Birth Date"), null=True, blank=True)

    ''' File Fields '''

    avatar = models.ImageField(
        _("Avatar"),
        storage=ImageKitStorage(),          # <-- goes straight to ImageKit
        upload_to="users/avatars",          # becomes the folder on ImageKit
        max_length=1000,
        null=True,
        blank=True,
    )
    imagekit_file_id = models.CharField(     # useful for permanent deletes
        _("ImageKit File ID"),
        max_length=1000,
        null=True,
        blank=True,
        editable=False,
    )

    objects = UserManager()

    EMAIL_FIELD    = "email"
    USERNAME_FIELD = "username"      # primary login field
    REQUIRED_FIELDS = ["email"]  # asked when createsuperuser

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        ordering = ["-date_joined"]

    def __str__(self):
        return self.username or self.email
    
    def avatar_url(self, w=256, h=256, signed=None, expire=3600):
        """
        Return a (optionally signed) transformed ImageKit URL for the avatar.
        If `signed` is None, we read a settings toggle; else use the explicit bool.
        """
        if not self.avatar:
            return None

        # local import avoids circulars

        if signed is None:
            signed = bool(getattr(settings, "IMAGEKIT_SIGNED_URLS", False))

        params = {
            "path": "/" + self.avatar.name,  # e.g. /users/avatars/abc.jpg
            "transformation": [
                {"width": str(w), "height": str(h), "crop": "at_max", "radius": "max"}
            ],
        }
        if signed:
            params["signed"] = True
            params["expire_seconds"] = int(expire)

        return imagekit.url(params)
    
    @property
    def full_name(self):
        s = f"{self.first_name} {self.last_name}".strip()
        return s or self.username or self.email