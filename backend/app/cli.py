from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.agents import DailyAnalysisAgent, EventExtractionAgent, InsightAnalysisAgent, RiskAssessmentAgent
from backend.app.rag import chunk_source_item, write_chunks
from backend.app.reports import DailyReportGenerator
from backend.app.schemas.analysis import PipelineRun
from backend.app.pipelines.collection import select_hot_items
from backend.app.services.event_clustering import EventClusterer
from backend.app.storage import RawSourceItem, SQLiteAnalysisStore, SQLiteMetadataStore


AI_KEYWORDS = [
    "AI",
    "artificial intelligence",
    "generative AI",
    "LLM",
    "large language model",
    "agent",
    "OpenAI",
    "Anthropic",
    "Claude",
    "Gemini",
    "DeepMind",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def score_ai_relevance(item: RawSourceItem) -> tuple[float, list[str]]:
    haystack = "\n".join([item.title, item.summary or "", item.content or ""]).lower()
    matches = sorted(
        {keyword for keyword in AI_KEYWORDS if keyword.lower() in haystack},
        key=str.lower,
    )
    score = min(1.0, len(matches) / 4)
    return score, matches


def load_fixture_items(path: str | Path) -> list[RawSourceItem]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    records = payload["items"] if isinstance(payload, dict) else payload
    return [RawSourceItem(**record) for record in records]


def _normalized_title(title: str) -> str:
    return re.sub(r"\W+", " ", title.casefold()).strip()


def _content_hash(item: RawSourceItem) -> str:
    text = "\n".join([item.title, item.summary or "", item.content or ""])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def deduplicate(items: list[RawSourceItem]) -> list[RawSourceItem]:
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    seen_hashes: set[str] = set()
    deduped: list[RawSourceItem] = []
    for item in items:
        normalized_url = item.source_url.split("#", 1)[0].rstrip("/").casefold()
        normalized_title = _normalized_title(item.title)
        item_hash = _content_hash(item)
        if (
            normalized_url in seen_urls
            or normalized_title in seen_titles
            or item_hash in seen_hashes
        ):
            continue
        seen_urls.add(normalized_url)
        seen_titles.add(normalized_title)
        seen_hashes.add(item_hash)
        deduped.append(item)
    return deduped


def run_collection_pipeline(
    items: list[RawSourceItem],
    db_path: str | Path,
    rag_dir: str | Path,
    min_relevance_score: float = 0.25,
    target_limit: int | None = 20,
    max_items_per_source: int | None = 3,
    min_chinese_items: int = 3,
) -> dict[str, Any]:
    started_at = _utc_now()
    scored: list[tuple[RawSourceItem, float, list[str]]] = []
    for item in items:
        score, keywords = score_ai_relevance(item)
        if score >= min_relevance_score:
            scored.append((item, score, keywords))

    deduplicated_items = select_hot_items(
        deduplicate([item for item, _, _ in scored]),
        relevance_by_id={item.id or "": score for item, score, _ in scored},
        target_limit=target_limit,
        max_items_per_source=max_items_per_source,
        min_chinese_items=min_chinese_items,
    )
    score_by_id = {item.id: score for item, score, _ in scored}
    store = SQLiteMetadataStore(db_path)

    stored_count = 0
    chunk_count = 0
    source_breakdown: Counter[str] = Counter()
    for item in deduplicated_items:
        store.upsert_item(item, ai_relevance_score=score_by_id.get(item.id or "", 0.0))
        chunks = chunk_source_item(item)
        write_chunks(chunks, rag_dir)
        stored_count += 1
        chunk_count += len(chunks)
        source_breakdown[str(item.source_type)] += 1

    finished_at = _utc_now()
    return {
        "started_at": _iso(started_at),
        "finished_at": _iso(finished_at),
        "candidate_count": len(items),
        "ai_related_count": len(scored),
        "deduplicated_count": len(deduplicated_items),
        "stored_count": stored_count,
        "chunk_count": chunk_count,
        "source_breakdown": dict(source_breakdown),
        "failed_sources": [],
        "db_path": str(db_path),
        "rag_dir": str(rag_dir),
    }


def run_daily_report_pipeline(
    items: list[RawSourceItem],
    db_path: str | Path,
    rag_dir: str | Path,
    report_dir: str | Path,
    min_relevance_score: float = 0.25,
    target_limit: int | None = 20,
    max_items_per_source: int | None = 3,
    min_chinese_items: int = 3,
) -> dict[str, Any]:
    summary = run_collection_pipeline(
        items=items,
        db_path=db_path,
        rag_dir=rag_dir,
        min_relevance_score=min_relevance_score,
        target_limit=target_limit,
        max_items_per_source=max_items_per_source,
        min_chinese_items=min_chinese_items,
    )
    deduped_items = _items_stored_by_pipeline(
        items,
        min_relevance_score,
        target_limit,
        max_items_per_source,
        min_chinese_items,
    )
    return run_analysis_report_pipeline(
        items=deduped_items,
        summary=summary,
        db_path=db_path,
        report_dir=report_dir,
    )


def run_analysis_report_pipeline(
    items: list[RawSourceItem],
    summary: dict[str, Any],
    db_path: str | Path,
    report_dir: str | Path,
) -> dict[str, Any]:
    event_candidates = EventExtractionAgent().extract(items)
    events = EventClusterer().cluster(event_candidates)
    risk_agent = RiskAssessmentAgent()
    risks = [risk_agent.assess(event, items) for event in events]
    risk_by_event_id = {risk.event_id: risk for risk in risks}
    events = [
        event.model_copy(update={"risk_score": risk_by_event_id[event.id].overall_risk})
        for event in events
    ]
    insight_agent = InsightAnalysisAgent()
    insights = [insight_agent.analyze(event, items) for event in events]
    report_date = datetime.now(timezone.utc).date()
    daily_analysis = DailyAnalysisAgent().analyze(
        report_date=report_date,
        events=events,
        insights=insights,
        risks=risks,
        source_items=items,
    )
    report = DailyReportGenerator().generate(
        report_date=report_date,
        events=events,
        insights=insights,
        risks=risks,
        source_items=items,
        summary=summary,
        daily_analysis=daily_analysis,
        output_dir=report_dir,
    )

    store = SQLiteAnalysisStore(db_path)
    store.upsert_pipeline_run(
        PipelineRun(
            id=f"run_{summary['started_at'].replace(':', '').replace('-', '').replace('.', '')}",
            started_at=summary["started_at"],
            finished_at=summary["finished_at"],
            status="success",
            candidate_count=summary["candidate_count"],
            ai_related_count=summary["ai_related_count"],
            deduplicated_count=summary["deduplicated_count"],
            stored_count=summary["stored_count"],
            failed_sources=summary["failed_sources"],
            summary=summary,
        )
    )
    for event in events:
        store.upsert_event(event)
    for insight in insights:
        store.upsert_insight(insight)
    for risk in risks:
        store.upsert_risk_assessment(risk)
    store.upsert_daily_report(report)

    return {
        **summary,
        "event_count": len(events),
        "insight_count": len(insights),
        "risk_assessment_count": len(risks),
        "report_json_path": report.json_path,
        "report_markdown_path": report.markdown_path,
    }


def _items_stored_by_pipeline(
    items: list[RawSourceItem],
    min_relevance_score: float,
    target_limit: int | None,
    max_items_per_source: int | None,
    min_chinese_items: int,
) -> list[RawSourceItem]:
    scored = [(item, score_ai_relevance(item)[0]) for item in items]
    ai_related = [item for item, score in scored if score >= min_relevance_score]
    return select_hot_items(
        deduplicate(ai_related),
        relevance_by_id={item.id or "": score for item, score in scored},
        target_limit=target_limit,
        max_items_per_source=max_items_per_source,
        min_chinese_items=min_chinese_items,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily AI Insight Engine CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect", help="Run the data source collection pipeline")
    collect.add_argument("--config", default="configs/sources.yaml")
    collect.add_argument("--db", default="data/source_items.sqlite")
    collect.add_argument("--chunks", default="data/rag/chunks.jsonl")
    collect.add_argument("--summary", default="reports/daily/latest_collection_summary.json")
    collect.add_argument("--per-source-limit", type=int, default=10)
    collect.add_argument("--target-limit", type=int, default=20)
    collect.add_argument("--max-items-per-source", type=int, default=3)
    collect.add_argument("--min-chinese-items", type=int, default=3)
    collect.add_argument(
        "--fixture",
        default="",
        help="Run from an offline RawSourceItem JSON fixture instead of live collectors.",
    )
    collect.add_argument("--rag-dir", default="data/rag")
    collect.add_argument("--min-relevance-score", type=float, default=0.25)
    collect.add_argument(
        "--with-report",
        action="store_true",
        help="Also extract events, insights, risks, and daily report artifacts.",
    )
    collect.add_argument("--report-dir", default="reports/daily")

    args = parser.parse_args()
    if args.command == "collect":
        if args.fixture:
            fixture_items = load_fixture_items(args.fixture)
            if args.with_report:
                summary = run_daily_report_pipeline(
                    items=fixture_items,
                    db_path=Path(args.db),
                    rag_dir=Path(args.rag_dir),
                    report_dir=Path(args.report_dir),
                    min_relevance_score=args.min_relevance_score,
                    target_limit=args.target_limit,
                    max_items_per_source=args.max_items_per_source,
                    min_chinese_items=args.min_chinese_items,
                )
            else:
                summary = run_collection_pipeline(
                    items=fixture_items,
                    db_path=Path(args.db),
                    rag_dir=Path(args.rag_dir),
                    min_relevance_score=args.min_relevance_score,
                    target_limit=args.target_limit,
                    max_items_per_source=args.max_items_per_source,
                    min_chinese_items=args.min_chinese_items,
                )
            if args.summary:
                summary_path = Path(args.summary)
                summary_path.parent.mkdir(parents=True, exist_ok=True)
                summary_path.write_text(
                    json.dumps(summary, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            return 0

        from backend.app.pipelines.collection import CollectionPipeline

        summary, _items = CollectionPipeline().run(
            config_path=Path(args.config),
            db_path=Path(args.db),
            chunks_path=Path(args.chunks),
            summary_path=Path(args.summary),
            per_source_limit=args.per_source_limit,
            target_limit=args.target_limit,
            max_items_per_source=args.max_items_per_source,
            min_chinese_items=args.min_chinese_items,
        )
        summary_payload = summary.model_dump(mode="json")
        if args.with_report:
            summary_payload = run_analysis_report_pipeline(
                items=_items,
                summary=summary_payload,
                db_path=Path(args.db),
                report_dir=Path(args.report_dir),
            )
            if args.summary:
                summary_path = Path(args.summary)
                summary_path.parent.mkdir(parents=True, exist_ok=True)
                summary_path.write_text(
                    json.dumps(summary_payload, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
        print(json.dumps(summary_payload, indent=2, ensure_ascii=False))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
