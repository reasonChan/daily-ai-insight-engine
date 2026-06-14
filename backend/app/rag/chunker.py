from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from backend.app.schemas.source import RawSourceItem


@dataclass(frozen=True)
class RagChunk:
    id: str
    text: str
    metadata: dict[str, str]


def _clean_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _split_text(text: str, max_chars: int) -> list[str]:
    text = _clean_whitespace(text)
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            boundary = max(text.rfind(". ", start, end), text.rfind("\n", start, end))
            if boundary > start + max_chars // 2:
                end = boundary + 1
        chunks.append(text[start:end].strip())
        start = end
    return [chunk for chunk in chunks if chunk]


def _datetime_to_storage(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def chunk_source_item(item: RawSourceItem, max_chars: int = 1200) -> list[RagChunk]:
    body = item.content or item.summary or ""
    parts = _split_text(body, max_chars=max_chars)
    chunks: list[RagChunk] = []
    for index, part in enumerate(parts):
        text = (
            f"Title: {item.title}\n"
            f"Source: {item.source_name}\n"
            f"Published At: {_datetime_to_storage(item.published_at)}\n"
            f"Content:\n{part}"
        )
        chunks.append(
            RagChunk(
                id=f"{item.id}-{index:03d}",
                text=text,
                metadata={
                    "source_item_id": item.id,
                    "source_type": str(item.source_type),
                    "medium_type": str(item.medium_type),
                    "source_name": item.source_name,
                    "published_at": _datetime_to_storage(item.published_at),
                    "language": item.language,
                    "title": item.title,
                    "url": item.source_url,
                    "chunk_index": str(index),
                },
            )
        )
    return chunks


def write_chunks(chunks: list[RagChunk], rag_dir: str | Path) -> list[Path]:
    output_dir = Path(rag_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for chunk in chunks:
        path = output_dir / f"{chunk.id}.json"
        path.write_text(
            json.dumps(
                {
                    "id": chunk.id,
                    "text": chunk.text,
                    "metadata": chunk.metadata,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        paths.append(path)
    return paths
