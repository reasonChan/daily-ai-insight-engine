from __future__ import annotations

from backend.app.schemas.analysis import Event, Insight
from backend.app.schemas.source import RawSourceItem


class InsightAnalysisAgent:
    def analyze(self, event: Event, source_items: list[RawSourceItem]) -> Insight:
        source_titles = [item.title for item in source_items if item.id in event.related_source_item_ids]
        companies = event.entities.companies
        sectors = _affected_sectors(event)
        key_points = [event.summary]
        key_points.extend(source_titles[:2])
        key_points = [point for index, point in enumerate(key_points) if point and point not in key_points[:index]]
        subject = ", ".join(companies or event.entities.models or event.entities.topics or [event.category])
        why = f"This {event.category} signal matters because it may affect {subject} decisions across AI product, research, or operations teams."
        return Insight(
            id=f"ins_{event.id.removeprefix('evt_')}",
            event_id=event.id,
            key_points=key_points[:4],
            why_it_matters=why,
            affected_companies=companies,
            affected_sectors=sectors,
            opportunities=_opportunities(event),
            risks=_risks(event),
            confidence=0.62 if source_items else 0.35,
            evidence_source_item_ids=list(event.related_source_item_ids),
        )


def _affected_sectors(event: Event) -> list[str]:
    mapping = {
        "product": ["AI applications", "developer tools"],
        "research": ["AI research", "model evaluation"],
        "policy": ["AI governance", "compliance"],
        "safety": ["AI safety", "security operations"],
        "infrastructure": ["cloud infrastructure", "AI compute"],
        "funding": ["AI startups", "venture capital"],
    }
    return mapping.get(event.category, ["AI industry"])


def _opportunities(event: Event) -> list[str]:
    if event.category in {"product", "research", "infrastructure"}:
        return ["Track follow-on adoption signals and developer response."]
    return ["Monitor related source coverage for strategic relevance."]


def _risks(event: Event) -> list[str]:
    if event.risk_score >= 0.6:
        return ["High-risk terms were present in the source evidence."]
    if event.category in {"policy", "safety"}:
        return ["Policy or safety implications may require closer review."]
    return ["No major risk signal detected from available source text."]
