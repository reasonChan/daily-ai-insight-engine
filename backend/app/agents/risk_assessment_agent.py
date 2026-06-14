from __future__ import annotations

from backend.app.schemas.analysis import Event, RiskAssessment
from backend.app.schemas.source import RawSourceItem


_RISK_TERMS = {
    "public_opinion_risk": ("backlash", "boycott", "controversy", "complaint", "criticism"),
    "policy_risk": ("regulation", "ban", "lawsuit", "compliance", "copyright", "policy"),
    "security_risk": ("breach", "vulnerability", "exploit", "jailbreak", "prompt injection"),
    "business_risk": ("layoffs", "funding", "acquisition", "pricing", "competition"),
    "technical_risk": ("outage", "hallucination", "benchmark", "eval", "latency", "failure"),
}


class RiskAssessmentAgent:
    def assess(self, event: Event, source_items: list[RawSourceItem]) -> RiskAssessment:
        evidence = [item for item in source_items if item.id in event.related_source_item_ids]
        text = "\n".join([event.title, event.summary, *(item.content or item.summary for item in evidence)]).casefold()
        scores = {dimension: _score_dimension(text, terms) for dimension, terms in _RISK_TERMS.items()}
        if event.category == "policy":
            scores["policy_risk"] = max(scores["policy_risk"], 0.55)
        if event.category == "safety":
            scores["security_risk"] = max(scores["security_risk"], 0.45)
        overall = round(
            max(scores.values()) * 0.55 + (sum(scores.values()) / len(scores)) * 0.45,
            3,
        )
        factors = _risk_factors(text)
        if not factors:
            factors = ["No explicit high-risk terms found in source evidence."]
        return RiskAssessment(
            id=f"risk_{event.id.removeprefix('evt_')}",
            event_id=event.id,
            **scores,
            overall_risk=overall,
            risk_factors=factors,
            evidence_source_item_ids=list(event.related_source_item_ids),
        )


def _score_dimension(text: str, terms: tuple[str, ...]) -> float:
    matches = sum(1 for term in terms if term in text)
    return round(min(1.0, matches * 0.25), 3)


def _risk_factors(text: str) -> list[str]:
    factors: list[str] = []
    for dimension, terms in _RISK_TERMS.items():
        matched = [term for term in terms if term in text]
        if matched:
            factors.append(f"{dimension.replace('_', ' ')} terms: {', '.join(matched[:3])}")
    return factors
