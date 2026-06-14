"""Hacker News Algolia collector."""

from __future__ import annotations

from typing import Any

from backend.app.collectors.base import SourceCollector
from backend.app.collectors.schema import (
    make_collection_result,
    make_error,
    make_raw_source_item,
    source_config_to_dict,
    to_collector_result,
)
from backend.app.collectors.utils import clean_text, parse_datetime, source_value
from backend.app.core.http import fetch_json


HN_API_URL = "https://hn.algolia.com/api/v1/search_by_date"


def collect(source: dict[str, Any], limit: int = 20) -> dict[str, Any]:
    source_name = source_value(source, "name", "Hacker News")
    query = source_value(source, "query", "AI OR LLM OR OpenAI OR Claude OR agents")

    result = fetch_json(HN_API_URL, params={"query": query, "tags": "story", "hitsPerPage": limit})
    if not result.get("ok"):
        error = result.get("error") or {"type": "unknown_error", "message": "Hacker News fetch failed"}
        return make_error(source_name, error.get("type", "http_error"), error.get("message", ""), url=result.get("url"))

    payload = result.get("json") or {}
    if not isinstance(payload, dict):
        return make_error(source_name, "unexpected_payload", "Hacker News API returned non-object payload")

    items: list[dict[str, Any]] = []
    hits = payload.get("hits", [])
    if not isinstance(hits, list):
        return make_error(source_name, "unexpected_payload", "Hacker News API payload missing hits list")
    for rank, hit in enumerate(hits, start=1):
        if not isinstance(hit, dict):
            continue
        title = clean_text(hit.get("title") or hit.get("story_title"))
        source_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        if not title or not source_url:
            continue

        points = hit.get("points") or 0
        comments = hit.get("num_comments") or 0
        items.append(
            make_raw_source_item(
                source_type="aggregator",
                medium_type="ranking_item",
                source_name=source_name,
                source_url=source_url,
                title=title,
                summary=clean_text(hit.get("story_text")) or title,
                content=clean_text(hit.get("story_text")),
                language=source_value(source, "language", "en"),
                published_at=parse_datetime(hit.get("created_at")),
                raw_payload=hit,
                authors=[hit["author"]] if hit.get("author") else [],
                item_type="aggregated_item",
                platform="hacker_news",
                original_source_name="Hacker News",
                original_source_url=f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                ranking={
                    "rank": rank,
                    "score": points,
                    "comments": comments,
                    "votes": points,
                },
                aggregation_context={
                    "query": query,
                    "topic": "ai",
                },
            )
        )

    return make_collection_result(source_name=source_name, items=items)


class HackerNewsCollector(SourceCollector):
    def collect(self, source: Any, limit: int):
        return to_collector_result(collect(source_config_to_dict(source), limit))
