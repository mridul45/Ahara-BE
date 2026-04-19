from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import Memory

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def update_memory_user_snapshot(sender, instance, created, **kwargs):
    """
    Update the user_snapshot in the Memory model when the User is updated.
    """
    if created:
        Memory.objects.create(user=instance)
        return

    # Build the new snapshot
    user_snapshot = {
        "id": instance.id,
        "first_name": instance.first_name,
        "last_name": instance.last_name,
        "bio": getattr(instance, "bio", ""),
        "gender": getattr(instance, "gender", ""),
        "city": getattr(instance, "city", ""),
        "state": getattr(instance, "state", ""),
        "country": getattr(instance, "country", ""),
        "birth_date": str(instance.birth_date) if getattr(instance, "birth_date", None) else None,
    }

    # OneToOneField — at most one Memory per user
    try:
        memory = Memory.objects.get(user=instance)
    except Memory.DoesNotExist:
        return

    memory.user_snapshot = user_snapshot
    memory.save(update_fields=["user_snapshot", "updated_at"])
