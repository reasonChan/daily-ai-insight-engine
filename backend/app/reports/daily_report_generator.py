from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.schemas.analysis import DailyReport, Event, Insight, RiskAssessment
from backend.app.schemas.daily_analysis import DailyAnalysis
from backend.app.schemas.daily_article import DailyArticle
from backend.app.schemas.source import RawSourceItem


class DailyReportGenerator:
    def generate(
        self,
        report_date: date,
        events: list[Event],
        insights: list[Insight],
        risks: list[RiskAssessment],
        source_items: list[RawSourceItem],
        summary: dict[str, Any],
        daily_analysis: DailyAnalysis | None = None,
        daily_article: DailyArticle | None = None,
        output_dir: str | Path = "reports/daily",
    ) -> DailyReport:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        ranked_events = sorted(events, key=lambda event: (event.importance_score, event.risk_score), reverse=True)
        risk_alerts = [risk for risk in sorted(risks, key=lambda risk: risk.overall_risk, reverse=True) if risk.overall_risk >= 0.45]
        generated_at = datetime.now(timezone.utc)
        payload = {
            "report_date": report_date.isoformat(),
            "executive_summary": _executive_summary(ranked_events, risk_alerts),
            "top_events": [event.model_dump(mode="json") for event in ranked_events[:5]],
            "insights": [insight.model_dump(mode="json") for insight in insights],
            "risk_alerts": [risk.model_dump(mode="json") for risk in risk_alerts],
            "daily_analysis": daily_analysis.model_dump(mode="json") if daily_analysis else None,
            "daily_article": daily_article.model_dump(mode="json") if daily_article else None,
            "source_breakdown": dict(Counter(item.source_type for item in source_items)),
            "failed_sources": summary.get("failed_sources", []),
            "notable_source_items": [_source_payload(item) for item in source_items],
            "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        }
        json_path = output_dir / f"{report_date.isoformat()}.json"
        md_path = output_dir / f"{report_date.isoformat()}.md"
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        md_path.write_text(_render_markdown(payload), encoding="utf-8")
        latest_path = output_dir / "latest.json"
        latest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return DailyReport(
            id=f"report_{report_date.isoformat()}",
            report_date=report_date,
            executive_summary=payload["executive_summary"],
            top_event_ids=[event.id for event in ranked_events[:5]],
            risk_alert_ids=[risk.id for risk in risk_alerts],
            markdown_path=str(md_path),
            json_path=str(json_path),
            report=payload,
            generated_at=generated_at,
        )


def _executive_summary(events: list[Event], risk_alerts: list[RiskAssessment]) -> str:
    if not events:
        return "本期没有发现可用于生成日报的 AI 相关事件。"
    return f"本期共识别 {len(events)} 个 AI 相关事件，其中 {len(risk_alerts)} 个进入风险预警；最高权重信号为：{events[0].title}"


def _source_payload(item: RawSourceItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "source_name": item.source_name,
        "source_type": item.source_type,
        "language": item.language,
        "url": item.source_url,
        "published_at": item.published_at.isoformat().replace("+00:00", "Z"),
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    article = payload.get("daily_article")
    lines = [
        f"# {article['title'] if article else 'Daily AI Insight Report - ' + payload['report_date']}",
        "",
    ]
    if article:
        if article.get("subtitle"):
            lines.extend([article["subtitle"], ""])
        lines.extend(_render_daily_article(article))
        lines.extend(["", "---", "", "## 结构化附录", ""])
    lines.extend([
        "## Executive Summary",
        "",
        payload["executive_summary"],
        "",
        "## Top Events",
        "",
    ])
    for event in payload["top_events"]:
        source_ids = ", ".join(event["related_source_item_ids"])
        lines.extend([f"- **{event['title']}** ({event['category']}, importance {event['importance_score']})", f"  Source items: {source_ids}"])
    analysis = payload.get("daily_analysis")
    if analysis:
        lines.extend(_render_daily_analysis(analysis))
    lines.extend(["", "## Key Insights", ""])
    for insight in payload["insights"]:
        lines.append(f"- **{insight['event_id']}**: {insight['why_it_matters']}")
    lines.extend(["", "## Risk Alerts", ""])
    if payload["risk_alerts"]:
        for risk in payload["risk_alerts"]:
            lines.append(f"- **{risk['event_id']}** overall risk {risk['overall_risk']}: {'; '.join(risk['risk_factors'])}")
    else:
        lines.append("- No elevated risk alerts.")
    lines.extend(["", "## Notable Source Items", ""])
    for item in payload["notable_source_items"]:
        lines.append(f"- [{item['title']}]({item['url']}) - {item['source_name']}")
    lines.extend(["", "## Source Breakdown", ""])
    for source_type, count in payload["source_breakdown"].items():
        lines.append(f"- {source_type}: {count}")
    lines.extend(["", "## Failed Sources", ""])
    if payload["failed_sources"]:
        for failure in payload["failed_sources"]:
            lines.append(f"- {failure}")
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _render_daily_article(article: dict[str, Any]) -> list[str]:
    lines = [
        "## 今日主线",
        "",
        article["lead"],
        "",
    ]
    for section in article.get("body_sections") or []:
        lines.extend(
            [
                f"## {section['heading']}",
                "",
                section["content"],
                "",
            ]
        )
    lines.extend(
        [
            "## 趋势判断",
            "",
            article["trend_outlook"],
            "",
            "## 风险与机会",
            "",
            article["risk_opportunity"],
            "",
            f"证据来源：{', '.join(article.get('evidence_source_item_ids') or [])}",
        ]
    )
    return lines


def _render_daily_analysis(analysis: dict[str, Any]) -> list[str]:
    lines = ["", "## 今日 AI 领域主要热点", ""]
    hot_topics = analysis.get("hot_topics") or []
    if hot_topics:
        for topic in hot_topics:
            evidence = ", ".join(topic.get("evidence_source_item_ids", []))
            lines.extend(
                [
                    f"{topic['rank']}. **{topic['title']}** ({topic['category']}, hot score {topic['hot_score']})",
                    f"   Logic: {topic['reason']}",
                    f"   Evidence: {evidence}",
                ]
            )
    else:
        lines.append("- No high-confidence hot topics found.")

    lines.extend(["", "## 重要事件深度总结", ""])
    deep_dives = analysis.get("deep_dives") or []
    if deep_dives:
        for dive in deep_dives:
            evidence = "; ".join(dive.get("evidence", []))
            lines.extend(
                [
                    f"- **{dive['title']}**",
                    f"  Background: {dive['background']}",
                    f"  Impact: {dive['impact_analysis']}",
                    f"  Evidence: {evidence}",
                ]
            )
    else:
        lines.append("- No event has enough evidence for deep-dive analysis.")

    lines.extend(["", "## 趋势判断", ""])
    trends = analysis.get("trend_judgments") or []
    if trends:
        for trend in trends:
            lines.extend(
                [
                    f"- **{trend['direction']}**: {trend['judgment']}",
                    f"  Logic: {trend['logic']}",
                    f"  Signal strength: {trend['signal_strength']}, confidence: {trend['confidence']}",
                ]
            )
    else:
        lines.append("- No clear trend signal was identified from today's structured events.")

    lines.extend(["", "## 风险与机会提示", ""])
    notes = analysis.get("risk_opportunity_notes") or []
    if notes:
        for note in notes:
            evidence = ", ".join(note.get("evidence_source_item_ids", []))
            lines.extend(
                [
                    f"- **{note['type']} | {note['title']}**",
                    f"  Rationale: {note['rationale']}",
                    f"  Evidence: {evidence}",
                ]
            )
    else:
        lines.append("- No material risk or opportunity note was identified.")
    return lines
