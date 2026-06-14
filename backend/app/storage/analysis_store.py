from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.schemas.analysis import (
    DailyReport,
    Event,
    EventEntities,
    EventSourceItem,
    EventSourceRelationship,
    Insight,
    PipelineRun,
    RiskAssessment,
)


class SQLiteAnalysisStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def upsert_pipeline_run(self, run: PipelineRun) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO pipeline_runs (
                    id, started_at, finished_at, status, candidate_count,
                    ai_related_count, deduplicated_count, stored_count,
                    failed_sources_json, summary_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    started_at=excluded.started_at,
                    finished_at=excluded.finished_at,
                    status=excluded.status,
                    candidate_count=excluded.candidate_count,
                    ai_related_count=excluded.ai_related_count,
                    deduplicated_count=excluded.deduplicated_count,
                    stored_count=excluded.stored_count,
                    failed_sources_json=excluded.failed_sources_json,
                    summary_json=excluded.summary_json
                """,
                _pipeline_run_row(run),
            )
            conn.commit()

    insert_pipeline_run = upsert_pipeline_run

    def fetch_pipeline_run(self, run_id: str) -> PipelineRun | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
        return _pipeline_run_from_row(row) if row else None

    def upsert_event(self, event: Event) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO events (
                    id, title, summary, category, entities_json, first_seen_at,
                    latest_seen_at, importance_score, sentiment_score, risk_score,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    summary=excluded.summary,
                    category=excluded.category,
                    entities_json=excluded.entities_json,
                    first_seen_at=excluded.first_seen_at,
                    latest_seen_at=excluded.latest_seen_at,
                    importance_score=excluded.importance_score,
                    sentiment_score=excluded.sentiment_score,
                    risk_score=excluded.risk_score,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at
                """,
                _event_row(event),
            )
            for source_item_id in event.related_source_item_ids:
                conn.execute(
                    """
                    INSERT INTO event_source_items (event_id, source_item_id, relationship)
                    VALUES (?, ?, ?)
                    ON CONFLICT(event_id, source_item_id) DO UPDATE SET
                        relationship=excluded.relationship
                    """,
                    (event.id, source_item_id, "primary"),
                )
            conn.commit()

    insert_event = upsert_event

    def fetch_event(self, event_id: str) -> Event | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
            links = conn.execute(
                "SELECT source_item_id FROM event_source_items WHERE event_id = ? ORDER BY source_item_id",
                (event_id,),
            ).fetchall()
        return _event_from_row(row, [link["source_item_id"] for link in links]) if row else None

    def list_events(
        self,
        limit: int | None = None,
        offset: int = 0,
        category: str | None = None,
        min_risk: float | None = None,
    ) -> list[Event]:
        where: list[str] = []
        params: list[Any] = []
        if category:
            where.append("category = ?")
            params.append(category)
        if min_risk is not None:
            where.append("risk_score >= ?")
            params.append(min_risk)
        where_sql = f" WHERE {' AND '.join(where)}" if where else ""
        limit_sql = ""
        if limit is not None:
            limit_sql = " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM events{where_sql} ORDER BY first_seen_at DESC, id{limit_sql}",
                params,
            ).fetchall()
            link_rows = conn.execute(
                "SELECT event_id, source_item_id FROM event_source_items ORDER BY source_item_id"
            ).fetchall()
        links_by_event: dict[str, list[str]] = {}
        for link in link_rows:
            links_by_event.setdefault(link["event_id"], []).append(link["source_item_id"])
        return [_event_from_row(row, links_by_event.get(row["id"], [])) for row in rows]

    fetch_events = list_events

    def link_event_source_item(
        self,
        event_id: str,
        source_item_id: str,
        relationship: EventSourceRelationship = "primary",
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO event_source_items (event_id, source_item_id, relationship)
                VALUES (?, ?, ?)
                ON CONFLICT(event_id, source_item_id) DO UPDATE SET
                    relationship=excluded.relationship
                """,
                (event_id, source_item_id, relationship),
            )
            conn.commit()

    def fetch_event_source_items(self, event_id: str) -> list[EventSourceItem]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT event_id, source_item_id, relationship
                FROM event_source_items
                WHERE event_id = ?
                ORDER BY source_item_id
                """,
                (event_id,),
            ).fetchall()
        return [EventSourceItem(**dict(row)) for row in rows]

    def upsert_insight(self, insight: Insight) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO insights (
                    id, event_id, key_points_json, why_it_matters,
                    affected_companies_json, affected_sectors_json,
                    opportunities_json, risks_json, confidence,
                    evidence_source_item_ids_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    event_id=excluded.event_id,
                    key_points_json=excluded.key_points_json,
                    why_it_matters=excluded.why_it_matters,
                    affected_companies_json=excluded.affected_companies_json,
                    affected_sectors_json=excluded.affected_sectors_json,
                    opportunities_json=excluded.opportunities_json,
                    risks_json=excluded.risks_json,
                    confidence=excluded.confidence,
                    evidence_source_item_ids_json=excluded.evidence_source_item_ids_json,
                    created_at=excluded.created_at
                """,
                _insight_row(insight),
            )
            conn.commit()

    insert_insight = upsert_insight

    def fetch_insight(self, insight_id: str) -> Insight | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM insights WHERE id = ?", (insight_id,)).fetchone()
        return _insight_from_row(row) if row else None

    def list_insights_for_event(self, event_id: str) -> list[Insight]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM insights WHERE event_id = ? ORDER BY created_at DESC, id",
                (event_id,),
            ).fetchall()
        return [_insight_from_row(row) for row in rows]

    def upsert_risk_assessment(self, risk: RiskAssessment) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO risk_assessments (
                    id, event_id, public_opinion_risk, policy_risk,
                    security_risk, business_risk, technical_risk, overall_risk,
                    risk_factors_json, evidence_source_item_ids_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    event_id=excluded.event_id,
                    public_opinion_risk=excluded.public_opinion_risk,
                    policy_risk=excluded.policy_risk,
                    security_risk=excluded.security_risk,
                    business_risk=excluded.business_risk,
                    technical_risk=excluded.technical_risk,
                    overall_risk=excluded.overall_risk,
                    risk_factors_json=excluded.risk_factors_json,
                    evidence_source_item_ids_json=excluded.evidence_source_item_ids_json,
                    created_at=excluded.created_at
                """,
                _risk_row(risk),
            )
            conn.commit()

    insert_risk_assessment = upsert_risk_assessment

    def fetch_risk_assessment(self, risk_id: str) -> RiskAssessment | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM risk_assessments WHERE id = ?", (risk_id,)).fetchone()
        return _risk_from_row(row) if row else None

    def list_risk_assessments_for_event(self, event_id: str) -> list[RiskAssessment]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM risk_assessments WHERE event_id = ? ORDER BY overall_risk DESC, id",
                (event_id,),
            ).fetchall()
        return [_risk_from_row(row) for row in rows]

    def upsert_daily_report(self, report: DailyReport) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO daily_reports (
                    id, report_date, executive_summary, top_event_ids_json,
                    risk_alert_ids_json, markdown_path, json_path,
                    report_json, generated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(report_date) DO UPDATE SET
                    id=excluded.id,
                    report_date=excluded.report_date,
                    executive_summary=excluded.executive_summary,
                    top_event_ids_json=excluded.top_event_ids_json,
                    risk_alert_ids_json=excluded.risk_alert_ids_json,
                    markdown_path=excluded.markdown_path,
                    json_path=excluded.json_path,
                    report_json=excluded.report_json,
                    generated_at=excluded.generated_at
                """,
                _daily_report_row(report),
            )
            conn.commit()

    insert_daily_report = upsert_daily_report

    def fetch_daily_report(self, report_id: str) -> DailyReport | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM daily_reports WHERE id = ?", (report_id,)).fetchone()
        return _daily_report_from_row(row) if row else None

    def fetch_daily_report_by_date(self, report_date: date | str) -> DailyReport | None:
        report_date_text = report_date if isinstance(report_date, str) else report_date.isoformat()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM daily_reports WHERE report_date = ? ORDER BY generated_at DESC, id LIMIT 1",
                (report_date_text,),
            ).fetchone()
        return _daily_report_from_row(row) if row else None

    def fetch_latest_daily_report(self) -> DailyReport | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM daily_reports ORDER BY report_date DESC, generated_at DESC, id LIMIT 1"
            ).fetchone()
        return _daily_report_from_row(row) if row else None

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    candidate_count INTEGER NOT NULL,
                    ai_related_count INTEGER NOT NULL,
                    deduplicated_count INTEGER NOT NULL,
                    stored_count INTEGER NOT NULL,
                    failed_sources_json TEXT NOT NULL,
                    summary_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    category TEXT NOT NULL,
                    entities_json TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    latest_seen_at TEXT NOT NULL,
                    importance_score REAL NOT NULL,
                    sentiment_score REAL NOT NULL,
                    risk_score REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS event_source_items (
                    event_id TEXT NOT NULL,
                    source_item_id TEXT NOT NULL,
                    relationship TEXT NOT NULL,
                    PRIMARY KEY (event_id, source_item_id)
                );

                CREATE TABLE IF NOT EXISTS insights (
                    id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    key_points_json TEXT NOT NULL,
                    why_it_matters TEXT NOT NULL,
                    affected_companies_json TEXT NOT NULL,
                    affected_sectors_json TEXT NOT NULL,
                    opportunities_json TEXT NOT NULL,
                    risks_json TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    evidence_source_item_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS risk_assessments (
                    id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    public_opinion_risk REAL NOT NULL,
                    policy_risk REAL NOT NULL,
                    security_risk REAL NOT NULL,
                    business_risk REAL NOT NULL,
                    technical_risk REAL NOT NULL,
                    overall_risk REAL NOT NULL,
                    risk_factors_json TEXT NOT NULL,
                    evidence_source_item_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS daily_reports (
                    id TEXT PRIMARY KEY,
                    report_date TEXT NOT NULL,
                    executive_summary TEXT NOT NULL,
                    top_event_ids_json TEXT NOT NULL,
                    risk_alert_ids_json TEXT NOT NULL,
                    markdown_path TEXT NOT NULL,
                    json_path TEXT NOT NULL,
                    report_json TEXT NOT NULL,
                    generated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at
                    ON pipeline_runs(started_at);
                CREATE INDEX IF NOT EXISTS idx_events_first_seen_at
                    ON events(first_seen_at);
                CREATE INDEX IF NOT EXISTS idx_event_source_items_source_item_id
                    ON event_source_items(source_item_id);
                CREATE INDEX IF NOT EXISTS idx_insights_event_id
                    ON insights(event_id);
                CREATE INDEX IF NOT EXISTS idx_risk_assessments_event_id
                    ON risk_assessments(event_id);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_reports_report_date
                    ON daily_reports(report_date);
                """
            )
            conn.commit()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


def _datetime_to_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _date_to_text(value: date) -> str:
    return value.isoformat()


def _pipeline_run_row(run: PipelineRun) -> tuple[Any, ...]:
    return (
        run.id,
        _datetime_to_text(run.started_at),
        _datetime_to_text(run.finished_at),
        run.status,
        run.candidate_count,
        run.ai_related_count,
        run.deduplicated_count,
        run.stored_count,
        _json_dumps(run.failed_sources),
        _json_dumps(run.summary),
    )


def _pipeline_run_from_row(row: sqlite3.Row) -> PipelineRun:
    return PipelineRun(
        id=row["id"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        status=row["status"],
        candidate_count=row["candidate_count"],
        ai_related_count=row["ai_related_count"],
        deduplicated_count=row["deduplicated_count"],
        stored_count=row["stored_count"],
        failed_sources=_json_loads(row["failed_sources_json"], []),
        summary=_json_loads(row["summary_json"], {}),
    )


def _event_row(event: Event) -> tuple[Any, ...]:
    return (
        event.id,
        event.title,
        event.summary,
        event.category,
        _json_dumps(event.entities.model_dump()),
        _datetime_to_text(event.first_seen_at),
        _datetime_to_text(event.latest_seen_at),
        event.importance_score,
        event.sentiment_score,
        event.risk_score,
        _datetime_to_text(event.created_at),
        _datetime_to_text(event.updated_at),
    )


def _event_from_row(row: sqlite3.Row, source_item_ids: list[str]) -> Event:
    return Event(
        id=row["id"],
        title=row["title"],
        summary=row["summary"],
        category=row["category"],
        entities=EventEntities(**_json_loads(row["entities_json"], {})),
        related_source_item_ids=source_item_ids,
        first_seen_at=row["first_seen_at"],
        latest_seen_at=row["latest_seen_at"],
        importance_score=row["importance_score"],
        sentiment_score=row["sentiment_score"],
        risk_score=row["risk_score"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _insight_row(insight: Insight) -> tuple[Any, ...]:
    return (
        insight.id,
        insight.event_id,
        _json_dumps(insight.key_points),
        insight.why_it_matters,
        _json_dumps(insight.affected_companies),
        _json_dumps(insight.affected_sectors),
        _json_dumps(insight.opportunities),
        _json_dumps(insight.risks),
        insight.confidence,
        _json_dumps(insight.evidence_source_item_ids),
        _datetime_to_text(insight.created_at),
    )


def _insight_from_row(row: sqlite3.Row) -> Insight:
    return Insight(
        id=row["id"],
        event_id=row["event_id"],
        key_points=_json_loads(row["key_points_json"], []),
        why_it_matters=row["why_it_matters"],
        affected_companies=_json_loads(row["affected_companies_json"], []),
        affected_sectors=_json_loads(row["affected_sectors_json"], []),
        opportunities=_json_loads(row["opportunities_json"], []),
        risks=_json_loads(row["risks_json"], []),
        confidence=row["confidence"],
        evidence_source_item_ids=_json_loads(row["evidence_source_item_ids_json"], []),
        created_at=row["created_at"],
    )


def _risk_row(risk: RiskAssessment) -> tuple[Any, ...]:
    return (
        risk.id,
        risk.event_id,
        risk.public_opinion_risk,
        risk.policy_risk,
        risk.security_risk,
        risk.business_risk,
        risk.technical_risk,
        risk.overall_risk,
        _json_dumps(risk.risk_factors),
        _json_dumps(risk.evidence_source_item_ids),
        _datetime_to_text(risk.created_at),
    )


def _risk_from_row(row: sqlite3.Row) -> RiskAssessment:
    return RiskAssessment(
        id=row["id"],
        event_id=row["event_id"],
        public_opinion_risk=row["public_opinion_risk"],
        policy_risk=row["policy_risk"],
        security_risk=row["security_risk"],
        business_risk=row["business_risk"],
        technical_risk=row["technical_risk"],
        overall_risk=row["overall_risk"],
        risk_factors=_json_loads(row["risk_factors_json"], []),
        evidence_source_item_ids=_json_loads(row["evidence_source_item_ids_json"], []),
        created_at=row["created_at"],
    )


def _daily_report_row(report: DailyReport) -> tuple[Any, ...]:
    return (
        report.id,
        _date_to_text(report.report_date),
        report.executive_summary,
        _json_dumps(report.top_event_ids),
        _json_dumps(report.risk_alert_ids),
        report.markdown_path,
        report.json_path,
        _json_dumps(report.report),
        _datetime_to_text(report.generated_at),
    )


def _daily_report_from_row(row: sqlite3.Row) -> DailyReport:
    return DailyReport(
        id=row["id"],
        report_date=row["report_date"],
        executive_summary=row["executive_summary"],
        top_event_ids=_json_loads(row["top_event_ids_json"], []),
        risk_alert_ids=_json_loads(row["risk_alert_ids_json"], []),
        markdown_path=row["markdown_path"],
        json_path=row["json_path"],
        report=_json_loads(row["report_json"], {}),
        generated_at=row["generated_at"],
    )
