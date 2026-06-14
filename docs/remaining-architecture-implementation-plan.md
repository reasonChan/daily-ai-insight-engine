# Daily AI Insight Engine - Remaining Architecture Implementation Plan

## 1. Current Baseline

The current implementation already covers the first data-source milestone:

- Configuration-driven source collection from RSS/Atom, arXiv, Hacker News, Reddit, and GitHub Releases.
- Unified source item schema and collector failure envelopes.
- AI relevance filtering with English and Chinese keywords.
- URL, normalized-title, and content-hash deduplication.
- SQLite metadata storage for `source_items`.
- RAG-ready chunk generation.
- CLI collection flow and offline fixture tests.

The next phase should turn collected source items into an end-to-end insight product:

```text
Source Items
  -> Cleaned Articles
  -> Events
  -> Insights
  -> Risk Assessments
  -> Daily Reports
  -> API
  -> Dashboard
  -> Scheduled Runs
  -> Historical Trends
```

This document defines the remaining feature work, technical direction, suggested order, and acceptance criteria.

## 2. Implementation Principles

- Keep the MVP pipeline-style. Avoid a fully autonomous multi-agent system until the data contracts stabilize.
- Every generated object must be traceable back to original `source_items`.
- Prefer structured outputs validated by Pydantic.
- Use deterministic rules as fallback when LLM calls fail.
- Keep local-first storage with SQLite for MVP.
- Add abstractions only where they protect clear boundaries: extraction, agents, storage, retrieval, reports, API.
- Tests should include offline fixtures and should not require live network calls.

## 3. Priority Roadmap

| Priority | Feature | Why It Comes Here |
| --- | --- | --- |
| P0 | Content cleaning and article extraction | Improves source quality before analysis |
| P0 | Structured storage expansion | Defines durable contracts for events, insights, reports, and runs |
| P0 | Event extraction and clustering | Converts raw items into the core analysis unit |
| P1 | Insight analysis and risk assessment agents | Produces the actual intelligence layer |
| P1 | Daily report generation | Creates the first user-facing artifact |
| P1 | FastAPI local API | Exposes data for dashboard and automation |
| P2 | Dashboard | Provides local visual consumption |
| P2 | Real vector store and retriever | Improves analysis context and search |
| P2 | Scheduler | Enables daily recurring operation |
| P3 | Historical trend analysis | Adds longitudinal value after enough data exists |

Recommended build order:

1. Content cleaning and article extraction.
2. Structured storage expansion.
3. Event extraction and event clustering.
4. Insight analysis and risk assessment.
5. Daily report JSON and Markdown generation.
6. FastAPI endpoints.
7. Dashboard.
8. Vector store and retriever.
9. Scheduled daily runs.
10. Historical trend analysis.

## 4. Feature Plans

## 4.1 Content Cleaning and Article Extraction

### Goal

Normalize article text quality so downstream event extraction and reporting are based on richer content than RSS summaries alone.

### Proposed Modules

```text
backend/app/extractors/
  article_extractor.py
  html_cleaner.py

backend/app/services/
  content_enrichment.py
```

### Technical Approach

- Add a `WebArticleExtractor` service.
- For media/blog sources, fetch `source_url` and extract article body.
- Use a proven library if dependencies are acceptable:
  - Preferred: `trafilatura`
  - Alternative: `readability-lxml`
  - Fallback: standard-library HTML text extraction
- Skip article extraction for API-native sources:
  - arXiv
  - GitHub Releases
  - Reddit
  - Hacker News items without original article URL
- Add extraction metadata into `raw_payload` or dedicated storage columns:
  - `extraction_status`
  - `content_length`
  - `content_quality_score`
  - `extracted_at`

### Acceptance Criteria

- Media/blog items with short summaries can be enriched with longer cleaned content.
- Extraction failure is recorded per item and does not stop the pipeline.
- Tests cover:
  - valid HTML fixture
  - empty HTML/body
  - network/extraction failure
  - source types that should skip extraction

## 4.2 Structured Storage Expansion

### Goal

Create durable database tables for events, insights, risk assessments, reports, and pipeline runs.

### Proposed Tables

```text
source_items              existing
pipeline_runs             new
events                    new
event_source_items         new
insights                  new
risk_assessments          new
daily_reports             new
```

### Suggested Schemas

`pipeline_runs`:

```json
{
  "id": "string",
  "started_at": "datetime",
  "finished_at": "datetime",
  "status": "success | partial_success | failed",
  "candidate_count": 0,
  "ai_related_count": 0,
  "deduplicated_count": 0,
  "stored_count": 0,
  "failed_sources_json": "json",
  "summary_json": "json"
}
```

`events`:

```json
{
  "id": "string",
  "title": "string",
  "summary": "string",
  "category": "model | product | research | funding | policy | safety | infrastructure | company | other",
  "entities_json": "json",
  "first_seen_at": "datetime",
  "latest_seen_at": "datetime",
  "importance_score": 0.0,
  "sentiment_score": 0.0,
  "risk_score": 0.0,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

`event_source_items`:

```json
{
  "event_id": "string",
  "source_item_id": "string",
  "relationship": "primary | supporting | duplicate_signal"
}
```

`insights`:

```json
{
  "id": "string",
  "event_id": "string",
  "key_points_json": "json",
  "why_it_matters": "string",
  "affected_companies_json": "json",
  "affected_sectors_json": "json",
  "opportunities_json": "json",
  "risks_json": "json",
  "confidence": 0.0,
  "created_at": "datetime"
}
```

`risk_assessments`:

```json
{
  "id": "string",
  "event_id": "string",
  "public_opinion_risk": 0.0,
  "policy_risk": 0.0,
  "security_risk": 0.0,
  "business_risk": 0.0,
  "technical_risk": 0.0,
  "overall_risk": 0.0,
  "risk_factors_json": "json",
  "evidence_source_item_ids_json": "json",
  "created_at": "datetime"
}
```

`daily_reports`:

```json
{
  "id": "string",
  "report_date": "date",
  "executive_summary": "string",
  "top_event_ids_json": "json",
  "risk_alert_ids_json": "json",
  "markdown_path": "string",
  "json_path": "string",
  "report_json": "json",
  "generated_at": "datetime"
}
```

### Technical Approach

- Continue using SQLite for MVP.
- Either extend the current `SQLiteSourceStore` or create a separate `SQLiteAnalysisStore`.
- Keep all JSON fields stored as text with consistent `json.dumps(..., ensure_ascii=False)`.
- Add repository methods rather than writing SQL directly in agents.

### Acceptance Criteria

- Tables are created automatically.
- Each report can be traced back to events and source items.
- Re-running the same date does not create uncontrolled duplicates.
- Offline tests verify insert, fetch, and upsert behavior.

## 4.3 Event Extraction

### Goal

Turn source items into structured events.

### Proposed Modules

```text
backend/app/agents/
  event_extraction_agent.py

backend/app/schemas/
  events.py
```

### Event Schema

```json
{
  "id": "string",
  "title": "string",
  "summary": "string",
  "category": "string",
  "entities": {
    "companies": ["string"],
    "products": ["string"],
    "people": ["string"],
    "models": ["string"],
    "topics": ["string"]
  },
  "related_source_item_ids": ["string"],
  "first_seen_at": "datetime",
  "latest_seen_at": "datetime",
  "importance_score": 0.0,
  "sentiment_score": 0.0,
  "risk_score": 0.0
}
```

### Technical Approach

- Use a pipeline-style `EventExtractionAgent`.
- Input: deduplicated AI-related source items from the current run.
- Output: list of validated `Event` objects.
- MVP extraction strategy:
  - Rule layer extracts obvious entities and categories.
  - LLM layer compresses source items into event candidates.
  - Fallback creates one weak event per high-quality source item.
- Use structured LLM output and validate with Pydantic.

### Acceptance Criteria

- Every event has at least one `related_source_item_id`.
- LLM output validation failure triggers fallback, not pipeline failure.
- Important source items produce events.
- Events include category, entities, and importance score.

## 4.4 Event Clustering

### Goal

Merge source items or weak events that describe the same real-world event.

### Proposed Modules

```text
backend/app/services/
  event_clustering.py
```

### Technical Approach

MVP clustering can be deterministic:

- Normalize titles.
- Extract entity sets.
- Compare source item time windows.
- Score similarity:
  - title token overlap
  - entity overlap
  - category match
  - same-day or near-day publication
- Greedy clustering is acceptable for 10-50 items per run.

Future clustering can use embeddings:

- Generate title/summary embeddings.
- Cluster by cosine similarity.
- Add event-level deduplication across historical events.

### Acceptance Criteria

- Duplicate coverage from Google News, media, and HN can merge into one event.
- Unrelated events from the same company are not merged only because the company matches.
- Each cluster has a canonical title and representative source item.

## 4.5 Insight Analysis Agent

### Goal

Explain why each event matters and what it may affect.

### Proposed Modules

```text
backend/app/agents/
  insight_analysis_agent.py

backend/app/schemas/
  insights.py
```

### Insight Schema

```json
{
  "id": "string",
  "event_id": "string",
  "key_points": ["string"],
  "why_it_matters": "string",
  "affected_companies": ["string"],
  "affected_sectors": ["string"],
  "opportunities": ["string"],
  "risks": ["string"],
  "confidence": 0.0,
  "evidence_source_item_ids": ["string"]
}
```

### Technical Approach

- Input: event + related source item text + optional RAG context.
- Use structured output.
- Enforce evidence discipline:
  - Do not introduce facts not supported by source items.
  - Each insight must cite source item ids.
- Add deterministic fallback:
  - key points from event summary and source titles
  - low confidence

### Acceptance Criteria

- High-importance events receive insights.
- Every insight references source item ids.
- Confidence is present and bounded from 0 to 1.
- Tests cover LLM success and fallback paths using mocked model responses.

## 4.6 Risk Assessment Agent

### Goal

Score and explain risks associated with each event.

### Proposed Modules

```text
backend/app/agents/
  risk_assessment_agent.py

backend/app/schemas/
  risks.py
```

### Risk Schema

```json
{
  "id": "string",
  "event_id": "string",
  "public_opinion_risk": 0.0,
  "policy_risk": 0.0,
  "security_risk": 0.0,
  "business_risk": 0.0,
  "technical_risk": 0.0,
  "overall_risk": 0.0,
  "risk_factors": ["string"],
  "evidence_source_item_ids": ["string"]
}
```

### Technical Approach

- Use rules for baseline risk:
  - policy terms: regulation, ban, lawsuit, compliance, copyright
  - security terms: breach, vulnerability, exploit, jailbreak, prompt injection
  - business terms: layoffs, funding, acquisition, pricing, competition
  - public-opinion terms: backlash, boycott, controversy, complaint
- Use LLM for explanation and normalization.
- Compute `overall_risk` from weighted dimensions.

### Acceptance Criteria

- Risk alerts can be generated from high `overall_risk`.
- Risk factors include evidence source item ids.
- Product announcements without risk terms do not become high-risk by default.
- Rule-only fallback works if model call fails.

## 4.7 RAG Retrieval Layer

### Goal

Move from RAG-ready chunk files to searchable retrieval.

### Proposed Modules

```text
backend/app/rag/
  embeddings.py
  vector_store.py
  retriever.py
```

### Technical Approach

- Add `EmbeddingService` abstraction.
- Support OpenAI-compatible embedding API.
- Use one local vector store:
  - Preferred MVP: Chroma
  - Alternative: LanceDB
- Add chunk metadata:
  - `source_item_id`
  - `event_id`
  - `source_type`
  - `medium_type`
  - `source_name`
  - `published_at`
  - `language`
  - `title`
  - `url`
- Add retriever methods:
  - `search(query, filters)`
  - `get_context_for_event(event_id)`
  - `get_recent_context(topic, date_range)`

### Acceptance Criteria

- Given a query, retriever returns relevant chunks with source metadata.
- Given an event id, retriever returns related source context.
- Retrieval can filter by source type, language, and date range.
- Tests can use fake embeddings.

## 4.8 Daily Report Generation

### Goal

Generate human-readable and machine-readable daily reports.

### Proposed Modules

```text
backend/app/reports/
  daily_report_generator.py
  markdown_renderer.py
```

### Report Structure

```text
# Daily AI Insight Report - YYYY-MM-DD

## Executive Summary

## Top Events

## Key Insights

## Risk Alerts

## Notable Source Items

## Source Breakdown

## Failed Sources
```

### JSON Report Shape

```json
{
  "report_date": "date",
  "executive_summary": "string",
  "top_events": [],
  "insights": [],
  "risk_alerts": [],
  "source_breakdown": {},
  "failed_sources": [],
  "generated_at": "datetime"
}
```

### Technical Approach

- Use stored events, insights, risk assessments, and pipeline summary.
- Rank top events by importance and risk.
- Generate:
  - `reports/daily/YYYY-MM-DD.json`
  - `reports/daily/YYYY-MM-DD.md`
- Keep the report generator deterministic where possible.
- Optionally use LLM only for executive summary text.

### Acceptance Criteria

- A full run produces both Markdown and JSON reports.
- Every report event includes source links or source ids.
- Risk alerts include risk score and evidence.
- Report generation can run from offline fixture data.

## 4.9 FastAPI Local API

### Goal

Expose the local data pipeline to the dashboard and manual controls.

### Proposed Modules

```text
backend/app/api/
  main.py
  routes/
    health.py
    runs.py
    source_items.py
    events.py
    insights.py
    reports.py
    search.py
```

### Core Endpoints

```text
GET  /health
POST /runs/collect
GET  /runs
GET  /source-items
GET  /events
GET  /insights
GET  /reports/latest
GET  /reports/{date}
GET  /search?q=...
```

### Technical Approach

- FastAPI app should call services, not contain business logic.
- No auth for MVP.
- Add pagination for list endpoints.
- Add filters:
  - date range
  - source type
  - language
  - category
  - risk threshold

### Acceptance Criteria

- API can trigger collection.
- API can return latest report.
- API can list source items and events.
- All endpoints return stable JSON schemas.

## 4.10 Dashboard

### Goal

Create a local analysis workspace for reports, events, sources, and risk alerts.

### Proposed Frontend Stack

- React
- Vite
- TypeScript
- Tailwind CSS
- Recharts or ECharts

### Suggested Pages

```text
Dashboard
Source Items
Events
Report
Trends
Settings
```

### UX Direction

- Build a work-focused dashboard, not a marketing landing page.
- First screen should show current operational state:
  - latest run status
  - source count
  - event count
  - risk alert count
  - failed source count
- Main interactions:
  - inspect latest report
  - drill down from event to source items
  - filter source items
  - view risk alerts
  - trigger collection run

### Acceptance Criteria

- Dashboard can read latest report from API.
- Event detail view shows related source items.
- Source item list supports filtering.
- Failed sources are visible.
- Layout is usable on desktop without overlapping text.

## 4.11 Scheduled Daily Runs

### Goal

Run the collection and report pipeline automatically.

### Proposed Modules

```text
backend/app/scheduler/
  scheduler.py
  jobs.py
```

### Technical Approach

- Use APScheduler for local MVP.
- Job should run the full daily pipeline:
  - collect
  - enrich
  - deduplicate
  - extract events
  - generate insights
  - assess risks
  - generate report
- Add guard against overlapping runs.
- Store each run in `pipeline_runs`.

### Acceptance Criteria

- Schedule can be configured locally.
- Manual trigger and scheduled trigger share the same pipeline.
- Failed jobs write run records and error summaries.
- No duplicate concurrent run for the same job.

## 4.12 Historical Trend Analysis

### Goal

Analyze changes across days after reports accumulate.

### Proposed Modules

```text
backend/app/services/
  trend_analysis.py
```

### Metrics

- Daily source item count.
- Daily event count.
- Source type breakdown.
- Category breakdown.
- Top entities.
- Risk score trend.
- Repeated topics across days.
- Today vs 7-day average.

### Technical Approach

- Use SQL aggregation first.
- Store trend snapshots only if API/dashboard performance requires it.
- Dashboard can visualize:
  - line charts
  - stacked bars
  - top entity rankings
  - risk trend cards

### Acceptance Criteria

- Can compute 7-day and 30-day summaries.
- Can identify recurring companies/models/topics.
- Can compare current day with rolling average.

## 5. Proposed End-to-End Pipeline

After the next phase, the target daily run should look like this:

```text
1. Load source config.
2. Collect source items.
3. Filter for AI relevance.
4. Extract and clean article content.
5. Deduplicate source items.
6. Store source items and chunks.
7. Extract weak events from source items.
8. Cluster events.
9. Store events and event-source links.
10. Generate insights for top events.
11. Assess risks for events.
12. Generate JSON and Markdown daily report.
13. Store report metadata.
14. Expose everything through API/dashboard.
```

## 6. Suggested Task Breakdown for the Next Implementation Window

### Task A: Storage Foundation

Scope:

- Add schemas for Event, Insight, RiskAssessment, DailyReport, PipelineRun.
- Add SQLite tables and repository methods.
- Add offline tests.

Acceptance:

- Database initializes all tables.
- Insert/fetch/upsert tests pass.
- Existing source item tests still pass.

### Task B: Event Pipeline

Scope:

- Add event extraction fallback rules.
- Add event clustering service.
- Wire source items to event output.

Acceptance:

- Fixture source items produce events.
- Duplicate event candidates merge.
- Every event references source item ids.

### Task C: Report Pipeline

Scope:

- Add insight/risk deterministic MVP.
- Add daily report generator.
- Write JSON and Markdown.

Acceptance:

- Fixture run produces a report.
- Report includes top events, insights, risk alerts, source breakdown.
- Report objects trace back to source item ids.

### Task D: API

Scope:

- Add FastAPI app and core read endpoints.
- Add manual run trigger endpoint.

Acceptance:

- App starts locally.
- `/health`, `/source-items`, `/events`, `/reports/latest` work.

### Task E: Dashboard

Scope:

- Create Vite/React dashboard.
- Implement latest report, event list, source list, and run status.

Acceptance:

- Dashboard displays API data.
- Event detail links to source items.
- Failed sources are visible.

## 7. Definition of Done for the Next Phase

The next phase is complete when:

- A single command can run from source collection through daily report generation.
- The generated report contains events, insights, risks, source links, and source breakdown.
- Events, insights, risks, reports, and runs are persisted in SQLite.
- API can serve latest report and related source/event data.
- Offline tests cover the end-to-end pipeline using fixtures.

