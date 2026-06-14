"""Shared schema helpers for collector outputs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def make_collection_result(
    *,
    source_name: str,
    items: list[dict[str, Any]] | None = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a stable collector result envelope."""

    return {
        "ok": error is None,
        "source_name": source_name,
        "collected_at": utc_now_iso(),
        "items": items or [],
        "error": error,
    }


def make_error(source_name: str, error_type: str, message: str, **extra: Any) -> dict[str, Any]:
    return make_collection_result(
        source_name=source_name,
        error={
            "type": error_type,
            "message": message,
            **{key: value for key, value in extra.items() if value is not None},
        },
    )


def make_raw_source_item(
    *,
    source_type: str,
    medium_type: str,
    source_name: str,
    source_url: str,
    title: str,
    summary: str = "",
    content: str = "",
    language: str = "other",
    published_at: str | None = None,
    raw_payload: dict[str, Any] | None = None,
    item_id: str | None = None,
    authors: list[str] | None = None,
    tags: list[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Create a dictionary compatible with the RawSourceItem base schema."""

    item = {
        "id": item_id or source_url,
        "source_type": source_type,
        "medium_type": medium_type,
        "source_name": source_name,
        "source_url": source_url,
        "title": title.strip(),
        "summary": summary.strip(),
        "content": content.strip(),
        "language": language,
        "published_at": published_at or utc_now_iso(),
        "collected_at": utc_now_iso(),
        "authors": authors or [],
        "tags": tags or [],
        "raw_payload": raw_payload or {},
    }
    item.update({key: value for key, value in extra.items() if value is not None})
    return item


def source_config_to_dict(source: Any) -> dict[str, Any]:
    if isinstance(source, dict):
        return source
    if hasattr(source, "model_dump"):
        return source.model_dump()
    return dict(source)


def to_collector_result(result: dict[str, Any]) -> Any:
    """Adapt the function-style result envelope to the app Pydantic schema."""

    from backend.app.schemas.source import CollectionFailure, CollectorResult, RawSourceItem

    failures = []
    error = result.get("error")
    if error:
        failures.append(
            CollectionFailure(
                source_name=result.get("source_name") or "unknown",
                reason=error.get("message") or error.get("type") or "collector failed",
            )
        )

    items = []
    for item in result.get("items") or []:
        try:
            items.append(RawSourceItem.model_validate(item))
        except Exception as exc:  # pragma: no cover - defensive collector boundary.
            failures.append(
                CollectionFailure(
                    source_name=result.get("source_name") or item.get("source_name") or "unknown",
                    reason=f"invalid collected item: {exc}",
                )
            )

    return CollectorResult(items=items, failures=failures)
