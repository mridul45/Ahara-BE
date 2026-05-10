from django.conf import settings


def paginate_queryset(qs, request):
    """
    Slice *qs* according to ``?page`` and ``?page_size`` query params.

    Limits are read from ``settings.PAGINATION`` so they can be tuned per
    environment without touching view code:
        PAGINATION = {"PAGE_SIZE_DEFAULT": 20, "PAGE_SIZE_MAX": 100}

    Returns ``(page_queryset, meta_dict)`` where *meta_dict* has the shape:
        { page, page_size, total, has_next }

    Both params are clamped to safe ranges — invalid input never raises.
    """
    config = getattr(settings, "PAGINATION", {})
    default_size: int = config.get("PAGE_SIZE_DEFAULT", 20)
    max_size: int = config.get("PAGE_SIZE_MAX", 100)

    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    try:
        page_size = min(
            max(1, int(request.query_params.get("page_size", default_size))),
            max_size,
        )
    except (ValueError, TypeError):
        page_size = default_size

    total = qs.count()
    start = (page - 1) * page_size
    end = start + page_size

    return qs[start:end], {
        "page": page,
        "page_size": page_size,
        "total": total,
        "has_next": end < total,
    }
