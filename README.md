# Daily AI Insight Engine

Daily AI Insight Engine is a local AI public-opinion and industry-insight system.

The first milestone focuses on the data source layer:

- Collect recent AI-related information from media, official channels, social platforms, and aggregators.
- Normalize heterogeneous source payloads into structured schemas.
- Store cleaned metadata and text chunks in a RAG-ready database.
- Prepare the downstream pipeline for event extraction, risk scoring, trend analysis, and daily report generation.

## Project Shell

```text
daily-ai-insight-engine/
  backend/
  frontend/
  configs/
  data/
  docs/
  reports/
```

## Documents

- `docs/overall-architecture.md`: overall system architecture.
- `docs/data-source-implementation.md`: concrete implementation plan for the data source layer.
