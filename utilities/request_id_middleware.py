"""
Request-ID middleware.

Generates a UUID-based request ID for every request, propagates it via the
X-Request-ID header (honouring the client-supplied value if present), and
injects it into the logging context so every log line emitted during that
request carries the same ID.

Usage in MIDDLEWARE (add near the top, before any logging-emitting middlewares):
    "utilities.request_id_middleware.RequestIdMiddleware",
"""

import logging
import uuid

logger = logging.getLogger("utilities.request_id")


class RequestIdFilter(logging.Filter):
    """Logging filter that injects the current request ID into log records."""

    def filter(self, record):
        record.request_id = getattr(_local, "request_id", "-")
        return True


class _Local:
    """Minimal thread/async-local storage for the request ID."""
    __slots__ = ("request_id",)


_local = _Local()


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Use client-supplied ID (e.g. from mobile app) or generate a fresh one.
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        _local.request_id = request_id
        request.request_id = request_id

        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response
