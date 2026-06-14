from __future__ import annotations

import json
from datetime import date

from backend.app.agents import DailyAnalysisAgent, InsightAnalysisAgent, RiskAssessmentAgent
from backend.app.cli import load_fixture_items, run_daily_report_pipeline
from backend.app.schemas.analysis import Event, EventEntities


def test_daily_analysis_agent_builds_evidence_backed_sections():
    items = load_fixture_items("tests/fixtures/raw_source_items.json")
    events = [
        Event(
            id="evt_openai",
            title="OpenAI announces agent platform",
            summary="OpenAI released new agent workflow tools for developers.",
            category="product",
            entities=EventEntities(companies=["OpenAI"], products=["Agents"], topics=["agent"]),
            related_source_item_ids=[items[0].id],
            first_seen_at="2026-06-14T00:00:00Z",
            latest_seen_at="2026-06-14T01:00:00Z",
            importance_score=0.82,
        ),
        Event(
            id="evt_policy",
            title="Regulators publish AI compliance guidance",
            summary="A policy update adds compliance expectations for AI systems.",
            category="policy",
            entities=EventEntities(companies=["Anthropic"], topics=["safety"]),
            related_source_item_ids=[items[1].id],
            first_seen_at="2026-06-14T00:30:00Z",
            latest_seen_at="2026-06-14T01:30:00Z",
            importance_score=0.74,
        ),
    ]
    risk_agent = RiskAssessmentAgent()
    risks = [risk_agent.assess(event, items) for event in events]
    risk_by_event_id = {risk.event_id: risk for risk in risks}
    events = [event.model_copy(update={"risk_score": risk_by_event_id[event.id].overall_risk}) for event in events]
    insights = [InsightAnalysisAgent().analyze(event, items) for event in events]

    analysis = DailyAnalysisAgent().analyze(
        report_date=date(2026, 6, 14),
        events=events,
        insights=insights,
        risks=risks,
        source_items=items,
    )

    assert 1 <= len(analysis.hot_topics) <= 5
    assert analysis.hot_topics[0].supporting_event_ids
    assert analysis.hot_topics[0].evidence_source_item_ids
    assert "importance=" in analysis.hot_topics[0].reason
    assert analysis.deep_dives[0].background
    assert analysis.deep_dives[0].impact_analysis
    assert {trend.direction for trend in analysis.trend_judgments} >= {"application", "policy"}
    assert all(trend.logic and trend.evidence_source_item_ids for trend in analysis.trend_judgments)
    assert analysis.risk_opportunity_notes
    assert all(note.related_event_ids and note.evidence_source_item_ids for note in analysis.risk_opportunity_notes)


def test_daily_report_pipeline_writes_daily_analysis_sections(tmp_path):
    items = load_fixture_items("tests/fixtures/raw_source_items.json")
    summary = run_daily_report_pipeline(
        items=items,
        db_path=tmp_path / "source_items.sqlite",
        rag_dir=tmp_path / "rag",
        report_dir=tmp_path / "reports",
    )

    payload = json.loads((tmp_path / "reports" / "latest.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "reports" / payload["report_date"]).with_suffix(".md").read_text(encoding="utf-8")

    assert summary["event_count"] >= 1
    assert payload["daily_analysis"]["hot_topics"]
    assert payload["daily_analysis"]["deep_dives"]
    assert payload["daily_analysis"]["trend_judgments"]
    assert payload["daily_analysis"]["risk_opportunity_notes"]
    assert payload["daily_analysis"]["hot_topics"][0]["evidence_source_item_ids"]
    assert "今日AI领域主要热点" in markdown
    assert "重要事件深度总结" in markdown
    assert "趋势判断" in markdown
    assert "风险与机会提示" in markdown
