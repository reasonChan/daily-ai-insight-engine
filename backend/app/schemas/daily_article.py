from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.schemas.analysis import _parse_datetime, utc_now


ArticleGenerator = Literal["rule_based", "llm", "hybrid"]


class ArticleSection(BaseModel):
    heading: str
    content: str
    related_event_ids: list[str] = Field(default_factory=list)
    evidence_source_item_ids: list[str] = Field(default_factory=list)


class DailyArticle(BaseModel):
    report_date: date
    title: str
    subtitle: str | None = None
    lead: str
    body_sections: list[ArticleSection] = Field(default_factory=list)
    trend_outlook: str
    risk_opportunity: str
    evidence_source_item_ids: list[str] = Field(default_factory=list)
    generated_by: ArticleGenerator = "rule_based"
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
