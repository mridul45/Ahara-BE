from django.conf import settings
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver
from utilities.cache_keys import memory_long_term, memory_snapshot
from .models import Memory

# ── LTM cache invalidation ────────────────────────────────────────────────────

@receiver(post_save, sender=Memory)
def _invalidate_ltm_cache(sender, instance, **kwargs):
    """Bust the LTM read cache whenever the Memory row is saved by any code path."""
    cache.delete(memory_long_term(instance.user_id))
    cache.delete(memory_snapshot(instance.user_id))


# ── User profile → memory snapshot sync ──────────────────────────────────────

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def update_memory_user_snapshot(sender, instance, created, **kwargs):
    """
    Update the user_snapshot in the Memory model when the User is updated.
    """
    if created:
        # Build the snapshot immediately using the committed user fields so the
        # newly created Memory row is never left with an empty user_snapshot.
        snapshot = {
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
        Memory.objects.create(user=instance, user_snapshot=snapshot)
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
