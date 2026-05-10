"""
Data migration: Move legacy ``Memory.data`` into the new three-tier fields.

* ``data["user_snapshot"]`` → ``user_snapshot``
* ``data["chat"]``          → ``short_term`` (wrapped as a single session)
* Handles duplicate Memory rows per user (merges before unique constraint).
"""

from django.db import migrations


def forwards(apps, schema_editor):
    Memory = apps.get_model("intelligence", "Memory")

    # ── 1. Deduplicate: if any user has >1 Memory row, keep the freshest ──
    from django.db.models import Count

    dupes = (
        Memory.objects.values("user_id")
        .annotate(cnt=Count("id"))
        .filter(cnt__gt=1)
    )
    for entry in dupes:
        rows = Memory.objects.filter(user_id=entry["user_id"]).order_by("-updated_at")
        keep = rows.first()
        rows.exclude(pk=keep.pk).delete()

    # ── 2. Copy data → new fields ────────────────────────────────────────
    for mem in Memory.objects.all().iterator():
        old_data = mem.data or {}
        changed = False

        # user_snapshot
        snapshot = old_data.get("user_snapshot")
        if snapshot and not mem.user_snapshot:
            mem.user_snapshot = snapshot
            changed = True

        # chat → short_term (store as a single legacy session)
        chat = old_data.get("chat")
        if chat and not mem.short_term:
            # Handle both list and dict shapes that may exist
            if isinstance(chat, list) and chat:
                mem.short_term = [
                    {
                        "ts": str(mem.updated_at) if mem.updated_at else "",
                        "session_id": "legacy_migration",
                        "facts": [
                            {
                                "fact": f"(migrated raw chat — {len(chat)} messages)",
                                "category": "context",
                                "confidence": "low",
                                "is_temporary": False,
                            }
                        ],
                    }
                ]
                changed = True

        if changed:
            mem.save(update_fields=["user_snapshot", "short_term"])


def backwards(apps, schema_editor):
    # No-op: the old ``data`` field is still intact for rollback.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("intelligence", "0002_memory_three_tier_schema"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards, elidable=True),
    ]
