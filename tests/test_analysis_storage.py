from __future__ import annotations

import sqlite3
from datetime import date

from backend.app.schemas.analysis import DailyReport, Event, EventEntities, Insight, PipelineRun, RiskAssessment
from backend.app.storage import SQLiteAnalysisStore


def test_analysis_store_creates_tables(tmp_path):
    SQLiteAnalysisStore(tmp_path / "analysis.sqlite")

    with sqlite3.connect(tmp_path / "analysis.sqlite") as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert {
        "pipeline_runs",
        "events",
        "event_source_items",
        "insights",
        "risk_assessments",
        "daily_reports",
    }.issubset(tables)


def test_pipeline_run_and_event_upsert_fetch_preserve_json(tmp_path):
    db_path = tmp_path / "analysis.sqlite"
    store = SQLiteAnalysisStore(db_path)
    source_name = "\u6d4b\u8bd5\u6e90"
    timeout_reason = "\u8d85\u65f6"
    chinese_note = "\u4e2d\u6587\u6458\u8981"
    chinese_topic = "\u4e2d\u6587"
    run = PipelineRun(
        id="run-1",
        started_at="2026-06-14T00:00:00Z",
        finished_at="2026-06-14T00:01:00Z",
        status="partial_success",
        candidate_count=4,
        ai_related_count=3,
        deduplicated_count=2,
        stored_count=2,
        failed_sources=[{"source_name": source_name, "reason": timeout_reason}],
        summary={"note": chinese_note},
    )
    event = Event(
        id="evt-1",
        title="OpenAI \u53d1\u5e03\u4e2d\u6587\u4ea7\u54c1\u66f4\u65b0",
        summary="\u4e00\u4e2a\u91cd\u8981\u7684 AI \u4ea7\u54c1\u4fe1\u53f7\u3002",
        category="product",
        entities=EventEntities(companies=["OpenAI"], products=["ChatGPT"], topics=[chinese_topic]),
        related_source_item_ids=["src-1", "src-2"],
        first_seen_at="2026-06-14T00:00:00Z",
        latest_seen_at="2026-06-14T01:00:00Z",
        importance_score=0.7,
    )

    store.upsert_pipeline_run(run)
    store.upsert_event(event)
    store.upsert_event(event.model_copy(update={"importance_score": 0.9}))

    fetched_run = store.fetch_pipeline_run("run-1")
    fetched_event = store.fetch_event("evt-1")

    assert fetched_run is not None
    assert fetched_run.failed_sources[0]["source_name"] == source_name
    assert fetched_run.summary["note"] == chinese_note
    assert fetched_event is not None
    assert fetched_event.importance_score == 0.9
    assert fetched_event.related_source_item_ids == ["src-1", "src-2"]
    assert fetched_event.entities.topics == [chinese_topic]
    with sqlite3.connect(db_path) as connection:
        raw = connection.execute("SELECT entities_json FROM events WHERE id = 'evt-1'").fetchone()[0]
    assert chinese_topic in raw
    assert "\\u4e2d\\u6587" not in raw


def test_insight_risk_and_daily_report_upsert_fetch(tmp_path):
    store = SQLiteAnalysisStore(tmp_path / "analysis.sqlite")
    key_point = "\u5173\u952e\u70b9"
    executive_summary = "\u4eca\u65e5\u6458\u8981"
    updated_summary = "\u66f4\u65b0\u540e\u7684\u6458\u8981"
    insight = Insight(
        id="ins-1",
        event_id="evt-1",
        key_points=[key_point],
        why_it_matters="\u5f71\u54cd\u4f01\u4e1a\u51b3\u7b56\u3002",
        affected_companies=["OpenAI"],
        affected_sectors=["AI applications"],
        opportunities=["\u8ddf\u8e2a\u91c7\u7528\u60c5\u51b5"],
        risks=["\u5173\u6ce8\u653f\u7b56\u53cd\u9988"],
        confidence=0.6,
        evidence_source_item_ids=["src-1"],
        created_at="2026-06-14T00:02:00Z",
    )
    risk = RiskAssessment(
        id="risk-1",
        event_id="evt-1",
        policy_risk=0.4,
        overall_risk=0.5,
        risk_factors=["policy risk terms: regulation"],
        evidence_source_item_ids=["src-1"],
        created_at="2026-06-14T00:03:00Z",
    )
    report = DailyReport(
        id="report-2026-06-14",
        report_date=date(2026, 6, 14),
        executive_summary=executive_summary,
        top_event_ids=["evt-1"],
        risk_alert_ids=["risk-1"],
        markdown_path="reports/daily/2026-06-14.md",
        json_path="reports/daily/2026-06-14.json",
        report={
            "executive_summary": executive_summary,
            "daily_analysis": {
                "hot_topics": [{"rank": 1, "title": "\u4ea7\u54c1\u70ed\u70b9"}],
                "deep_dives": [],
                "trend_judgments": [],
                "risk_opportunity_notes": [],
            },
        },
        generated_at="2026-06-14T00:04:00Z",
    )

    store.upsert_insight(insight)
    store.upsert_insight(insight.model_copy(update={"confidence": 0.8}))
    store.upsert_risk_assessment(risk)
    store.upsert_daily_report(report)
    store.upsert_daily_report(report.model_copy(update={"executive_summary": updated_summary}))

    fetched_insight = store.fetch_insight("ins-1")
    fetched_risk = store.fetch_risk_assessment("risk-1")
    fetched_report = store.fetch_daily_report_by_date("2026-06-14")

    assert fetched_insight is not None
    assert fetched_insight.confidence == 0.8
    assert store.list_insights_for_event("evt-1") == [fetched_insight]
    assert fetched_risk is not None
    assert fetched_risk.overall_risk == 0.5
    assert store.list_risk_assessments_for_event("evt-1") == [fetched_risk]
    assert fetched_report is not None
    assert fetched_report.executive_summary == updated_summary
    assert fetched_report.top_event_ids == ["evt-1"]
    assert fetched_report.report["daily_analysis"]["hot_topics"][0]["title"] == "\u4ea7\u54c1\u70ed\u70b9"
    assert set(fetched_report.report["daily_analysis"]) == {
        "hot_topics",
        "deep_dives",
        "trend_judgments",
        "risk_opportunity_notes",
    }
    assert store.fetch_latest_daily_report() == fetched_report
