"""arXiv API collector."""

from __future__ import annotations

from typing import Any
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


ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _text(entry: ElementTree.Element, name: str) -> str:
    child = entry.find(f"atom:{name}", ATOM_NS)
    return clean_text(child.text if child is not None else "")


def _authors(entry: ElementTree.Element) -> list[str]:
    authors: list[str] = []
    for author in entry.findall("atom:author", ATOM_NS):
        name = author.find("atom:name", ATOM_NS)
        if name is not None and name.text:
            authors.append(clean_text(name.text))
    return authors


def _categories(entry: ElementTree.Element) -> list[str]:
    return [
        category.attrib["term"]
        for category in entry.findall("atom:category", ATOM_NS)
        if category.attrib.get("term")
    ]


def _paper_id(source_url: str) -> str:
    return source_url.rstrip("/").rsplit("/", 1)[-1]


def collect(source: dict[str, Any], limit: int = 20) -> dict[str, Any]:
    source_name = source_value(source, "name", "arXiv")
    query = source_value(source, "query", "cat:cs.AI OR cat:cs.CL OR cat:cs.LG OR cat:cs.CV")

    result = fetch_text(
        ARXIV_API_URL,
        params={
            "search_query": query,
            "start": 0,
            "max_results": limit,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        },
    )
    if not result.get("ok"):
        error = result.get("error") or {"type": "unknown_error", "message": "arXiv fetch failed"}
        return make_error(source_name, error.get("type", "http_error"), error.get("message", ""), url=result.get("url"))

    try:
        root = ElementTree.fromstring(result.get("text") or "")
    except ElementTree.ParseError as exc:
        return make_error(source_name, "xml_parse_error", str(exc), url=result.get("url"))

    items: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        source_url = _text(entry, "id")
        title = _text(entry, "title")
        abstract = _text(entry, "summary")
        categories = _categories(entry)
        paper_id = _paper_id(source_url)

        if not title or not source_url:
            continue

        items.append(
            make_raw_source_item(
                source_type="official",
                medium_type="paper",
                source_name="arXiv",
                source_url=source_url,
                title=title,
                summary=abstract,
                content=abstract,
                language=source_value(source, "language", "en"),
                published_at=parse_datetime(_text(entry, "published")),
                raw_payload={
                    "paper_id": paper_id,
                    "updated_at": parse_datetime(_text(entry, "updated")),
                    "categories": categories,
                },
                item_id=paper_id,
                authors=_authors(entry),
                tags=categories,
                item_type="paper",
                abstract=abstract,
                categories=categories,
                paper_id=paper_id,
                updated_at=parse_datetime(_text(entry, "updated")),
            )
        )

    return make_collection_result(source_name=source_name, items=items)


class ArxivCollector(SourceCollector):
    def collect(self, source: Any, limit: int):
        return to_collector_result(collect(source_config_to_dict(source), limit))
