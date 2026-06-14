from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


SourceType = Literal["tech_media", "official", "social", "aggregator"]
MediumType = Literal[
    "article",
    "blog",
    "release",
    "paper",
    "social_post",
    "discussion",
    "ranking_item",
]
Language = Literal["zh", "en", "other"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RawSourceItem(BaseModel):
    id: str | None = None
    source_type: SourceType
    medium_type: MediumType
    source_name: str
    source_url: str
    title: str
    summary: str = ""
    content: str = ""
    language: Language = "other"
    published_at: datetime
    collected_at: datetime = Field(default_factory=utc_now)
    authors: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("published_at", "collected_at", mode="before")
    @classmethod
    def parse_datetime(cls, value: Any) -> datetime:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
        else:
            raise TypeError("datetime field must be a datetime or ISO string")
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @model_validator(mode="after")
    def fill_id_and_validate_text(self) -> "RawSourceItem":
        if not self.summary and not self.content:
            raise ValueError("RawSourceItem requires summary or content")
        if not self.id:
            digest = hashlib.sha256(self.source_url.encode("utf-8")).hexdigest()[:16]
            self.id = f"src_{digest}"
        return self

    @property
    def text_for_hash(self) -> str:
        return self.content or self.summary or self.title


class CollectionFailure(BaseModel):
    source_name: str
    reason: str


class RelevanceResult(BaseModel):
    is_ai_related: bool
    relevance_score: float
    matched_keywords: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)


class DeduplicationResult(BaseModel):
    items: list[RawSourceItem]
    duplicate_source_urls: list[str] = Field(default_factory=list)
    source_count_by_canonical_id: dict[str, int] = Field(default_factory=dict)


class CollectionSummary(BaseModel):
    started_at: datetime
    finished_at: datetime
    candidate_count: int
    ai_related_count: int
    deduplicated_count: int
    stored_count: int
    source_breakdown: dict[str, int] = Field(default_factory=dict)
    failed_sources: list[CollectionFailure] = Field(default_factory=list)


class CollectorResult(BaseModel):
    items: list[RawSourceItem] = Field(default_factory=list)
    failures: list[CollectionFailure] = Field(default_factory=list)

