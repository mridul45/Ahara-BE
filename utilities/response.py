# ahara/common/responses.py
from __future__ import annotations

from http import HTTPStatus
from django.utils.timezone import now
from rest_framework.response import Response
from rest_framework import status as drf_status
from rest_framework.views import exception_handler


def _build_payload(request, *, data=None, status_code=drf_status.HTTP_200_OK,
                   message: str | None = None, errors=None, meta=None):
    resolver = getattr(request, "resolver_match", None)
    view_name = getattr(resolver, "view_name", None)
    return {
        "endpoint": {
            "path": getattr(request, "path", None),
            "method": getattr(request, "method", None),
            "view": view_name,
            "query": getattr(request, "META", {}).get("QUERY_STRING", ""),
        },
        "status": {
            "code": int(status_code),
            "text": HTTPStatus(status_code).phrase if status_code in HTTPStatus._value2member_map_ else "",
            "message": message or "",
        },
        "data": data,
        "errors": errors,
        "meta": meta,
        "timestamp": now().isoformat(),
    }


class ApiResponse(Response):
    """
    Drop-in Response that enforces a consistent payload shape.
    Usage:
        return ApiResponse(request, data=..., status_code=201, message="User created")
    """
    def __init__(self, request, *, data=None, status_code=drf_status.HTTP_200_OK,
                 message: str | None = None, errors=None, meta=None, headers=None,
                 content_type=None):
        super().__init__(
            _build_payload(request, data=data, status_code=status_code, message=message, errors=errors, meta=meta),
            status=status_code, headers=headers, content_type=content_type
        )


def api_response(request, *, data=None, status_code=drf_status.HTTP_200_OK,
                 message: str | None = None, errors=None, meta=None, headers=None):
    """Functional alias if you prefer a function call."""
    return ApiResponse(request, data=data, status_code=status_code, message=message, errors=errors, meta=meta, headers=headers)


# Optional: unify error responses into the same template
def unified_exception_handler(exc, context):
    """
    Plug this into REST_FRAMEWORK['EXCEPTION_HANDLER'] to ensure errors
    also follow the same envelope.
    """
    drf_resp = exception_handler(exc, context)
    request = context.get("request")

    # DRF handled (e.g., ValidationError, NotAuthenticated, etc.)
    if drf_resp is not None:
        status_code = drf_resp.status_code
        errors = drf_resp.data
        message = (errors.get("detail") if isinstance(errors, dict) else None) or ""
        drf_resp.data = _build_payload(request, data=None, status_code=status_code, message=message, errors=errors, meta=None)
        return drf_resp

    # Unhandled -> 500
    return ApiResponse(
        request,
        data=None,
        status_code=drf_status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="Internal Server Error",
        errors={"detail": str(exc)},
    )
