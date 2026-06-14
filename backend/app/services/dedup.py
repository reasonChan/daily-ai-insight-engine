from __future__ import annotations

import hashlib
import re

from backend.app.schemas.source import DeduplicationResult, RawSourceItem


def content_hash(item: RawSourceItem) -> str:
    return hashlib.sha256(item.text_for_hash.encode("utf-8")).hexdigest()


def deduplicate_items(items: list[RawSourceItem]) -> DeduplicationResult:
    seen_urls: dict[str, str] = {}
    seen_titles: dict[str, str] = {}
    seen_hashes: dict[str, str] = {}
    canonical_counts: dict[str, int] = {}
    duplicate_urls: list[str] = []
    unique: list[RawSourceItem] = []

    for item in items:
        canonical_id = _find_canonical(item, seen_urls, seen_titles, seen_hashes)
        if canonical_id:
            canonical_counts[canonical_id] = canonical_counts.get(canonical_id, 1) + 1
            duplicate_urls.append(item.source_url)
            continue

        assert item.id is not None
        url_key = _normalize_url(item.source_url)
        title_key = normalize_title(item.title)
        hash_key = content_hash(item)
        seen_urls[url_key] = item.id
        seen_titles[title_key] = item.id
        seen_hashes[hash_key] = item.id
        canonical_counts[item.id] = 1
        unique.append(item)

    return DeduplicationResult(
        items=unique,
        duplicate_source_urls=duplicate_urls,
        source_count_by_canonical_id=canonical_counts,
    )


def _find_canonical(
    item: RawSourceItem,
    seen_urls: dict[str, str],
    seen_titles: dict[str, str],
    seen_hashes: dict[str, str],
) -> str | None:
    return (
        seen_urls.get(_normalize_url(item.source_url))
        or seen_titles.get(normalize_title(item.title))
        or seen_hashes.get(content_hash(item))
    )


def normalize_title(title: str) -> str:
    return re.sub(r"\W+", " ", title.casefold()).strip()


def _normalize_url(url: str) -> str:
    base = url.split("#", 1)[0]
    return base.rstrip("/")

