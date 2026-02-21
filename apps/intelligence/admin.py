from django.contrib import admin
from .models import Memory

@admin.register(Memory)
class MemoryAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "updated_at")
    search_fields = ("user__username", "user__email")
    list_filter = ("created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")