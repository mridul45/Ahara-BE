"""
Custom logging filters for Ahara.
"""

import logging


class SlowQueryFilter(logging.Filter):
    """
    Only passes log records whose SQL execution time exceeds a threshold.

    Django's ``django.db.backends`` logger emits one DEBUG record per query.
    The record's ``duration`` attribute carries the elapsed time in milliseconds.
    This filter drops records below the threshold so the console only shows
    genuinely slow queries without flooding logs in development.

    Configuration in LOGGING:
        "filters": {
            "slow_query": {
                "()": "utilities.logging_filters.SlowQueryFilter",
                "threshold_ms": 200,
            }
        }
    """

    def __init__(self, threshold_ms: int = 200, name: str = ""):
        super().__init__(name)
        self.threshold_ms = threshold_ms

    def filter(self, record: logging.LogRecord) -> bool:
        duration = getattr(record, "duration", None)
        if duration is None:
            return False
        return float(duration) >= self.threshold_ms
