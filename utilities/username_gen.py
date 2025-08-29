import re
from django.contrib.auth import get_user_model

User = get_user_model()

def _generate_unique_username(base: str) -> str:
    """
    Build a username from `base` (usually email local-part), keeping only
    characters allowed by Django's default username validator:
    letters, digits and @/./+/-/_ .
    """
    base = (base or "user").strip().lower()
    # keep letters, digits and @ . + - _
    base = re.sub(r"[^A-Za-z0-9@.+\-_]", "_", base) or "user"

    # If it's free, use it; else append a number suffix.
    if not User.objects.filter(username=base).exists():
        return base
    i = 2
    while True:
        cand = f"{base}{i}"
        if not User.objects.filter(username=cand).exists():
            return cand
        i += 1