from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from backend.app.collectors.registry import CollectorRegistry
from backend.app.core.config import load_sources_config
from backend.app.rag.chunking import write_chunks_jsonl
from backend.app.schemas.source import CollectionFailure, CollectionSummary, RawSourceItem
from backend.app.services.dedup import deduplicate_items
from backend.app.services.relevance import evaluate_ai_relevance
from backend.app.storage.sqlite_store import SQLiteSourceStore


class CollectionPipeline:
    def __init__(self, registry: CollectorRegistry | None = None):
        self.registry = registry or CollectorRegistry()

    def run(
        self,
        config_path: str | Path,
        db_path: str | Path = "data/source_items.sqlite",
        chunks_path: str | Path = "data/rag/chunks.jsonl",
        summary_path: str | Path | None = "reports/daily/latest_collection_summary.json",
        per_source_limit: int = 10,
        target_limit: int | None = 20,
        max_items_per_source: int | None = 3,
        min_chinese_items: int = 3,
    ) -> tuple[CollectionSummary, list[RawSourceItem]]:
        started = datetime.now(timezone.utc)
        sources = [source for source in load_sources_config(config_path).sources if source.enabled]
        candidates: list[RawSourceItem] = []
        failures: list[CollectionFailure] = []

        for source in sources:
            collector = self.registry.resolve(source)
            result = collector.collect(source, source.limit or per_source_limit)
            candidates.extend(result.items)
            failures.extend(result.failures)

        relevance_by_id = {}
        ai_related = []
        for item in candidates:
            relevance = evaluate_ai_relevance(item)
            if item.id:
                relevance_by_id[item.id] = relevance.relevance_score
                item.raw_payload = {
                    **item.raw_payload,
                    "ai_relevance": relevance.model_dump(),
                }
            if relevance.is_ai_related:
                ai_related.append(item)

        deduped = select_hot_items(
            deduplicate_items(ai_related).items,
            relevance_by_id=relevance_by_id,
            target_limit=target_limit,
            max_items_per_source=max_items_per_source,
            min_chinese_items=min_chinese_items,
        )

        stored_count = SQLiteSourceStore(db_path).upsert_items(deduped, relevance_by_id)
        write_chunks_jsonl(deduped, chunks_path)

        source_breakdown: dict[str, int] = {}
        for item in deduped:
            source_breakdown[item.source_type] = source_breakdown.get(item.source_type, 0) + 1

        summary = CollectionSummary(
            started_at=started,
            finished_at=datetime.now(timezone.utc),
            candidate_count=len(candidates),
            ai_related_count=len(ai_related),
            deduplicated_count=len(deduped),
            stored_count=stored_count,
            source_breakdown=source_breakdown,
            failed_sources=failures,
        )
        if summary_path:
            _write_summary(summary, summary_path)
        return summary, deduped


def select_hot_items(
    items: list[RawSourceItem],
    relevance_by_id: dict[str, float],
    target_limit: int | None = 20,
    max_items_per_source: int | None = 3,
    min_chinese_items: int = 3,
) -> list[RawSourceItem]:
    ranked = sorted(
        items,
        key=lambda item: (
            _hotness_score(item, relevance_by_id),
            item.published_at,
            item.title,
        ),
        reverse=True,
    )
    selected: list[RawSourceItem] = []
    counts_by_source: dict[str, int] = {}
    selected_ids: set[str] = set()

    if min_chinese_items > 0:
        for item in ranked:
            if item.language != "zh":
                continue
            if not _can_select(item, counts_by_source, max_items_per_source):
                continue
            selected.append(item)
            if item.id:
                selected_ids.add(item.id)
            _count_selected(item, counts_by_source)
            if len([selected_item for selected_item in selected if selected_item.language == "zh"]) >= min_chinese_items:
                break
            if target_limit is not None and len(selected) >= target_limit:
                return selected

    for item in ranked:
        if item.id in selected_ids:
            continue
        if not _can_select(item, counts_by_source, max_items_per_source):
            continue
        selected.append(item)
        if item.id:
            selected_ids.add(item.id)
        _count_selected(item, counts_by_source)
        if target_limit is not None and len(selected) >= target_limit:
            break
    return selected


def _can_select(
    item: RawSourceItem,
    counts_by_source: dict[str, int],
    max_items_per_source: int | None,
) -> bool:
    source_name = item.source_name or item.source_url
    return max_items_per_source is None or counts_by_source.get(source_name, 0) < max_items_per_source


def _count_selected(item: RawSourceItem, counts_by_source: dict[str, int]) -> None:
    source_name = item.source_name or item.source_url
    counts_by_source[source_name] = counts_by_source.get(source_name, 0) + 1


def _hotness_score(item: RawSourceItem, relevance_by_id: dict[str, float]) -> float:
    relevance = relevance_by_id.get(item.id or "", 0.0)
    source_weight = {
        "official": 0.22,
        "tech_media": 0.18,
        "aggregator": 0.12,
        "social": 0.10,
    }.get(str(item.source_type), 0.12)
    content_length = len((item.summary or "") + (item.content or ""))
    content_quality = min(0.18, content_length / 3000)
    language_diversity = 0.08 if item.language == "zh" else 0.0
    raw_hotness = item.raw_payload.get("points") or item.raw_payload.get("score") or item.raw_payload.get("comments") or 0
    try:
        engagement = min(0.12, float(raw_hotness) / 1000)
    except (TypeError, ValueError):
        engagement = 0.0
    return round(relevance * 0.48 + source_weight + content_quality + engagement + language_diversity, 4)


def _write_summary(summary: CollectionSummary, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
