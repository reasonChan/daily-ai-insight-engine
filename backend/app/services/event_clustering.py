from __future__ import annotations

import re
from collections import defaultdict

from backend.app.schemas.analysis import Event, EventEntities


class EventClusterer:
    def cluster(self, events: list[Event]) -> list[Event]:
        clusters: list[list[Event]] = []
        for event in sorted(events, key=lambda item: item.first_seen_at):
            target = next((cluster for cluster in clusters if _similar(event, cluster[0])), None)
            if target is None:
                clusters.append([event])
            else:
                target.append(event)
        return [_merge(cluster) for cluster in clusters]


def _similar(left: Event, right: Event) -> bool:
    if left.category != right.category:
        return False
    days_apart = abs((left.first_seen_at.date() - right.first_seen_at.date()).days)
    if days_apart > 2:
        return False
    title_overlap = _jaccard(_tokens(left.title), _tokens(right.title))
    entity_overlap = _entity_overlap(left.entities, right.entities)
    return title_overlap >= 0.55 or (title_overlap >= 0.32 and entity_overlap)


def _merge(cluster: list[Event]) -> Event:
    primary = max(cluster, key=lambda event: (event.importance_score, len(event.summary)))
    source_ids: list[str] = []
    for event in cluster:
        for source_id in event.related_source_item_ids:
            if source_id not in source_ids:
                source_ids.append(source_id)
    first_seen = min(event.first_seen_at for event in cluster)
    latest_seen = max(event.latest_seen_at for event in cluster)
    return primary.model_copy(
        update={
            "related_source_item_ids": source_ids,
            "first_seen_at": first_seen,
            "latest_seen_at": latest_seen,
            "importance_score": round(max(event.importance_score for event in cluster), 3),
            "risk_score": round(max(event.risk_score for event in cluster), 3),
            "entities": _merge_entities([event.entities for event in cluster]),
        }
    )


def _tokens(text: str) -> set[str]:
    stopwords = {"the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "new"}
    return {token for token in re.findall(r"[a-z0-9]+", text.casefold()) if token not in stopwords}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _entity_overlap(left: EventEntities, right: EventEntities) -> bool:
    return bool(set(left.companies) & set(right.companies) or set(left.models) & set(right.models))


def _merge_entities(entities: list[EventEntities]) -> EventEntities:
    merged: dict[str, set[str]] = defaultdict(set)
    for entity in entities:
        merged["companies"].update(entity.companies)
        merged["products"].update(entity.products)
        merged["people"].update(entity.people)
        merged["models"].update(entity.models)
        merged["topics"].update(entity.topics)
    return EventEntities(**{key: sorted(value) for key, value in merged.items()})
