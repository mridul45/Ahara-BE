from django.db import models
from django.conf import settings
from django.core.cache import cache

# Create your models here.

class Memory(models.Model):

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memories")
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Memory"
        verbose_name_plural = "Memories"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Memory for {self.user} - {self.created_at}"

    def save(self, *args, **kwargs):
        if not self.pk:
            user_snapshot = {
                "id": self.user.id,
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "bio": getattr(self.user, "bio", ""),
                "gender": getattr(self.user, "gender", ""),
                "city": getattr(self.user, "city", ""),
                "state": getattr(self.user, "state", ""),
                "country": getattr(self.user, "country", ""),
                "birth_date": str(self.user.birth_date) if getattr(self.user, "birth_date", None) else None,
            }
            self.data = {
                "user_snapshot": user_snapshot,
                "chat": {},
            }
        super().save(*args, **kwargs)
        # Invalidate cache so next read refetches from DB
        cache.delete(f"user_memory_data_{self.user.id}")