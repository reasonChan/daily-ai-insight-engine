from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware


DEFAULT_DB_PATH = Path("data/live_source_items.sqlite")
DEFAULT_REPORTS_DIR = Path("reports/daily")


app = FastAPI(title="Daily AI Insight Engine API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, Any]:
    db_path = _source_db_path()
    reports_dir = _reports_dir()
    latest_report = _latest_report_path(reports_dir)
    source_count = _safe_source_count(db_path)
    report_payload = _read_json_file(latest_report) if latest_report else None
    failed_sources = report_payload.get("failed_sources", []) if isinstance(report_payload, dict) else []
    return {
        "status": "ok",
        "generated_at": _utc_now(),
        "storage": {
            "source_db_path": str(db_path),
            "source_db_exists": db_path.exists(),
            "source_item_count": source_count,
        },
        "reports": {
            "reports_dir": str(reports_dir),
            "latest_report": str(latest_report) if latest_report else None,
            "latest_report_exists": latest_report is not None,
        },
        "failed_source_count": len(failed_sources),
    }


@app.get("/source-items")
def source_items(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    source_type: str | None = None,
    language: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    db_path = _source_db_path()
    if not db_path.exists():
        return {"items": [], "total": 0, "limit": limit, "offset": offset}

    where: list[str] = []
    params: list[Any] = []
    if source_type:
        where.append("source_type = ?")
        params.append(source_type)
    if language:
        where.append("language = ?")
        params.append(language)
    if date_from:
        where.append("published_at >= ?")
        params.append(date_from)
    if date_to:
        where.append("published_at <= ?")
        params.append(date_to)
    clause = f"WHERE {' AND '.join(where)}" if where else ""

    with _connect(db_path) as conn:
        total = int(conn.execute(f"SELECT COUNT(*) AS count FROM source_items {clause}", params).fetchone()["count"])
        rows = conn.execute(
            f"""
            SELECT * FROM source_items
            {clause}
            ORDER BY published_at DESC, collected_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

    return {
        "items": [_source_item_payload(dict(row)) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/events")
def events(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    category: str | None = None,
    min_risk: float | None = Query(default=None, ge=0.0, le=1.0),
) -> dict[str, Any]:
    store_events = _fetch_events_from_analysis_store(limit=limit, offset=offset, category=category, min_risk=min_risk)
    if store_events is not None:
        return store_events

    report = _latest_report_payload()
    all_events = list(report.get("top_events", [])) if report else []
    if category:
        all_events = [item for item in all_events if item.get("category") == category]
    if min_risk is not None:
        all_events = [item for item in all_events if float(item.get("risk_score") or 0.0) >= min_risk]
    return {
        "items": all_events[offset : offset + limit],
        "total": len(all_events),
        "limit": limit,
        "offset": offset,
        "source": "latest_report",
    }


@app.get("/reports/latest")
def latest_report() -> dict[str, Any]:
    payload = _latest_report_payload()
    if payload:
        return payload
    raise HTTPException(status_code=404, detail="No report JSON found in reports directory")


@app.get("/reports/{report_date}")
def report_by_date(report_date: str) -> dict[str, Any]:
    try:
        date.fromisoformat(report_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="report date must be YYYY-MM-DD") from exc
    report_path = _reports_dir() / f"{report_date}.json"
    payload = _read_json_file(report_path)
    if payload:
        return payload
    raise HTTPException(status_code=404, detail=f"No report found for {report_date}")


def _source_db_path() -> Path:
    return Path(os.environ.get("AI_INSIGHT_SOURCE_DB_PATH", DEFAULT_DB_PATH))


def _reports_dir() -> Path:
    return Path(os.environ.get("AI_INSIGHT_REPORTS_DIR", DEFAULT_REPORTS_DIR))


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _safe_source_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with _connect(path) as conn:
            return int(conn.execute("SELECT COUNT(*) AS count FROM source_items").fetchone()["count"])
    except sqlite3.Error:
        return 0


def _source_item_payload(row: dict[str, Any]) -> dict[str, Any]:
    raw_payload = _loads_json(row.get("raw_payload_json"), {})
    return {
        "id": row.get("id"),
        "source_type": row.get("source_type"),
        "medium_type": row.get("medium_type"),
        "source_name": row.get("source_name"),
        "source_url": row.get("source_url"),
        "title": row.get("title"),
        "summary": row.get("summary"),
        "content": row.get("content"),
        "language": row.get("language"),
        "published_at": row.get("published_at"),
        "collected_at": row.get("collected_at"),
        "raw_payload": raw_payload,
        "content_hash": row.get("content_hash"),
        "ai_relevance_score": row.get("ai_relevance_score"),
    }


def _latest_report_payload() -> dict[str, Any] | None:
    latest = _latest_report_path(_reports_dir())
    return _read_json_file(latest) if latest else None


def _latest_report_path(reports_dir: Path) -> Path | None:
    explicit = reports_dir / "latest.json"
    if explicit.exists():
        return explicit
    dated = sorted(
        (path for path in reports_dir.glob("*.json") if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", path.name)),
        reverse=True,
    )
    if dated:
        return dated[0]
    summaries = sorted(reports_dir.glob("*summary.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return summaries[0] if summaries else None


def _read_json_file(path: Path | None) -> dict[str, Any] | None:
    if not path or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _fetch_events_from_analysis_store(
    limit: int,
    offset: int,
    category: str | None,
    min_risk: float | None,
) -> dict[str, Any] | None:
    try:
        from backend.app.storage.sqlite_analysis_store import SQLiteAnalysisStore  # type: ignore
    except Exception:
        return None

    try:
        store = SQLiteAnalysisStore(_source_db_path())
        if hasattr(store, "list_events"):
            items = store.list_events(limit=limit, offset=offset, category=category, min_risk=min_risk)
        elif hasattr(store, "fetch_events"):
            items = store.fetch_events(limit=limit, offset=offset, category=category, min_risk=min_risk)
        else:
            return None
    except Exception:
        return None

    normalized = [_model_or_mapping_to_dict(item) for item in items]
    return {"items": normalized, "total": len(normalized), "limit": limit, "offset": offset, "source": "analysis_store"}


def _model_or_mapping_to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    return dict(value)


def _loads_json(value: Any, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
