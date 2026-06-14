from __future__ import annotations

import json
import sqlite3

from fastapi.testclient import TestClient

from backend.app.api.main import app


def test_health_source_items_and_reports(monkeypatch, tmp_path):
    db_path = tmp_path / "source_items.sqlite"
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    _create_source_db(db_path)
    monkeypatch.setenv("AI_INSIGHT_SOURCE_DB_PATH", str(db_path))
    monkeypatch.setenv("AI_INSIGHT_REPORTS_DIR", str(reports_dir))

    report = {
        "report_date": "2026-06-14",
        "executive_summary": "Tracked one AI event.",
        "top_events": [
            {
                "id": "evt_1",
                "title": "OpenAI ships agent tooling",
                "summary": "Developer workflows changed.",
                "category": "product",
                "related_source_item_ids": ["src_1"],
                "risk_score": 0.2,
                "importance_score": 0.8,
            }
        ],
        "risk_alerts": [],
        "daily_analysis": {
            "hot_topics": [
                {
                    "rank": 1,
                    "title": "OpenAI ships agent tooling",
                    "category": "product",
                    "importance_score": 0.8,
                    "hot_score": 0.72,
                    "reason": "Ranked by importance=0.80; source_coverage=1.",
                    "supporting_event_ids": ["evt_1"],
                    "evidence_source_item_ids": ["src_1"],
                }
            ],
            "deep_dives": [],
            "trend_judgments": [],
            "risk_opportunity_notes": [],
            "evidence_source_item_ids": ["src_1"],
            "generated_at": "2026-06-14T02:00:00Z",
            "report_date": "2026-06-14",
        },
        "source_breakdown": {"official": 1},
        "failed_sources": [{"source_name": "Reddit", "reason": "HTTP 403"}],
        "generated_at": "2026-06-14T02:00:00Z",
    }
    (reports_dir / "2026-06-14.json").write_text(json.dumps(report), encoding="utf-8")

    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["storage"]["source_item_count"] == 2
    assert health.json()["failed_source_count"] == 1

    sources = client.get("/source-items", params={"source_type": "official"})
    assert sources.status_code == 200
    assert sources.json()["total"] == 1
    assert sources.json()["items"][0]["id"] == "src_1"

    latest = client.get("/reports/latest")
    assert latest.status_code == 200
    assert latest.json()["report_date"] == "2026-06-14"
    assert latest.json()["daily_analysis"]["hot_topics"][0]["rank"] == 1

    dated = client.get("/reports/2026-06-14")
    assert dated.status_code == 200
    assert dated.json()["executive_summary"] == "Tracked one AI event."
    assert set(dated.json()["daily_analysis"]) >= {
        "hot_topics",
        "deep_dives",
        "trend_judgments",
        "risk_opportunity_notes",
    }

    events = client.get("/events")
    assert events.status_code == 200
    assert events.json()["items"][0]["id"] == "evt_1"


def test_missing_report_returns_404(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_INSIGHT_SOURCE_DB_PATH", str(tmp_path / "missing.sqlite"))
    monkeypatch.setenv("AI_INSIGHT_REPORTS_DIR", str(tmp_path / "reports"))

    response = TestClient(app).get("/reports/latest")

    assert response.status_code == 404


def _create_source_db(path):
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE source_items (
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
        conn.executemany(
            """
            INSERT INTO source_items VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                (
                    "src_1",
                    "official",
                    "blog",
                    "OpenAI Blog",
                    "https://example.com/openai",
                    "OpenAI ships agent tooling",
                    "Agent workflow update.",
                    "",
                    "en",
                    "2026-06-14T01:00:00Z",
                    "2026-06-14T02:00:00Z",
                    '{"fixture": true}',
                    "hash-1",
                    0.92,
                ),
                (
                    "src_2",
                    "aggregator",
                    "ranking_item",
                    "Hacker News",
                    "https://example.com/hn",
                    "Developers discuss AI agents",
                    "Discussion.",
                    "",
                    "en",
                    "2026-06-13T01:00:00Z",
                    "2026-06-14T02:00:00Z",
                    "{}",
                    "hash-2",
                    0.78,
                ),
            ],
        )
        conn.commit()
