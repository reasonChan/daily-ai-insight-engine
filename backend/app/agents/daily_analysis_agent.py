from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timezone

from backend.app.schemas.analysis import Event, Insight, RiskAssessment
from backend.app.schemas.daily_analysis import (
    DailyAnalysis,
    EventDeepDive,
    HotTopic,
    RiskOpportunityNote,
    TrendJudgment,
)
from backend.app.schemas.source import RawSourceItem


_ENTITY_WEIGHTS = {
    "OpenAI",
    "Anthropic",
    "Google",
    "DeepMind",
    "Microsoft",
    "Meta",
    "Nvidia",
    "Amazon",
    "Apple",
}

_CATEGORY_TO_TREND = {
    "model": "technology",
    "research": "technology",
    "infrastructure": "technology",
    "safety": "technology",
    "product": "application",
    "company": "application",
    "policy": "policy",
    "funding": "capital",
}

_TREND_LABELS = {
    "technology": "Technology",
    "application": "Application",
    "policy": "Policy",
    "capital": "Capital",
}


class DailyAnalysisAgent:
    """Builds evidence-backed daily analysis from structured event objects."""

    def analyze(
        self,
        report_date: date,
        events: list[Event],
        insights: list[Insight],
        risks: list[RiskAssessment],
        source_items: list[RawSourceItem],
    ) -> DailyAnalysis:
        insight_by_event_id = {insight.event_id: insight for insight in insights}
        risk_by_event_id = {risk.event_id: risk for risk in risks}
        source_by_id = {item.id: item for item in source_items}
        ranked_events = sorted(
            events,
            key=lambda event: _hot_score(event, risk_by_event_id.get(event.id), source_by_id),
            reverse=True,
        )
        hot_topics = [
            _hot_topic(rank, event, risk_by_event_id.get(event.id), source_by_id)
            for rank, event in enumerate(ranked_events[:5], start=1)
        ]
        deep_dives = [
            _deep_dive(event, insight_by_event_id.get(event.id), risk_by_event_id.get(event.id), source_by_id)
            for event in ranked_events[:3]
        ]
        trend_judgments = _trend_judgments(ranked_events, risk_by_event_id)
        risk_opportunity_notes = _risk_opportunity_notes(ranked_events, insight_by_event_id, risk_by_event_id)
        evidence_ids = _unique(
            source_id
            for section in (
                hot_topics,
                deep_dives,
                trend_judgments,
                risk_opportunity_notes,
            )
            for item in section
            for source_id in item.evidence_source_item_ids
        )
        return DailyAnalysis(
            report_date=report_date,
            hot_topics=hot_topics,
            deep_dives=deep_dives,
            trend_judgments=trend_judgments,
            risk_opportunity_notes=risk_opportunity_notes,
            evidence_source_item_ids=evidence_ids,
            generated_at=datetime.now(timezone.utc),
        )


def _hot_topic(
    rank: int,
    event: Event,
    risk: RiskAssessment | None,
    source_by_id: dict[str, RawSourceItem],
) -> HotTopic:
    hot_score = _hot_score(event, risk, source_by_id)
    coverage = len(event.related_source_item_ids)
    risk_score = risk.overall_risk if risk else event.risk_score
    reason_parts = [
        f"importance={event.importance_score:.2f}",
        f"risk={risk_score:.2f}",
        f"source_coverage={coverage}",
    ]
    if event.entities.companies or event.entities.models:
        reason_parts.append(f"entities={', '.join((event.entities.companies + event.entities.models)[:4])}")
    return HotTopic(
        rank=rank,
        title=event.title,
        category=event.category,
        importance_score=event.importance_score,
        hot_score=hot_score,
        reason="Ranked by " + "; ".join(reason_parts) + ".",
        supporting_event_ids=[event.id],
        evidence_source_item_ids=list(event.related_source_item_ids),
    )


def _deep_dive(
    event: Event,
    insight: Insight | None,
    risk: RiskAssessment | None,
    source_by_id: dict[str, RawSourceItem],
) -> EventDeepDive:
    source_titles = [
        source_by_id[source_id].title
        for source_id in event.related_source_item_ids
        if source_id in source_by_id
    ]
    background = event.summary or "Background is based on the clustered source items for this event."
    if source_titles:
        background = f"{background} Supporting coverage includes: {'; '.join(source_titles[:3])}."
    impact = insight.why_it_matters if insight else f"This {event.category} event may affect AI industry decisions."
    if risk and risk.overall_risk >= 0.45:
        impact = f"{impact} Risk signal is elevated at {risk.overall_risk:.2f}: {'; '.join(risk.risk_factors[:2])}."
    affected_entities = _unique(
        [
            *event.entities.companies,
            *event.entities.products,
            *event.entities.models,
            *(insight.affected_sectors if insight else []),
        ]
    )
    evidence = source_titles[:4] or list(event.related_source_item_ids[:4])
    confidence = max(insight.confidence if insight else 0.45, min(0.85, 0.45 + len(event.related_source_item_ids) * 0.08))
    return EventDeepDive(
        event_id=event.id,
        title=event.title,
        background=background,
        impact_analysis=impact,
        affected_entities=affected_entities,
        evidence=evidence,
        evidence_source_item_ids=list(event.related_source_item_ids),
        confidence=round(confidence, 3),
    )


def _trend_judgments(events: list[Event], risk_by_event_id: dict[str, RiskAssessment]) -> list[TrendJudgment]:
    grouped: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        direction = _CATEGORY_TO_TREND.get(event.category)
        if direction:
            grouped[direction].append(event)

    judgments: list[TrendJudgment] = []
    for direction in ("technology", "application", "policy", "capital"):
        direction_events = grouped.get(direction, [])
        if not direction_events:
            continue
        categories = Counter(event.category for event in direction_events)
        top_entities = _top_entities(direction_events)
        avg_importance = sum(event.importance_score for event in direction_events) / len(direction_events)
        max_risk = max((risk_by_event_id.get(event.id).overall_risk if risk_by_event_id.get(event.id) else event.risk_score) for event in direction_events)
        signal_strength = min(1.0, avg_importance * 0.55 + min(1.0, len(direction_events) / 5) * 0.25 + max_risk * 0.20)
        logic_parts = [
            f"{len(direction_events)} event(s)",
            f"avg_importance={avg_importance:.2f}",
            f"max_risk={max_risk:.2f}",
            f"categories={dict(categories)}",
        ]
        if top_entities:
            logic_parts.append(f"top_entities={', '.join(top_entities)}")
        label = _TREND_LABELS[direction]
        judgments.append(
            TrendJudgment(
                direction=direction,
                judgment=f"{label} signals are concentrated in {', '.join(categories.keys())}.",
                logic="; ".join(logic_parts) + ".",
                supporting_event_ids=[event.id for event in direction_events[:5]],
                evidence_source_item_ids=_unique(source_id for event in direction_events[:5] for source_id in event.related_source_item_ids),
                signal_strength=round(signal_strength, 3),
                confidence=round(min(0.9, 0.45 + len(direction_events) * 0.08 + avg_importance * 0.2), 3),
            )
        )
    return sorted(judgments, key=lambda item: item.signal_strength, reverse=True)


def _risk_opportunity_notes(
    events: list[Event],
    insight_by_event_id: dict[str, Insight],
    risk_by_event_id: dict[str, RiskAssessment],
) -> list[RiskOpportunityNote]:
    notes: list[RiskOpportunityNote] = []
    for event in events:
        risk = risk_by_event_id.get(event.id)
        if risk and risk.overall_risk >= 0.35:
            notes.append(
                RiskOpportunityNote(
                    type="risk",
                    title=f"Watch risk around {event.title}",
                    rationale=f"Overall risk {risk.overall_risk:.2f}; {'; '.join(risk.risk_factors[:3])}.",
                    related_event_ids=[event.id],
                    evidence_source_item_ids=list(event.related_source_item_ids),
                    priority=risk.overall_risk,
                )
            )
        insight = insight_by_event_id.get(event.id)
        if insight and insight.opportunities and event.importance_score >= 0.65:
            notes.append(
                RiskOpportunityNote(
                    type="opportunity",
                    title=f"Opportunity signal from {event.title}",
                    rationale=f"{insight.opportunities[0]} Importance score {event.importance_score:.2f}.",
                    related_event_ids=[event.id],
                    evidence_source_item_ids=list(event.related_source_item_ids),
                    priority=round(min(1.0, event.importance_score * 0.8 + insight.confidence * 0.2), 3),
                )
            )
    return sorted(notes, key=lambda item: item.priority, reverse=True)[:6]


def _hot_score(
    event: Event,
    risk: RiskAssessment | None,
    source_by_id: dict[str, RawSourceItem],
) -> float:
    risk_score = risk.overall_risk if risk else event.risk_score
    coverage_score = min(1.0, len(event.related_source_item_ids) / 3)
    entity_score = min(
        1.0,
        0.2 * len(set(event.entities.companies) & _ENTITY_WEIGHTS)
        + 0.1 * len(event.entities.models),
    )
    source_weight = max((_source_weight(source_by_id.get(source_id)) for source_id in event.related_source_item_ids), default=0.2)
    recency_score = 1.0 if (datetime.now(timezone.utc).date() - event.latest_seen_at.date()).days <= 1 else 0.55
    score = (
        event.importance_score * 0.36
        + risk_score * 0.18
        + coverage_score * 0.18
        + entity_score * 0.10
        + source_weight * 0.10
        + recency_score * 0.08
    )
    return round(min(1.0, score), 3)


def _source_weight(item: RawSourceItem | None) -> float:
    if item is None:
        return 0.2
    return {
        "official": 1.0,
        "research": 0.9,
        "tech_media": 0.75,
        "aggregator": 0.45,
        "social": 0.35,
    }.get(str(item.source_type), 0.5)


def _top_entities(events: list[Event]) -> list[str]:
    counts: Counter[str] = Counter()
    for event in events:
        counts.update(event.entities.companies)
        counts.update(event.entities.models)
        counts.update(event.entities.topics)
    return [entity for entity, _ in counts.most_common(5)]


def _unique(values) -> list:
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
