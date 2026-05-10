"""
Liveness and readiness check endpoints.

/health/  — liveness: process is alive (no DB/cache required)
/ready/   — readiness: DB and Redis/cache are reachable
"""

from django.core.cache import cache
from django.db import connection, OperationalError
from django.http import JsonResponse
from django.views import View


class HealthView(View):
    """Liveness probe — always returns 200 if the process is alive."""

    def get(self, request):
        return JsonResponse({"status": "ok"})


class ReadyView(View):
    """Readiness probe — checks DB connectivity and cache reachability."""

    def get(self, request):
        errors = {}

        # Check database
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except OperationalError as exc:
            errors["db"] = str(exc)

        # Check cache (write + read a sentinel key)
        try:
            cache.set("ahara:ready:ping", "1", timeout=5)
            if cache.get("ahara:ready:ping") != "1":
                errors["cache"] = "get after set returned wrong value"
        except Exception as exc:
            errors["cache"] = str(exc)

        if errors:
            return JsonResponse({"status": "down", "errors": errors}, status=503)
        return JsonResponse({"status": "ok"})
