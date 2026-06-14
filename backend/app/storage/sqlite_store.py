from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class SQLiteSourceStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def upsert_items(
        self,
        items: list[object],
        relevance_scores: dict[str, float] | None = None,
    ) -> int:
        relevance_scores = relevance_scores or {}
        with sqlite3.connect(self.db_path) as conn:
            count = 0
            for item in items:
                item_id = str(getattr(item, "id"))
                conn.execute(_UPSERT_SQL, _item_to_row(item, relevance_scores.get(item_id, 0.0)))
                count += 1
            conn.commit()
        return count

    def upsert_item(self, item: object, ai_relevance_score: float = 0.0) -> None:
        item_id = str(getattr(item, "id"))
        self.upsert_items([item], {item_id: ai_relevance_score})

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def count_items(self) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM source_items").fetchone()
            return int(row["count"])

    def fetch_item(self, item_id: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM source_items WHERE id = ?",
                (item_id,),
            ).fetchone()
        return dict(row) if row else None

    def fetch_items(self, limit: int = 100, offset: int = 0) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM source_items
                ORDER BY published_at DESC, id
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS source_items (
                    id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    medium_type TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    content TEXT NOT NULL,
                    language TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    collected_at TEXT NOT NULL,
                    raw_payload_json TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    ai_relevance_score REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_source_items_published_at ON source_items(published_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_source_items_source_type ON source_items(source_type)"
            )
            conn.commit()


SQLiteMetadataStore = SQLiteSourceStore


_UPSERT_SQL = """
INSERT INTO source_items (
    id, source_type, medium_type, source_name, source_url, title,
    summary, content, language, published_at, collected_at,
    raw_payload_json, content_hash, ai_relevance_score
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    source_type=excluded.source_type,
    medium_type=excluded.medium_type,
    source_name=excluded.source_name,
    source_url=excluded.source_url,
    title=excluded.title,
    summary=excluded.summary,
    content=excluded.content,
    language=excluded.language,
    published_at=excluded.published_at,
    collected_at=excluded.collected_at,
    raw_payload_json=excluded.raw_payload_json,
    content_hash=excluded.content_hash,
    ai_relevance_score=excluded.ai_relevance_score
"""


def _item_to_row(item: object, relevance_score: float) -> tuple:
    raw_payload = getattr(item, "raw_payload", {}) or {}
    raw_payload_json = (
        item.raw_payload_json()
        if hasattr(item, "raw_payload_json")
        else json.dumps(raw_payload, ensure_ascii=False)
    )
    return (
        getattr(item, "id"),
        getattr(item, "source_type"),
        getattr(item, "medium_type"),
        getattr(item, "source_name"),
        getattr(item, "source_url"),
        getattr(item, "title"),
        getattr(item, "summary") or "",
        getattr(item, "content") or "",
        getattr(item, "language"),
        _datetime_to_text(getattr(item, "published_at")),
        _datetime_to_text(getattr(item, "collected_at")),
        raw_payload_json,
        _content_hash(item),
        relevance_score,
    )


def _datetime_to_text(value: object) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _content_hash(item: object) -> str:
    existing = getattr(item, "content_hash", None)
    if existing:
        return str(existing)
    import hashlib

    text = "\n".join(
        [
            str(getattr(item, "title", "") or ""),
            str(getattr(item, "summary", "") or ""),
            str(getattr(item, "content", "") or ""),
        ]
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
