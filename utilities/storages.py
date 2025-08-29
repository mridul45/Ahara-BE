# utilities/storages.py (alternate save)
import posixpath, tempfile, requests
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible
from django.core.exceptions import ValidationError
from django.conf import settings

UPLOAD_URL = "https://upload.imagekit.io/api/v1/files/upload"

@deconstructible
class ImageKitStorage(Storage):
    def _split(self, name: str):
        name = name.replace("\\", "/")
        folder, filename = posixpath.split(name)
        if not folder:
            folder = "/"
        if not folder.startswith("/"):
            folder = "/" + folder
        if not folder.endswith("/"):
            folder += "/"
        return folder, filename

    def _full_path(self, name: str):
        name = name.replace("\\", "/")
        return name if name.startswith("/") else "/" + name

    def save(self, name, content, max_length=None):
        folder, filename = self._split(name)

        with tempfile.NamedTemporaryFile(suffix=posixpath.splitext(filename)[1] or ".bin") as tmp:
            if hasattr(content, "multiple_chunks") and content.multiple_chunks():
                for chunk in content.chunks():
                    tmp.write(chunk)
            else:
                try:
                    if hasattr(content, "seek"):
                        content.seek(0)
                except Exception:
                    pass
                data = content.read()
                if not data:
                    raise ValidationError("Avatar upload seems empty.")
                tmp.write(data)

            tmp.flush()
            tmp.seek(0)

            files = {"file": (filename, tmp, "application/octet-stream")}
            data = {
                "fileName": filename,
                "folder": folder,
                "useUniqueFileName": "true",
                "isPrivateFile": "true" if getattr(settings, "IMAGEKIT_PRIVATE_FILES", False) else "false",
            }

            # Basic auth: private key as username, blank password
            resp = requests.post(UPLOAD_URL, files=files, data=data,
                                 auth=(settings.IMAGEKIT_PRIVATE_KEY, ""))
            resp.raise_for_status()
            res = resp.json()
            # res["filePath"] like "/users/avatars/abc.jpg"
            return res["filePath"].lstrip("/")

    def url(self, name):
        params = {"path": self._full_path(name)}
        if bool(getattr(settings, "IMAGEKIT_SIGNED_URLS", False)):
            from .imagekit_client import imagekit
            params["signed"] = True
            params["expire_seconds"] = int(getattr(settings, "IMAGEKIT_SIGNED_URL_TTL", 3600))
            return imagekit.url(params)
        return f'{settings.IMAGEKIT_URL_ENDPOINT}{self._full_path(name)}'

    def exists(self, name): return False
    def delete(self, name): pass  # keep your previous delete if you need it
