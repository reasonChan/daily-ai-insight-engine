"""RSS and Atom collector."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus
from xml.etree import ElementTree

from backend.app.collectors.base import SourceCollector
from backend.app.collectors.schema import (
    make_collection_result,
    make_error,
    make_raw_source_item,
    source_config_to_dict,
    to_collector_result,
)
from backend.app.collectors.utils import clean_text, parse_datetime, source_value
from backend.app.core.http import fetch_text


GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"


def _child_text(element: ElementTree.Element, names: tuple[str, ...]) -> str:
    for child in list(element):
        local_name = child.tag.rsplit("}", 1)[-1]
        if local_name in names and child.text:
            return child.text
    return ""


def _link(element: ElementTree.Element) -> str:
    for child in list(element):
        local_name = child.tag.rsplit("}", 1)[-1]
        if local_name == "link":
            return child.attrib.get("href") or (child.text or "")
    return ""


def _raw_payload(element: ElementTree.Element) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for child in list(element):
        key = child.tag.rsplit("}", 1)[-1]
        payload[key] = child.attrib if child.attrib else clean_text(child.text)
    return payload


def _rss_entries(root: ElementTree.Element) -> list[ElementTree.Element]:
    channel = root.find("channel")
    if channel is not None:
        return list(channel.findall("item"))
    return [entry for entry in root.iter() if entry.tag.rsplit("}", 1)[-1] == "entry"]


def _rss_url(source: dict[str, Any]) -> str:
    if source.get("url"):
        return str(source["url"])
    query = quote_plus(str(source.get("query", "artificial intelligence")))
    return f"{GOOGLE_NEWS_RSS_URL}?q={query}&hl=en-US&gl=US&ceid=US:en"


def collect(source: dict[str, Any], limit: int = 20) -> dict[str, Any]:
    """Collect normalized items from an RSS or Atom feed."""

    source_name = source_value(source, "name", "RSS")
    result = fetch_text(_rss_url(source))
    if not result.get("ok"):
        error = result.get("error") or {"type": "unknown_error", "message": "RSS fetch failed"}
        return make_error(source_name, error.get("type", "http_error"), error.get("message", ""), url=result.get("url"))

    try:
        root = ElementTree.fromstring(result.get("text") or "")
    except ElementTree.ParseError as exc:
        return make_error(source_name, "xml_parse_error", str(exc), url=result.get("url"))

    items: list[dict[str, Any]] = []
    for entry in _rss_entries(root)[:limit]:
        title = clean_text(_child_text(entry, ("title",)))
        url = _link(entry) or clean_text(_child_text(entry, ("guid", "id")))
        summary = clean_text(_child_text(entry, ("description", "summary", "subtitle"))) or title
        content = clean_text(_child_text(entry, ("encoded", "content"))) or summary
        published_at = parse_datetime(_child_text(entry, ("pubDate", "published", "updated")))

        if not title or not url:
            continue

        items.append(
            make_raw_source_item(
                source_type=source_value(source, "type", "tech_media"),
                medium_type=source_value(source, "medium", "article"),
                source_name=source_name,
                source_url=url,
                title=title,
                summary=summary,
                content=content,
                language=source_value(source, "language", "other"),
                published_at=published_at,
                raw_payload=_raw_payload(entry),
            )
        )

    return make_collection_result(source_name=source_name, items=items)


class RssCollector(SourceCollector):
    def collect(self, source: Any, limit: int):
        return to_collector_result(collect(source_config_to_dict(source), limit))
