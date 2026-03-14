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
        return

    # Find all memories associated with this user
    memories = Memory.objects.filter(user=instance)
    
    if not memories.exists():
        return

    # Construct the new snapshot
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

    # Update each memory
    for memory in memories:
        if "user_snapshot" in memory.data:
            memory.data["user_snapshot"] = user_snapshot
            memory.save(update_fields=["data", "updated_at"])
        # If user_snapshot doesn't exist (legacy data?), we might want to create it or skip.
        # Given the create logic, it should exist. 
        # But if the 'data' structure was different before, we might just want to set it/update it if the key exists or just update it regardless?
        # The prompt says "it will be edited in the user_snapshot".
        # I'll update it safely.
        else:
             # Initialize if missing (though save() handles it on creation, old rows might not have it)
            current_data = memory.data if memory.data else {}
            current_data["user_snapshot"] = user_snapshot
            memory.data = current_data
            memory.save(update_fields=["data", "updated_at"])
