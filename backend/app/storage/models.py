from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from backend.app.schemas.source import RawSourceItem


def parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def datetime_to_storage(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def raw_source_item_from_mapping(payload: dict[str, Any]) -> RawSourceItem:
    return RawSourceItem(**payload)


def content_hash(item: RawSourceItem) -> str:
    text = "\n".join([item.title, item.summary or "", item.content or ""])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
