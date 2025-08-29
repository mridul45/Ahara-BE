# ahara/users/signals.py
import posixpath

from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.db.models.signals import pre_save
from django.dispatch import receiver

from utilities.imagekit_client import imagekit

from .models import User


@receiver(pre_save, sender=User)
def _remember_old_avatar(sender, instance: User, **kwargs):
    if not instance.pk:
        instance._old_avatar_name = None
        instance._old_file_id = None
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        old = None
    if old:
        changed = old.avatar and (
            not instance.avatar or old.avatar.name != instance.avatar.name
        )
        if changed:
            instance._old_avatar_name = old.avatar.name
            instance._old_file_id = old.imagekit_file_id


@receiver(post_save, sender=User)
def _backfill_file_id_and_cleanup(sender, instance: User, created, **kwargs):
    # Backfill fileId if we just uploaded a new avatar
    if instance.avatar and not instance.imagekit_file_id:
        folder, filename = posixpath.split("/" + instance.avatar.name)
        try:
            files = imagekit.list_files(
                {"path": folder + "/", "name": filename, "limit": 1}
            )
            items = (
                getattr(files, "list", None) or getattr(files, "results", None) or []
            )
            if items:
                file_id = getattr(items[0], "file_id", None) or items[0].get("fileId")
                if file_id:
                    sender.objects.filter(pk=instance.pk).update(
                        imagekit_file_id=file_id
                    )
        except Exception:
            pass

    # Delete the previously stored avatar on ImageKit, if any
    old_id = getattr(instance, "_old_file_id", None)
    old_name = getattr(instance, "_old_avatar_name", None)
    try:
        if old_id:
            imagekit.delete_file(old_id)  # server-side delete by fileId
        elif old_name:
            # fallback delete by path (uses storage.delete best-effort)
            instance._meta.get_field("avatar").storage.delete(old_name)
    except Exception:
        pass


@receiver(post_delete, sender=User)
def _delete_avatar_on_user_delete(sender, instance: User, **kwargs):
    try:
        if instance.imagekit_file_id:
            imagekit.delete_file(instance.imagekit_file_id)
        elif instance.avatar:
            instance._meta.get_field("avatar").storage.delete(instance.avatar.name)
    except Exception:
        pass
