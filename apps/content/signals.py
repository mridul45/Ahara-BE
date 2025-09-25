import posixpath
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from utilities.imagekit_client import imagekit
from .models import Video


def _get_file_id(folder, filename):
    try:
        files = imagekit.list_files({"path": folder + "/", "name": filename, "limit": 1})
        items = getattr(files, "list", None) or getattr(files, "results", None) or []
        if items:
            return getattr(items[0], "file_id", None) or items[0].get("fileId")
    except Exception:
        return None


def _delete_from_imagekit(file_id, field_storage, field_name):
    try:
        if file_id:
            imagekit.delete_file(file_id)
        elif field_name:
            field_storage.delete(field_name)
    except Exception:
        pass


@receiver(pre_save, sender=Video)
def _remember_old_files(sender, instance, **kwargs):
    if not instance.pk:
        instance._old_files = {}
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        old = None
    instance._old_files = {}
    if old:
        if old.video and (not instance.video or old.video.name != instance.video.name):
            instance._old_files["video"] = (old.video_file_id, old.video.name)
        if old.thumbnail and (not instance.thumbnail or old.thumbnail.name != instance.thumbnail.name):
            instance._old_files["thumbnail"] = (old.thumbnail_file_id, old.thumbnail.name)
        if old.subtitles and (not instance.subtitles or old.subtitles.name != instance.subtitles.name):
            instance._old_files["subtitles"] = (old.subtitles_file_id, old.subtitles.name)
        if old.transcript and (not instance.transcript or old.transcript.name != instance.transcript.name):
            instance._old_files["transcript"] = (old.transcript_file_id, old.transcript.name)


@receiver(post_save, sender=Video)
def _backfill_file_ids_and_cleanup(sender, instance, created, **kwargs):
    # Backfill file IDs
    if instance.video and not instance.video_file_id:
        folder, filename = posixpath.split("/" + instance.video.name)
        fid = _get_file_id(folder, filename)
        if fid:
            sender.objects.filter(pk=instance.pk).update(video_file_id=fid)

    if instance.thumbnail and not instance.thumbnail_file_id:
        folder, filename = posixpath.split("/" + instance.thumbnail.name)
        fid = _get_file_id(folder, filename)
        if fid:
            sender.objects.filter(pk=instance.pk).update(thumbnail_file_id=fid)

    if instance.subtitles and not instance.subtitles_file_id:
        folder, filename = posixpath.split("/" + instance.subtitles.name)
        fid = _get_file_id(folder, filename)
        if fid:
            sender.objects.filter(pk=instance.pk).update(subtitles_file_id=fid)

    if instance.transcript and not instance.transcript_file_id:
        folder, filename = posixpath.split("/" + instance.transcript.name)
        fid = _get_file_id(folder, filename)
        if fid:
            sender.objects.filter(pk=instance.pk).update(transcript_file_id=fid)

    # Cleanup replaced old files
    for field, (fid, name) in getattr(instance, "_old_files", {}).items():
        storage = getattr(instance, field).storage if getattr(instance, field) else None
        _delete_from_imagekit(fid, storage, name)


@receiver(post_delete, sender=Video)
def _delete_files_on_video_delete(sender, instance, **kwargs):
    if instance.video or instance.video_file_id:
        _delete_from_imagekit(instance.video_file_id, instance.video.storage, instance.video.name if instance.video else None)
    if instance.thumbnail or instance.thumbnail_file_id:
        _delete_from_imagekit(instance.thumbnail_file_id, instance.thumbnail.storage, instance.thumbnail.name if instance.thumbnail else None)
    if instance.subtitles or instance.subtitles_file_id:
        _delete_from_imagekit(instance.subtitles_file_id, instance.subtitles.storage, instance.subtitles.name if instance.subtitles else None)
    if instance.transcript or instance.transcript_file_id:
        _delete_from_imagekit(instance.transcript_file_id, instance.transcript.storage, instance.transcript.name if instance.transcript else None)
