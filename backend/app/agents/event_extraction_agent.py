from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Iterable

from backend.app.schemas.analysis import Event, EventEntities
from backend.app.schemas.source import RawSourceItem


_CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("policy", ("regulation", "policy", "ban", "law", "copyright", "compliance")),
    ("safety", ("safety", "alignment", "jailbreak", "misuse", "eval", "evaluation")),
    ("research", ("paper", "research", "benchmark", "arxiv", "model card")),
    ("product", ("launch", "announces", "release", "tooling", "workflow", "developer")),
    ("infrastructure", ("gpu", "cluster", "inference", "training", "datacenter")),
    ("funding", ("funding", "raises", "acquisition", "valuation", "invests")),
    ("company", ("layoffs", "partnership", "reorg", "appoints")),
]

_KNOWN_COMPANIES = (
    "OpenAI",
    "Anthropic",
    "Google",
    "DeepMind",
    "Microsoft",
    "Meta",
    "Nvidia",
    "Amazon",
    "Apple",
    "Mistral",
    "Perplexity",
)
_KNOWN_MODELS = ("GPT", "Claude", "Gemini", "Llama", "Mistral", "DeepSeek", "Qwen")


class EventExtractionAgent:
    """Deterministic event extraction fallback for the MVP pipeline."""

    def extract(self, items: Iterable[RawSourceItem]) -> list[Event]:
        events: list[Event] = []
        for item in items:
            if not item.id:
                continue
            text = _combined_text(item)
            entities = _extract_entities(text)
            event_id = _event_id(item)
            events.append(
                Event(
                    id=event_id,
                    title=item.title.strip(),
                    summary=_summary(item),
                    category=_category(text),
                    entities=entities,
                    related_source_item_ids=[item.id],
                    first_seen_at=item.published_at,
                    latest_seen_at=item.published_at,
                    importance_score=_importance_score(item, entities),
                    sentiment_score=0.0,
                    risk_score=0.0,
                )
            )
        return events


def _combined_text(item: RawSourceItem) -> str:
    return "\n".join([item.title, item.summary or "", item.content or "", " ".join(item.tags)])


def _event_id(item: RawSourceItem) -> str:
    normalized = re.sub(r"\W+", " ", item.title.casefold()).strip()
    digest = hashlib.sha256(f"{normalized}|{item.published_at.date()}".encode("utf-8")).hexdigest()
    return f"evt_{digest[:16]}"


def _summary(item: RawSourceItem) -> str:
    text = (item.summary or item.content or item.title).strip()
    return text[:400]


def _category(text: str) -> str:
    lowered = text.casefold()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return category
    return "other"


def _extract_entities(text: str) -> EventEntities:
    companies = sorted({name for name in _KNOWN_COMPANIES if re.search(rf"\b{re.escape(name)}\b", text)})
    models = sorted({name for name in _KNOWN_MODELS if re.search(rf"\b{re.escape(name)}\b", text, re.I)})
    topics = sorted(
        {
            topic
            for topic in ("agent", "coding", "evaluation", "safety", "LLM", "generative AI")
            if topic.casefold() in text.casefold()
        }
    )
    return EventEntities(companies=companies, products=[], people=[], models=models, topics=topics)


def _importance_score(item: RawSourceItem, entities: EventEntities) -> float:
    text_length = len((item.summary or "") + (item.content or ""))
    entity_bonus = min(0.25, 0.05 * (len(entities.companies) + len(entities.models)))
    source_bonus = 0.15 if item.source_type in {"official", "tech_media"} else 0.05
    length_bonus = min(0.25, text_length / 1200)
    return round(min(1.0, 0.35 + source_bonus + entity_bonus + length_bonus), 3)
