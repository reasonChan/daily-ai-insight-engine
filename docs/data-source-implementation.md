# Daily AI Insight Engine - Data Source Implementation

## 1. Objective

The data source layer should collect at least 10 to 20 recent AI-related news or information items per run.

The collected data should include:

- Title
- Body content or summary
- Source name
- Source URL
- Published time
- Collected time
- Language
- Medium-specific metadata

Chinese and English sources should both be supported where possible.

## 2. Source Categories

| Type | Example Sources | Medium | Main Value |
| --- | --- | --- | --- |
| Tech media | TechCrunch, The Verge, 机器之心, 量子位 | News articles | Industry updates, company events, product launches |
| Official channels | Company blogs, GitHub Releases, arXiv | Announcements, papers, releases | First-party technical signals |
| Social media | Twitter/X, Reddit, 知乎热榜 | Posts, discussions, comments | Public-opinion signals and risk hints |
| Aggregators | Google News, Hacker News, Product Hunt | Ranking items, aggregated news | Topic discovery and trend detection |

## 3. Tool Mapping

Each source type should be represented by a lightweight source tool. A tool can be implemented as a local collector module first, and upgraded into a skill or MCP tool later.

| Tool | Target Sources | Recommended Form | MVP Priority |
| --- | --- | --- | --- |
| `rss_collector_tool` | Tech media, official blogs, Google News RSS | Local collector, later skill | High |
| `web_article_extractor_tool` | Article body pages | Local extractor | High |
| `arxiv_collector_tool` | arXiv | Local API collector, later MCP | High |
| `github_release_collector_tool` | GitHub Releases | Local API collector, later MCP | High |
| `hacker_news_collector_tool` | Hacker News Algolia API | Local API collector | High |
| `reddit_collector_tool` | Reddit subreddits | Local JSON/RSS collector | Medium |
| `zhihu_hot_collector_tool` | Zhihu hot list | Local HTML collector | Medium |
| `product_hunt_collector_tool` | Product Hunt | API or HTML collector | Low |
| `x_collector_tool` | Twitter/X | API or third-party RSS bridge | Low |
| `source_normalizer_tool` | All sources | Local schema mapper | High |
| `rag_ingestion_tool` | Normalized source items | Local ingestion service | High |

## 4. General Collection Flow

```text
Source Tool
  -> Raw Payload
  -> RawSourceItem
  -> AI Relevance Filter
  -> Content Fetcher
  -> Cleaner
  -> Deduplicator
  -> Medium-specific Schema
  -> SQLite Metadata Store
  -> Vector Chunks
  -> RAG Database
```

## 5. Unified Base Schema

All source tools should first normalize output into `RawSourceItem`.

```json
{
  "id": "string",
  "source_type": "tech_media | official | social | aggregator",
  "medium_type": "article | blog | release | paper | social_post | discussion | ranking_item",
  "source_name": "string",
  "source_url": "string",
  "title": "string",
  "summary": "string",
  "content": "string",
  "language": "zh | en | other",
  "published_at": "datetime",
  "collected_at": "datetime",
  "authors": ["string"],
  "tags": ["string"],
  "raw_payload": {}
}
```

Required fields:

- `title`
- `source_name`
- `source_url`
- `published_at`
- `collected_at`
- `summary` or `content`

## 6. Tech Media Sources

### Example Sources

- TechCrunch AI
- The Verge AI
- MIT Technology Review AI
- 机器之心
- 量子位

### Collection Strategy

Priority order:

1. RSS feeds
2. Topic or tag pages
3. Google News RSS fallback
4. Article body extraction

### Tool

`tech_media_collector_tool`

This can be implemented through `rss_collector_tool` plus `web_article_extractor_tool`.

### Schema

```json
{
  "item_type": "media_article",
  "title": "string",
  "subtitle": "string",
  "summary": "string",
  "content": "string",
  "source_name": "TechCrunch",
  "source_url": "https://...",
  "author": "string",
  "published_at": "datetime",
  "language": "en",
  "category": "industry_news | product | funding | policy | research | company",
  "mentioned_entities": {
    "companies": ["string"],
    "products": ["string"],
    "people": ["string"]
  }
}
```

## 7. Official Channel Sources

### Example Sources

- OpenAI Blog
- Google DeepMind Blog
- Anthropic News
- Microsoft AI Blog
- GitHub Releases
- arXiv

### Collection Strategy

Company blogs:

- RSS
- Sitemap
- HTML list pages

GitHub Releases:

- GitHub REST API
- Repository allowlist for AI frameworks and tools

arXiv:

- arXiv API
- Categories: `cs.AI`, `cs.CL`, `cs.LG`, `cs.CV`
- Keywords: `large language model`, `generative AI`, `agent`, `multimodal`, `alignment`

### Tools

- `official_blog_collector_tool`
- `github_release_collector_tool`
- `arxiv_collector_tool`

### Official Blog Schema

```json
{
  "item_type": "official_blog",
  "organization": "OpenAI",
  "title": "string",
  "summary": "string",
  "content": "string",
  "source_url": "https://...",
  "published_at": "datetime",
  "language": "en",
  "announcement_type": "model | product | safety | policy | research | partnership",
  "official_level": "primary_source"
}
```

### GitHub Release Schema

```json
{
  "item_type": "github_release",
  "repo": "owner/name",
  "owner": "string",
  "project_name": "string",
  "release_name": "string",
  "tag_name": "string",
  "body": "string",
  "source_url": "https://github.com/...",
  "published_at": "datetime",
  "language": "en",
  "assets": [
    {
      "name": "string",
      "download_url": "string"
    }
  ],
  "signals": {
    "is_major_release": true,
    "contains_breaking_change": false,
    "contains_security_fix": false
  }
}
```

### arXiv Paper Schema

```json
{
  "item_type": "paper",
  "title": "string",
  "abstract": "string",
  "authors": ["string"],
  "source_name": "arXiv",
  "source_url": "https://arxiv.org/abs/...",
  "published_at": "datetime",
  "updated_at": "datetime",
  "categories": ["cs.AI", "cs.CL"],
  "language": "en",
  "paper_id": "string",
  "research_topics": ["LLM", "agents", "multimodal"]
}
```

## 8. Social Media Sources

### Example Sources

- Twitter/X
- Reddit
- 知乎热榜

### Collection Strategy

MVP should avoid fragile or high-friction scraping paths.

Reddit:

- JSON endpoint
- RSS endpoint
- Target communities: `r/artificial`, `r/MachineLearning`, `r/LocalLLaMA`, `r/OpenAI`

Zhihu:

- Hot list HTML or lightweight third-party hot-list source
- Keyword filter: `AI`, `人工智能`, `大模型`, `OpenAI`, `模型`, `机器人`, `芯片`

Twitter/X:

- Keep interface reserved
- Prefer official API or approved RSS bridge later

### Tools

- `reddit_collector_tool`
- `zhihu_hot_collector_tool`
- `x_collector_tool`

### Schema

```json
{
  "item_type": "social_post",
  "platform": "reddit | x | zhihu",
  "title": "string",
  "content": "string",
  "summary": "string",
  "source_url": "https://...",
  "author": "string",
  "published_at": "datetime",
  "language": "zh | en",
  "engagement": {
    "upvotes": 0,
    "comments": 0,
    "shares": 0,
    "likes": 0,
    "score": 0
  },
  "discussion_context": {
    "community": "string",
    "topic": "string",
    "sentiment_hint": "positive | neutral | negative | mixed"
  },
  "credibility_level": "discussion_signal",
  "requires_verification": true
}
```

## 9. Aggregator Sources

### Example Sources

- Google News
- Hacker News
- Product Hunt

### Collection Strategy

Google News:

- RSS search queries
- English and Chinese queries
- Example keywords: `AI`, `artificial intelligence`, `LLM`, `OpenAI`, `人工智能`, `大模型`

Hacker News:

- Algolia HN Search API
- Query keywords: `AI`, `LLM`, `OpenAI`, `Claude`, `agents`, `GPU`

Product Hunt:

- API or ranking page
- Focus on AI-related launches

### Tools

- `google_news_collector_tool`
- `hacker_news_collector_tool`
- `product_hunt_collector_tool`

### Schema

```json
{
  "item_type": "aggregated_item",
  "platform": "google_news | hacker_news | product_hunt",
  "title": "string",
  "summary": "string",
  "source_url": "https://...",
  "original_source_name": "string",
  "original_source_url": "https://...",
  "published_at": "datetime",
  "language": "zh | en",
  "ranking": {
    "rank": 0,
    "score": 0,
    "comments": 0,
    "votes": 0
  },
  "aggregation_context": {
    "query": "AI",
    "topic": "string"
  }
}
```

## 10. AI Relevance Filter

### Rule-based Filter for MVP

Chinese and English keywords:

```text
AI
artificial intelligence
generative AI
LLM
large language model
agent
OpenAI
Anthropic
Claude
Gemini
DeepMind
大模型
人工智能
生成式AI
智能体
多模态
算力
芯片
机器人
```

### Filter Output

```json
{
  "is_ai_related": true,
  "relevance_score": 0.86,
  "matched_keywords": ["LLM", "OpenAI"],
  "topics": ["LLM", "product_release"]
}
```

LLM-based classification can be added after the first stable collector version.

## 11. Deduplication

MVP deduplication rules:

1. Exact URL match
2. Normalized title match
3. Content hash match

Second-stage deduplication:

1. Title embedding similarity
2. Summary similarity
3. Event-level clustering

Deduplication metadata:

```json
{
  "canonical_item_id": "string",
  "duplicate_source_urls": ["string"],
  "source_count": 3
}
```

## 12. RAG Storage Design

### Structured Metadata Store

Use SQLite for MVP.

Table: `source_items`

```json
{
  "id": "string",
  "source_type": "string",
  "medium_type": "string",
  "source_name": "string",
  "source_url": "string",
  "title": "string",
  "summary": "string",
  "content": "string",
  "language": "string",
  "published_at": "datetime",
  "collected_at": "datetime",
  "raw_payload_json": "json",
  "content_hash": "string",
  "ai_relevance_score": 0.0
}
```

### Vector Store

Use Chroma or LanceDB for MVP.

Chunk content format:

```text
Title: ...
Source: ...
Published At: ...
Content:
...
```

Chunk metadata:

```json
{
  "source_item_id": "string",
  "source_type": "tech_media",
  "medium_type": "article",
  "source_name": "TechCrunch",
  "published_at": "datetime",
  "language": "en",
  "title": "string",
  "url": "string"
}
```

## 13. Initial Source Configuration

The first version should be configuration-driven.

Example `configs/sources.yaml`:

```yaml
sources:
  - name: TechCrunch AI
    type: tech_media
    medium: article
    method: rss
    url: https://techcrunch.com/tag/artificial-intelligence/feed/
    language: en
    enabled: true

  - name: Google News AI
    type: aggregator
    medium: ranking_item
    method: rss
    query: artificial intelligence
    language: en
    enabled: true

  - name: arXiv cs.AI
    type: official
    medium: paper
    method: api
    query: cat:cs.AI OR cat:cs.CL OR cat:cs.LG
    language: en
    enabled: true

  - name: Reddit LocalLLaMA
    type: social
    medium: discussion
    method: json
    url: https://www.reddit.com/r/LocalLLaMA/top.json
    language: en
    enabled: true
```

## 14. MVP Source Mix

Recommended first implementation:

Tech media:

- TechCrunch AI
- The Verge AI
- MIT Technology Review AI
- 机器之心
- 量子位

Official channels:

- OpenAI Blog
- Google DeepMind Blog
- Anthropic News
- GitHub Releases
- arXiv

Social media:

- Reddit `r/MachineLearning`
- Reddit `r/LocalLLaMA`
- Reddit `r/OpenAI`

Aggregators:

- Google News RSS
- Hacker News Algolia API

## 15. Implementation Steps

1. Create `configs/sources.yaml`.
2. Define Pydantic schemas for raw and medium-specific source items.
3. Implement `rss_collector_tool`.
4. Implement `arxiv_collector_tool`.
5. Implement `github_release_collector_tool`.
6. Implement `hacker_news_collector_tool`.
7. Implement `reddit_collector_tool`.
8. Implement `web_article_extractor_tool`.
9. Implement keyword-based AI relevance filtering.
10. Implement URL, title, and content-hash deduplication.
11. Implement SQLite metadata storage.
12. Implement vector chunk generation and RAG ingestion.
13. Add a collection summary report per run.

## 16. Collection Summary Format

Every collection run should produce a summary:

```json
{
  "started_at": "datetime",
  "finished_at": "datetime",
  "candidate_count": 80,
  "ai_related_count": 32,
  "deduplicated_count": 18,
  "stored_count": 18,
  "source_breakdown": {
    "tech_media": 7,
    "official": 4,
    "social": 3,
    "aggregator": 4
  },
  "failed_sources": [
    {
      "source_name": "string",
      "reason": "string"
    }
  ]
}
```
