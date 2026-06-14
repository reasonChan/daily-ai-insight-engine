from __future__ import annotations

from .analysis_store import SQLiteAnalysisStore as _SQLiteAnalysisStore


class SQLiteAnalysisStore(_SQLiteAnalysisStore):
    """Compatibility import for API code that probes optional analysis storage."""

    def list_events(self, *args, **kwargs):
        events = super().list_events(*args, **kwargs)
        if not events:
            raise LookupError("analysis store has no events")
        return events

    fetch_events = list_events


__all__ = ["SQLiteAnalysisStore"]
