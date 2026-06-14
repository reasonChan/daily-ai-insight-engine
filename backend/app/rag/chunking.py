from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.schemas.source import RawSourceItem


def item_to_chunk(item: RawSourceItem) -> dict[str, Any]:
    text = (
        f"Title: {item.title}\n"
        f"Source: {item.source_name}\n"
        f"Published At: {item.published_at.isoformat()}\n"
        "Content:\n"
        f"{item.content or item.summary}"
    )
    metadata = {
        "source_item_id": item.id,
        "source_type": item.source_type,
        "medium_type": item.medium_type,
        "source_name": item.source_name,
        "published_at": item.published_at.isoformat(),
        "language": item.language,
        "title": item.title,
        "url": item.source_url,
    }
    return {"id": f"{item.id}:chunk:0", "text": text, "metadata": metadata}


def write_chunks_jsonl(items: list[RawSourceItem], path: str | Path) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item_to_chunk(item), ensure_ascii=False) + "\n")
    return len(items)

