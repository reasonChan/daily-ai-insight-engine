# Daily AI Insight Engine - Overall Architecture

## 1. System Goal

Daily AI Insight Engine is designed to collect daily AI-related news and public-discussion signals, extract structured insights, and generate readable analysis reports with visualized trends and risk alerts.

The system is intended for:

- AI industry trend analysis
- Public-opinion monitoring and risk warning
- Rapid information understanding and decision support

## 2. Architecture Overview

```text
Data Source Layer
  -> Collection and Cleaning Layer
  -> Event Clustering Layer
  -> AI Analysis Layer
  -> Structured Storage Layer
  -> RAG Retrieval Layer
  -> Report Generation Layer
  -> Dashboard and Visualization Layer
```

## 3. Core Pipeline

```text
Source Tools
  -> Raw Source Items
  -> Normalizer
  -> AI Relevance Filter
  -> Content Fetcher
  -> Cleaner
  -> Deduplicator
  -> RAG Ingestion
  -> Event Extraction Agent
  -> Insight Analysis Agent
  -> Risk Assessment Agent
  -> Daily Report Generator
```

## 4. Recommended Technology Stack

### Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- SQLite for MVP, PostgreSQL later
- APScheduler for local scheduled jobs

### AI and Agent Layer

- OpenAI-compatible model interface
- Structured output with Pydantic schemas
- Lightweight pipeline-style agents for MVP
- Optional LangGraph after the pipeline stabilizes

### RAG Storage

- SQLite for structured metadata
- Chroma or LanceDB for vector chunks
- Source-level metadata attached to every chunk

### Frontend

- React
- Vite
- TypeScript
- Tailwind CSS
- Recharts or ECharts

## 5. Main Modules

```text
backend/
  app/
    api/
    agents/
    collectors/
    core/
    models/
    pipelines/
    rag/
    reports/
    schemas/
    services/

frontend/
  src/
    api/
    charts/
    components/
    pages/

configs/
  sources.yaml

data/
  raw/
  processed/
  rag/

reports/
  daily/

docs/
```

## 6. Agent Design

The MVP should use a pipeline-style agent architecture instead of a fully autonomous multi-agent system.

### Planned Agents

- `NewsIngestionAgent`: coordinates source collection.
- `EventExtractionAgent`: extracts events from normalized items.
- `InsightAnalysisAgent`: explains why each event matters.
- `RiskAssessmentAgent`: scores public-opinion, policy, security, and business risks.
- `ReportGenerationAgent`: generates daily Markdown, JSON, and dashboard-ready outputs.

## 7. Core Data Objects

### Article

- id
- title
- url
- source
- published_at
- raw_content
- cleaned_content
- language
- collected_at

### Event

- id
- title
- summary
- category
- entities
- related_article_ids
- first_seen_at
- latest_seen_at
- importance_score
- sentiment_score
- risk_score

### Insight

- id
- event_id
- key_points
- why_it_matters
- affected_companies
- affected_sectors
- opportunities
- risks
- confidence

### DailyReport

- id
- report_date
- executive_summary
- top_events
- trend_analysis
- risk_alerts
- generated_at

## 8. MVP Scope

The first version should focus on a reliable end-to-end loop:

1. Configure data sources.
2. Collect 10 to 20 recent AI-related items daily.
3. Normalize source payloads.
4. Store metadata and text in a RAG-ready database.
5. Generate structured daily data.
6. Produce Markdown and JSON reports.
7. Expose local API endpoints.
8. Display reports and source items in a local dashboard.

Out of MVP scope:

- Multi-user permissions
- Large distributed task queue
- Real-time monitoring
- Complex autonomous agents
- Production-grade crawler infrastructure
- Full PDF publishing pipeline

## 9. Development Order

1. Data source layer
2. Normalized schemas
3. Local database and RAG ingestion
4. Collection pipeline CLI
5. FastAPI endpoints
6. Report generator
7. Dashboard
8. Scheduled daily runs
9. Historical trend analysis
