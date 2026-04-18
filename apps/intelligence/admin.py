from django.contrib import admin
from .models import Memory


@admin.register(Memory)
class MemoryAdmin(admin.ModelAdmin):
    list_display = ("user", "short_term_count", "ltm_fact_count", "sessions_since_consolidation", "version", "updated_at")
    search_fields = ("user__username", "user__email")
    list_filter = ("created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at", "version", "sessions_since_consolidation", "last_consolidation_at")

    fieldsets = (
        (None, {
            "fields": ("user",),
        }),
        ("Tier 3 — Long-Term Memory", {
            "fields": ("long_term",),
            "classes": ("collapse",),
        }),
        ("Tier 2 — Short-Term Memory", {
            "fields": ("short_term",),
            "classes": ("collapse",),
        }),
        ("User Profile Snapshot", {
            "fields": ("user_snapshot",),
            "classes": ("collapse",),
        }),
        ("Consolidation Metadata", {
            "fields": ("sessions_since_consolidation", "last_consolidation_at", "version"),
        }),
        ("Deprecated (old format)", {
            "fields": ("data",),
            "classes": ("collapse",),
            "description": "Legacy field — will be removed in a future migration.",
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
        }),
    )

    @admin.display(description="STM Sessions")
    def short_term_count(self, obj):
        stm = obj.short_term
        return len(stm) if isinstance(stm, list) else 0

    @admin.display(description="LTM Facts")
    def ltm_fact_count(self, obj):
        ltm = obj.long_term
        if not isinstance(ltm, dict):
            return 0
        return sum(len(v) for v in ltm.values() if isinstance(v, list))