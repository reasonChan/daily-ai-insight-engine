# Daily AI Insight Engine

Daily AI Insight Engine 是一个本地优先的 AI 行业信息采集、结构化分析和日报生成系统。

它可以从科技媒体、官方渠道、聚合平台和社区来源中采集近期 AI 相关新闻或信息，经过清洗、去重、筛选、结构化抽取后，生成包含热点事件、深度总结、趋势判断和风险/机会提示的日报，并通过本地 Web Dashboard 展示。

## 当前能力

- 采集 10-20 条近期 AI 相关信息。
- 支持中英文来源混合。
- 单一来源最多保留 3 条，避免某个来源刷屏。
- 按热度、相关性、来源质量、内容质量和语言多样性筛选。
- 抽取结构化事件、实体、类别、重要性、风险分数。
- 生成日报分析：
  - 今日 AI 领域主要热点 Top 3-5
  - 重要事件深度总结
  - 技术 / 应用 / 政策 / 资本趋势判断
  - 风险与机会提示
- 前端中文展示。
- 来源列表标注中文/英文来源。
- 用户点击来源后再展示原始数据、摘要、正文、采集载荷和本源链接。

最近一次真实运行结果：

```json
{
  "candidate_count": 80,
  "ai_related_count": 69,
  "deduplicated_count": 20,
  "source_breakdown": {
    "aggregator": 6,
    "tech_media": 8,
    "official": 6
  }
}
```

最终日报入选来源：

```text
中文来源：3
英文来源：17
单一来源超过 3 条：无
热点数量：5
趋势方向：policy / technology / application / capital
```

## 项目结构

```text
daily-ai-insight-engine/
  backend/          后端采集、分析、存储、API
  frontend/         React + Vite 中文 Dashboard
  configs/          数据源配置
  docs/             架构和说明文档
  reports/          报告目录占位，生成报告默认不入库
  tests/            离线测试和 fixture
```

## 数据源说明

系统通过 `configs/sources.yaml` 配置数据源，当前覆盖四类来源。

| 来源类型 | 当前来源 | 语言 | 选择理由 | 数据特点 |
| --- | --- | --- | --- | --- |
| 科技媒体 | TechCrunch AI、The Verge AI、MIT Technology Review AI、机器之心 | 英文、中文 | 捕捉产品发布、产业事件、公司动态、应用趋势 | 新闻结构稳定，标题和摘要质量较高 |
| 官方渠道 | OpenAI Blog、Google DeepMind Blog、arXiv AI | 英文 | 一手信号，适合识别模型、产品、安全、研究更新 | 可信度高，但频率较低 |
| 聚合平台 | Google News AI、Google News AI 中文、Hacker News AI | 英文、中文 | 发现当天热点、多源重复报道和开发者社区热度 | 覆盖广，但需要去重和筛选 |
| 社交讨论 | Reddit LocalLLaMA、Reddit MachineLearning | 英文 | 捕捉社区反馈、舆情和风险信号 | 价值高，但容易受访问限制影响 |

数据源选择原则：

- 官方源提供可信的一手信息。
- 科技媒体保证行业事件覆盖。
- 聚合源提升热点发现能力。
- 社区源用于舆情和风险监测。
- 中文 Google News 源用于保证中文语料进入日报。

当前失败源会记录到日报和 API 中，不阻断系统运行。例如：

- arXiv AI：本地 SSL 证书校验失败时会记录错误。
- 机器之心：RSS/XML 解析失败时会记录错误。
- Reddit：HTTP 403 时会记录错误。

## 系统设计思路

系统采用本地优先、流水线式架构：

```text
数据源配置
  -> 采集器
  -> RawSourceItem 归一化
  -> AI 相关性筛选
  -> 去重
  -> 热度排序与来源限额
  -> SQLite 元数据存储
  -> RAG chunk 写入
  -> 事件抽取
  -> 事件聚类
  -> 洞察分析
  -> 风险评估
  -> 日报分析综合
  -> JSON / Markdown 报告
  -> FastAPI
  -> React 前端展示
```

关键决策：

- **配置驱动数据源**：所有来源写在 `configs/sources.yaml`，便于新增、禁用和替换。
- **统一原始数据模型**：不同来源先归一化为 `RawSourceItem`，后续流程不关心来源原始格式。
- **规则化 MVP**：当前核心分析使用确定性规则，保证输出稳定、可测试、可追溯。
- **分析和展示分离**：`DailyAnalysisAgent` 负责生成结构化分析，`DailyReportGenerator` 负责渲染 JSON 和 Markdown，前端只消费 API 数据。
- **证据链优先**：事件、洞察、风险和日报分析都保留 `source_item_id`，避免不可追溯的空洞结论。

## 结构化数据模型

### RawSourceItem

用于保存原始来源证据和元数据。

核心字段：

```text
id
source_type
medium_type
source_name
source_url
title
summary
content
language
published_at
collected_at
authors
tags
raw_payload
```

设计理由：

- `source_type` 区分官方、媒体、聚合、社交来源，影响可信度和热度评分。
- `medium_type` 区分文章、博客、论文、讨论、榜单项。
- `language` 用于中英文混合控制和前端标注。
- `raw_payload` 保留原始采集信息，便于审计和前端查看。
- `published_at` 和 `collected_at` 分离，便于判断信息时效。

### Event

用于把多条新闻信息抽象为可分析事件。

核心字段：

```text
id
title
summary
category
entities
related_source_item_ids
first_seen_at
latest_seen_at
importance_score
sentiment_score
risk_score
```

设计理由：

- `category` 支持模型、产品、研究、融资、政策、安全、基础设施、公司动态等分类。
- `entities` 抽取公司、产品、人物、模型、主题等实体。
- `related_source_item_ids` 保证事件可追溯回原始来源。
- `importance_score` 用于热点排序。
- `risk_score` 用于风险提示和日报排序。

### Insight

用于解释事件为什么重要。

核心字段：

```text
event_id
key_points
why_it_matters
affected_companies
affected_sectors
opportunities
risks
confidence
evidence_source_item_ids
```

它不只是摘要，而是要求输出影响对象、机会、风险和证据来源。

### RiskAssessment

用于多维度风险判断。

核心字段：

```text
public_opinion_risk
policy_risk
security_risk
business_risk
technical_risk
overall_risk
risk_factors
evidence_source_item_ids
```

风险被拆成舆情、政策、安全、商业、技术五个维度，而不是只给一个总分。

### DailyAnalysis

用于组织最终日报分析。

核心字段：

```text
hot_topics
deep_dives
trend_judgments
risk_opportunity_notes
evidence_source_item_ids
```

子结构：

- `HotTopic`：今日 Top 3-5 热点及入选理由。
- `EventDeepDive`：关键事件背景和影响分析。
- `TrendJudgment`：技术、应用、政策、资本方向趋势判断。
- `RiskOpportunityNote`：风险或机会提示。

## AI 使用方式

当前版本采用“AI 分析任务的结构化设计 + 规则化实现”。

也就是说，模块命名为 agent，但核心逻辑主要是确定性规则和结构化输出；这样即使没有外部 LLM API，也能稳定生成日报。

当前 agent：

- `EventExtractionAgent`：从来源条目抽取事件、类别、实体和重要性。
- `InsightAnalysisAgent`：生成事件影响、机会和风险说明。
- `RiskAssessmentAgent`：按多维风险规则评分。
- `DailyAnalysisAgent`：生成热点、深度总结、趋势判断、风险机会提示。

预留的 LLM Prompt 设计方向：

```text
事件抽取：
输入标题、摘要、正文、来源、发布时间。
输出事件标题、摘要、类别、实体、重要性、相关 source ids。
要求不得引入来源中不存在的事实。

洞察分析：
输入事件对象、相关来源文本、风险结果。
输出为什么重要、影响对象、机会、风险、证据 source ids、置信度。
要求所有结论必须对应证据来源。

日报综合：
输入 top events、insights、risk assessments、source breakdown。
输出热点、深度总结、趋势判断、风险机会提示。
要求每条判断必须说明逻辑依据和 evidence_source_item_ids。
```

错误处理：

- 单个来源失败不影响整次运行。
- 失败来源写入 `failed_sources`。
- RSS/XML 解析失败会记录具体原因。
- HTTP 403、SSL 失败等网络问题会记录到采集摘要和日报。
- 如果后续接入 LLM，LLM 超时或结构化输出校验失败时，应回退到规则化 agent。
- 不允许生成没有证据来源的分析结论。

## 核心流程

从原始数据到最终报告：

```text
1. 读取 configs/sources.yaml
2. 按来源类型选择采集器
3. 获取 RSS/API/JSON 原始数据
4. 归一化为 RawSourceItem
5. 执行 AI 相关性筛选
6. 对相关条目写入 ai_relevance 信息
7. 执行去重
8. 按热度排序并限制单源数量
9. 写入 SQLite source_items
10. 写入 RAG chunk 文件
11. 抽取 Event
12. 聚类相似 Event
13. 生成 Insight
14. 生成 RiskAssessment
15. 生成 DailyAnalysis
16. 渲染 JSON / Markdown 日报
17. 写入 daily_reports 存储
18. FastAPI 暴露报告和来源数据
19. 前端展示日报分析
20. 用户点击来源后查看原始数据和本源链接
```

## 数据清洗、去重、筛选、归一化策略

### 数据清洗

- RSS/Atom XML 被解析为条目。
- 标题、摘要、正文经过 `clean_text` 去除多余空白和 HTML 噪声。
- 发布时间统一解析为 datetime。
- RSS 的 `description`、`summary`、`content` 等字段映射到统一字段。
- 不具备标题或 URL 的条目会被跳过。
- 没有摘要但有正文，或没有正文但有摘要的条目仍可进入系统。

### 归一化

```text
RSS item / API payload / JSON payload
  -> collector-specific parser
  -> make_raw_source_item
  -> RawSourceItem Pydantic validation
```

归一化保证：

- 后续流程不关心来源原始格式。
- 所有条目都有统一字段。
- 原始载荷保存在 `raw_payload`，用于审计和前端查看。

### AI 相关性筛选

当前使用中英文关键词规则判断 AI 相关性。

英文关键词示例：

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
multimodal
alignment
```

中文关键词示例：

```text
人工智能
生成式AI
生成式 AI
大模型
大语言模型
智能体
多模态
算力
芯片
机器学习
深度学习
```

筛选输出：

```json
{
  "is_ai_related": true,
  "relevance_score": 0.5,
  "matched_keywords": ["OpenAI", "LLM"],
  "topics": ["company", "llm"]
}
```

### 去重

当前使用三层去重：

1. URL 去重：去除尾部 `/`，忽略 fragment。
2. 标题去重：对标题做大小写归一化和符号清理。
3. 内容哈希去重：对标题、摘要、正文组合生成 SHA256。

可以处理：

- 同一 URL 的 UTM 变体。
- 多源聚合中标题完全相同的重复报道。
- URL 不同但内容一致的重复项。

### 热度排序与来源限制

去重后不直接按时间截断，而是按热度选择。

热度分数考虑：

- AI 相关性分数
- 来源类型权重
- 内容长度和质量
- 社区互动字段，例如 points、score、comments
- 中文多样性加分

选择规则：

- 默认目标数量：20 条。
- 单一 `source_name` 最多 3 条。
- 默认至少保留 3 条中文条目。
- 中文条目内部同样按热度选择。
- 剩余名额按整体热度补齐。

## 前端展示

前端通过 FastAPI 获取：

- `/health`
- `/reports/latest`
- `/events`
- `/source-items`

展示策略：

- 默认展示日报分析和结构化结论。
- 来源列表优先展示最新日报入选的 20 条。
- 每条来源标注中文或英文来源。
- 默认隐藏原始数据。
- 用户点击来源后，才展示摘要、正文、原始采集载荷和本源链接。

## 快速开始

安装后端依赖：

```bash
pip install -r requirements.txt
```

安装前端依赖：

```bash
cd frontend
npm install
```

运行一次采集并生成日报：

```bash
python -m backend.app.cli collect \
  --config configs/sources.yaml \
  --db data/live_source_items.sqlite \
  --rag-dir data/rag \
  --chunks data/rag/live_chunks.jsonl \
  --summary reports/daily/live_collection_summary.json \
  --per-source-limit 10 \
  --target-limit 20 \
  --max-items-per-source 3 \
  --min-chinese-items 3 \
  --with-report \
  --report-dir reports/daily
```

启动 API：

```bash
uvicorn backend.app.api.main:app --reload --port 8000
```

启动前端：

```bash
cd frontend
npm run dev
```

访问：

```text
http://localhost:5173
```

## 测试

```bash
python -m pytest
```

Windows 本地如遇系统临时目录权限问题，可以指定测试临时目录：

```bash
python -m pytest -q --basetemp .pytest-tmp-local
```

## 文档

- `docs/overall-architecture.md`：整体架构。
- `docs/data-source-implementation.md`：数据源层实现计划。
- `docs/remaining-architecture-implementation-plan.md`：后续架构实施计划。
- `docs/system-design-and-data-flow-cn.md`：中文系统说明文档。

## 当前限制

- 部分来源受网络、证书或反爬限制影响。
- 机器之心 RSS 当前可能出现 XML 解析失败。
- Reddit 当前可能返回 403。
- 当前分析主要是规则化实现，还未接入外部 LLM 做高级自然语言推理。

后续可改进：

- 增加更稳定的中文 RSS 或 API 来源。
- 为 Google News RSS 解析原始媒体来源名和真实跳转 URL。
- 增加文章正文抽取器，提升正文质量。
- 接入 LLM 进行结构化输出增强，但保留规则 fallback。
- 增加历史趋势分析，比较今日与 7 日 / 30 日平均水平。
