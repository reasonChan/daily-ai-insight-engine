"""Reddit JSON collector."""

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


def collect(source: dict[str, Any], limit: int = 20) -> dict[str, Any]:
    source_name = source_value(source, "name", "Reddit")
    url = str(source.get("url") or "https://www.reddit.com/r/artificial/top.json")

    result = fetch_json(url, params={"limit": limit, "t": source.get("time_window", "day")})
    if not result.get("ok"):
        error = result.get("error") or {"type": "unknown_error", "message": "Reddit fetch failed"}
        return make_error(source_name, error.get("type", "http_error"), error.get("message", ""), url=result.get("url"))

    payload = result.get("json") or {}
    if not isinstance(payload, dict):
        return make_error(source_name, "unexpected_payload", "Reddit API returned non-object payload")
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        return make_error(source_name, "unexpected_payload", "Reddit API payload missing data object")
    posts = data.get("children", [])
    if not isinstance(posts, list):
        return make_error(source_name, "unexpected_payload", "Reddit API payload missing children list")
    items: list[dict[str, Any]] = []
    for post in posts[:limit]:
        if not isinstance(post, dict):
            continue
        data = post.get("data") or {}
        if not isinstance(data, dict):
            continue
        title = clean_text(data.get("title"))
        permalink = data.get("permalink")
        source_url = data.get("url")
        reddit_url = f"https://www.reddit.com{permalink}" if permalink else source_url

        if not title or not reddit_url:
            continue

        content = clean_text(data.get("selftext"))
        subreddit = data.get("subreddit_name_prefixed") or data.get("subreddit")
        items.append(
            make_raw_source_item(
                source_type="social",
                medium_type="discussion",
                source_name=source_name,
                source_url=reddit_url,
                title=title,
                summary=content[:300] or title,
                content=content,
                language=source_value(source, "language", "en"),
                published_at=parse_datetime(data.get("created_utc")),
                raw_payload=data,
                item_id=data.get("name") or data.get("id") or reddit_url,
                authors=[data["author"]] if data.get("author") else [],
                item_type="social_post",
                platform="reddit",
                author=data.get("author"),
                engagement={
                    "upvotes": data.get("ups", 0),
                    "comments": data.get("num_comments", 0),
                    "shares": 0,
                    "likes": 0,
                    "score": data.get("score", 0),
                },
                discussion_context={
                    "community": subreddit,
                    "topic": "ai",
                    "sentiment_hint": "neutral",
                },
                credibility_level="discussion_signal",
                requires_verification=True,
                original_source_url=source_url,
            )
        )

    return make_collection_result(source_name=source_name, items=items)


class RedditCollector(SourceCollector):
    def collect(self, source: Any, limit: int):
        return to_collector_result(collect(source_config_to_dict(source), limit))
