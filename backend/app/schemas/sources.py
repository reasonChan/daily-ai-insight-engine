from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, root_validator, validator


class SourceType(str, Enum):
    TECH_MEDIA = "tech_media"
    OFFICIAL = "official"
    SOCIAL = "social"
    AGGREGATOR = "aggregator"


class MediumType(str, Enum):
    ARTICLE = "article"
    BLOG = "blog"
    RELEASE = "release"
    PAPER = "paper"
    SOCIAL_POST = "social_post"
    DISCUSSION = "discussion"
    RANKING_ITEM = "ranking_item"


class RawSourceItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_type: SourceType
    medium_type: MediumType
    source_name: str
    source_url: str
    title: str
    summary: Optional[str] = None
    content: Optional[str] = None
    language: str = "other"
    published_at: datetime
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    authors: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    raw_payload: Dict[str, Any] = Field(default_factory=dict)

    @validator("title", "source_name", "source_url")
    def required_text(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("field must not be empty")
        return value.strip()

    @validator("language")
    def normalize_language(cls, value: str) -> str:
        normalized = (value or "other").strip().lower()
        return normalized if normalized in {"zh", "en"} else "other"

    @root_validator(skip_on_failure=True)
    def summary_or_content_required(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        summary = (values.get("summary") or "").strip()
        content = (values.get("content") or "").strip()
        if not summary and not content:
            raise ValueError("RawSourceItem requires summary or content")
        values["summary"] = summary or None
        values["content"] = content or None
        return values


class SourceConfig(BaseModel):
    name: str
    source_type: SourceType = Field(alias="type")
    medium: MediumType
    method: str
    url: Optional[str] = None
    query: Optional[str] = None
    language: str = "other"
    enabled: bool = True
    options: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        validate_by_name = True
        use_enum_values = True

    @validator("name", "method")
    def config_text_required(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("field must not be empty")
        return value.strip()

    @root_validator(skip_on_failure=True)
    def url_or_query_required(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if not values.get("url") and not values.get("query"):
            raise ValueError("SourceConfig requires url or query")
        return values


class RelevanceResult(BaseModel):
    is_ai_related: bool
    relevance_score: float = Field(ge=0.0, le=1.0)
    matched_keywords: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)


class DeduplicationMetadata(BaseModel):
    canonical_item_id: str
    duplicate_source_urls: List[str] = Field(default_factory=list)
    source_count: int = 1


class FailedSource(BaseModel):
    source_name: str
    reason: str


class CollectionSummary(BaseModel):
    started_at: datetime
    finished_at: datetime
    candidate_count: int = 0
    ai_related_count: int = 0
    deduplicated_count: int = 0
    stored_count: int = 0
    source_breakdown: Dict[str, int] = Field(default_factory=dict)
    failed_sources: List[FailedSource] = Field(default_factory=list)
