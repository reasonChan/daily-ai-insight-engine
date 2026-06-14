from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from backend.app.schemas import DeduplicationMetadata, RawSourceItem


@dataclass
class DeduplicationResult:
    unique_items: List[RawSourceItem]
    duplicate_metadata: Dict[str, DeduplicationMetadata] = field(default_factory=dict)
    duplicate_count: int = 0


class SourceDeduplicator:
    def deduplicate(self, items: Iterable[RawSourceItem]) -> DeduplicationResult:
        unique_items: List[RawSourceItem] = []
        duplicate_metadata: Dict[str, DeduplicationMetadata] = {}
        indexes: Dict[str, str] = {}
        canonical_by_id: Dict[str, RawSourceItem] = {}
        duplicate_count = 0

        for item in items:
            keys = self._dedup_keys(item)
            canonical_id = self._find_canonical_id(keys, indexes)
            if canonical_id is None:
                unique_items.append(item)
                canonical_by_id[item.id] = item
                for key in keys:
                    indexes[key] = item.id
                duplicate_metadata[item.id] = DeduplicationMetadata(
                    canonical_item_id=item.id,
                    duplicate_source_urls=[item.source_url],
                    source_count=1,
                )
                continue

            duplicate_count += 1
            metadata = duplicate_metadata[canonical_id]
            if item.source_url not in metadata.duplicate_source_urls:
                metadata.duplicate_source_urls.append(item.source_url)
            metadata.source_count += 1
            for key in keys:
                indexes.setdefault(key, canonical_id)

            canonical = canonical_by_id[canonical_id]
            self._merge_item_metadata(canonical, item)

        return DeduplicationResult(
            unique_items=unique_items,
            duplicate_metadata=duplicate_metadata,
            duplicate_count=duplicate_count,
        )

    def _dedup_keys(self, item: RawSourceItem) -> Tuple[str, ...]:
        keys = [
            "url:" + self.normalize_url(item.source_url),
            "title:" + self.normalize_title(item.title),
        ]
        content_hash = self.content_hash(item)
        if content_hash:
            keys.append("content:" + content_hash)
        return tuple(key for key in keys if not key.endswith(":"))

    @staticmethod
    def _find_canonical_id(keys: Tuple[str, ...], indexes: Dict[str, str]) -> Optional[str]:
        for key in keys:
            canonical_id = indexes.get(key)
            if canonical_id:
                return canonical_id
        return None

    @staticmethod
    def normalize_url(url: str) -> str:
        split = urlsplit(url.strip())
        query = urlencode(sorted(parse_qsl(split.query, keep_blank_values=True)))
        path = split.path.rstrip("/") or "/"
        return urlunsplit((split.scheme.lower(), split.netloc.lower(), path, query, ""))

    @staticmethod
    def normalize_title(title: str) -> str:
        lowered = title.casefold()
        stripped = re.sub(r"[^\w\u4e00-\u9fff]+", " ", lowered)
        return re.sub(r"\s+", " ", stripped).strip()

    @staticmethod
    def content_hash(item: RawSourceItem) -> Optional[str]:
        content = item.content or item.summary or ""
        normalized = re.sub(r"\s+", " ", content.casefold()).strip()
        if not normalized:
            return None
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _merge_item_metadata(canonical: RawSourceItem, duplicate: RawSourceItem) -> None:
        for author in duplicate.authors:
            if author not in canonical.authors:
                canonical.authors.append(author)
        for tag in duplicate.tags:
            if tag not in canonical.tags:
                canonical.tags.append(tag)
