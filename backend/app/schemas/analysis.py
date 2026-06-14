from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


EventCategory = Literal[
    "model",
    "product",
    "research",
    "funding",
    "policy",
    "safety",
    "infrastructure",
    "company",
    "other",
]
PipelineRunStatus = Literal["success", "partial_success", "failed"]
EventSourceRelationship = Literal["primary", "supporting", "duplicate_signal"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise TypeError("datetime field must be a datetime or ISO string")
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class EventEntities(BaseModel):
    companies: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)


class PipelineRun(BaseModel):
    id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: PipelineRunStatus
    candidate_count: int = Field(default=0, ge=0)
    ai_related_count: int = Field(default=0, ge=0)
    deduplicated_count: int = Field(default=0, ge=0)
    stored_count: int = Field(default=0, ge=0)
    failed_sources: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)

    @field_validator("started_at", "finished_at", mode="before")
    @classmethod
    def parse_datetimes(cls, value: Any) -> datetime | None:
        if value is None:
            return None
        return _parse_datetime(value)


class Event(BaseModel):
    id: str
    title: str
    summary: str
    category: EventCategory = "other"
    entities: EventEntities = Field(default_factory=EventEntities)
    related_source_item_ids: list[str] = Field(default_factory=list)
    first_seen_at: datetime
    latest_seen_at: datetime
    importance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    sentiment_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("first_seen_at", "latest_seen_at", "created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetimes(cls, value: Any) -> datetime:
        return _parse_datetime(value)

    @model_validator(mode="after")
    def validate_seen_window(self) -> "Event":
        if self.latest_seen_at < self.first_seen_at:
            raise ValueError("latest_seen_at must be greater than or equal to first_seen_at")
        return self


class EventSourceItem(BaseModel):
    event_id: str
    source_item_id: str
    relationship: EventSourceRelationship = "primary"


class Insight(BaseModel):
    id: str
    event_id: str
    key_points: list[str] = Field(default_factory=list)
    why_it_matters: str
    affected_companies: list[str] = Field(default_factory=list)
    affected_sectors: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_source_item_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_created_at(cls, value: Any) -> datetime:
        return _parse_datetime(value)


class RiskAssessment(BaseModel):
    id: str
    event_id: str
    public_opinion_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    policy_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    security_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    business_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    technical_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    overall_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_factors: list[str] = Field(default_factory=list)
    evidence_source_item_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_created_at(cls, value: Any) -> datetime:
        return _parse_datetime(value)


class DailyReport(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    report_date: date
    executive_summary: str
    top_event_ids: list[str] = Field(default_factory=list)
    risk_alert_ids: list[str] = Field(default_factory=list)
    markdown_path: str = ""
    json_path: str = ""
    report: dict[str, Any] = Field(default_factory=dict, alias="report_json")
    generated_at: datetime = Field(default_factory=utc_now)

    @field_validator("report_date", mode="before")
    @classmethod
    def parse_report_date(cls, value: Any) -> date:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            return date.fromisoformat(value)
        raise TypeError("report_date must be a date or ISO date string")

    @field_validator("generated_at", mode="before")
    @classmethod
    def parse_generated_at(cls, value: Any) -> datetime:
        return _parse_datetime(value)
