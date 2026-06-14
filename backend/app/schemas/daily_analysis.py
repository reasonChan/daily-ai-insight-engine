from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.schemas.analysis import _parse_datetime, utc_now


TrendDirection = Literal["technology", "application", "policy", "capital"]
RiskOpportunityType = Literal["risk", "opportunity"]


class HotTopic(BaseModel):
    rank: int = Field(ge=1)
    title: str
    category: str
    importance_score: float = Field(ge=0.0, le=1.0)
    hot_score: float = Field(ge=0.0, le=1.0)
    reason: str
    supporting_event_ids: list[str] = Field(default_factory=list)
    evidence_source_item_ids: list[str] = Field(default_factory=list)


class EventDeepDive(BaseModel):
    event_id: str
    title: str
    background: str
    impact_analysis: str
    affected_entities: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    evidence_source_item_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class TrendJudgment(BaseModel):
    direction: TrendDirection
    judgment: str
    logic: str
    supporting_event_ids: list[str] = Field(default_factory=list)
    evidence_source_item_ids: list[str] = Field(default_factory=list)
    signal_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class RiskOpportunityNote(BaseModel):
    type: RiskOpportunityType
    title: str
    rationale: str
    related_event_ids: list[str] = Field(default_factory=list)
    evidence_source_item_ids: list[str] = Field(default_factory=list)
    priority: float = Field(default=0.0, ge=0.0, le=1.0)


class DailyAnalysis(BaseModel):
    report_date: date
    hot_topics: list[HotTopic] = Field(default_factory=list)
    deep_dives: list[EventDeepDive] = Field(default_factory=list)
    trend_judgments: list[TrendJudgment] = Field(default_factory=list)
    risk_opportunity_notes: list[RiskOpportunityNote] = Field(default_factory=list)
    evidence_source_item_ids: list[str] = Field(default_factory=list)
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
