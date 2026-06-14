# Daily AI Insight Engine 系统说明文档

## 1. 数据源说明

### 1.1 当前数据源

系统通过 `configs/sources.yaml` 配置数据源，当前覆盖四类来源：

| 来源类型 | 当前来源 | 语言 | 选择理由 | 数据特点 |
| --- | --- | --- | --- | --- |
| 科技媒体 | TechCrunch AI、The Verge AI、MIT Technology Review AI、机器之心 | 英文、中文 | 科技媒体适合捕捉产品发布、产业事件、公司动态、应用趋势 | 新闻结构相对稳定，标题和摘要质量较高，适合事件抽取 |
| 官方渠道 | OpenAI Blog、Google DeepMind Blog、arXiv AI | 英文 | 官方源是一手信号，适合识别模型、产品、安全、研究方向更新 | 可信度高，但频率较低；arXiv 受网络证书影响可能失败 |
| 聚合平台 | Google News AI、Google News AI 中文、Hacker News AI | 英文、中文 | 聚合源适合发现当天热点和多源重复报道，HN 适合捕捉开发者社区热度 | 覆盖广，但可能包含重复、标题党或二手来源，需要去重和筛选 |
| 社交讨论 | Reddit LocalLLaMA、Reddit MachineLearning | 英文 | 社区源适合发现舆情、开发者反馈、工具体验和风险信号 | 讨论价值高，但容易受访问限制影响，当前 Reddit 返回 403 |

### 1.2 最新运行数据

最近一次运行摘要：

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

最终日报入选 20 条 AI 相关信息：

- 中文来源：3 条
- 英文来源：17 条
- 单一来源最多 3 条
- 覆盖来源：Google News AI 中文、Hacker News AI、MIT Technology Review AI、The Verge AI、OpenAI Blog、Google DeepMind Blog、TechCrunch AI

当前失败源会被记录到日报和 API 中，不会阻断整条流水线：

- arXiv AI：本地 SSL 证书校验失败
- 机器之心：RSS/XML 解析失败
- Reddit LocalLLaMA：HTTP 403
- Reddit MachineLearning：HTTP 403

### 1.3 数据源选择理由

系统没有只依赖单一新闻源，而是采用多源混合：

- 官方源保证可信度和一手信息。
- 科技媒体保证行业事件覆盖。
- 聚合源保证热点发现能力。
- 社区源预留舆情和风险监测能力。
- 中文 Google News 源用于保证中文语料进入日报，提升中英文混合分析能力。

为了避免单一来源刷屏，采集后会执行全局热度排序和来源上限控制：

- 每个 `source_name` 最多保留 3 条。
- 默认目标数量为 20 条。
- 默认保留至少 3 条中文高相关数据。
- 其余名额按热度排序选择。

## 2. 系统设计思路

### 2.1 整体架构

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

### 2.2 关键设计决策

#### 使用配置驱动数据源

所有来源写在 `configs/sources.yaml` 中，而不是写死在代码里。这样可以快速新增、禁用或替换来源。

#### 使用统一原始数据模型

所有采集器先归一化为 `RawSourceItem`。不同来源可能是 RSS、API、JSON 或聚合条目，但进入后续流程前必须具备统一字段：

- 标题
- 摘要或正文
- 来源名称
- 来源 URL
- 发布时间
- 采集时间
- 语言
- 原始载荷

这样后续去重、评分、分析和展示都可以使用同一套接口。

#### MVP 阶段优先使用确定性规则

当前系统没有把核心逻辑完全交给大模型，而是使用规则化、可解释的 pipeline：

- 关键词相关性判断
- URL、标题、内容哈希去重
- 热度加权排序
- 来源上限控制
- 规则化事件抽取
- 规则化风险评分
- 结构化日报分析

这样做的原因：

- 输出稳定，便于测试。
- 每条分析可以追溯到 source item。
- 即使没有外部 LLM API，也能生成完整日报。
- 后续可以把 LLM 作为增强层，而不是替代基础逻辑。

#### 分析和展示分离

`DailyAnalysisAgent` 负责生成结构化分析，`DailyReportGenerator` 只负责渲染 JSON 和 Markdown。前端只消费 API 返回的数据，不在前端重新做分析判断。

## 3. 结构化数据模型设计

### 3.1 原始来源模型：RawSourceItem

设计目的：保存证据和来源元数据。

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

字段设计理由：

- `source_type` 用于区分官方、媒体、聚合、社交来源，影响可信度和热度评分。
- `medium_type` 用于区分文章、博客、论文、讨论、榜单项。
- `language` 用于中英文混合控制和前端标注。
- `raw_payload` 用于保留原始采集信息，方便用户点击查看原始数据。
- `published_at` 和 `collected_at` 分离，便于判断信息时效性。

### 3.2 事件模型：Event

设计目的：把多条新闻信息抽象为“可分析事件”。

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

字段设计理由：

- `category` 支持模型、产品、研究、融资、政策、安全、基础设施、公司动态等分类。
- `entities` 抽取公司、产品、人物、模型、主题等结构化实体。
- `related_source_item_ids` 保证每个事件都能追溯回原始来源。
- `importance_score` 用于热点排序。
- `risk_score` 用于风险提示和日报排序。

### 3.3 洞察模型：Insight

设计目的：解释事件为什么重要。

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

字段设计理由：

- `why_it_matters` 避免只做摘要，要求说明事件影响。
- `affected_companies` 和 `affected_sectors` 支持行业分析。
- `opportunities` 和 `risks` 支持行动建议。
- `confidence` 表示分析置信度。
- `evidence_source_item_ids` 保证分析不是空洞判断。

### 3.4 风险模型：RiskAssessment

设计目的：把风险拆成可比较的维度。

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

字段设计理由：

- AI 新闻的风险可能来自政策、安全、商业、技术或舆情，不适合只给一个总分。
- `risk_factors` 记录触发风险的关键词或证据。
- `overall_risk` 用于日报风险提示排序。

### 3.5 日报分析模型：DailyAnalysis

设计目的：组织最终日报中的分析模块。

核心字段：

```text
hot_topics
deep_dives
trend_judgments
risk_opportunity_notes
evidence_source_item_ids
```

子结构包括：

- `HotTopic`：今日 Top 3-5 热点及入选理由。
- `EventDeepDive`：关键事件背景和影响分析。
- `TrendJudgment`：技术、应用、政策、资本方向趋势判断。
- `RiskOpportunityNote`：风险或机会提示。

字段设计理由：

- 热点、深度总结、趋势、风险机会是日报的不同分析层级。
- 每个分析对象都带事件 ID 和来源 ID，避免生成不可追溯的空洞结论。

## 4. AI 使用方式

### 4.1 当前使用场景

当前版本采用“AI 分析任务的结构化设计 + 规则化实现”的方式。也就是说，模块命名为 agent，但核心逻辑主要是确定性规则和结构化输出。

当前 agent 包括：

- `EventExtractionAgent`：从来源条目中抽取事件、类别、实体和重要性。
- `InsightAnalysisAgent`：生成事件影响、机会和风险说明。
- `RiskAssessmentAgent`：按多维度风险规则评分。
- `DailyAnalysisAgent`：生成日报热点、深度总结、趋势判断、风险机会提示。

### 4.2 Prompt 设计思路

当前没有强依赖外部 LLM Prompt。系统已经预留了适合接入 LLM 的结构化 prompt 方向：

#### 事件抽取 Prompt 目标

```text
输入：标题、摘要、正文、来源、发布时间。
输出：事件标题、摘要、类别、实体、重要性、相关 source ids。
要求：不得引入来源中不存在的事实。
```

#### 洞察分析 Prompt 目标

```text
输入：事件对象、相关来源文本、风险结果。
输出：为什么重要、影响对象、机会、风险、证据 source ids、置信度。
要求：所有结论必须能对应证据来源。
```

#### 日报综合 Prompt 目标

```text
输入：Top events、insights、risk assessments、source breakdown。
输出：热点、深度总结、趋势判断、风险机会提示。
要求：每条判断必须说明逻辑依据和 evidence_source_item_ids。
```

### 4.3 错误处理

系统当前错误处理原则：

- 单个来源失败不影响整次运行。
- 失败来源写入 `failed_sources`。
- RSS/XML 解析失败会记录具体原因。
- HTTP 403、SSL 失败等网络问题会记录到采集摘要和日报。
- LLM 尚未作为硬依赖，因此不存在模型调用失败导致日报无法生成的问题。
- 结构化对象使用 Pydantic 校验，字段不合法会在测试或采集边界暴露。

如果后续接入 LLM，应保持以下 fallback：

- LLM 结构化输出校验失败时，回退到规则化 agent。
- LLM 超时或 API 错误时，继续生成低置信度日报。
- 不允许 LLM 生成无 evidence_source_item_ids 的结论。

## 5. 核心流程说明

### 5.1 从原始数据到最终报告

完整流程如下：

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

### 5.2 数据清洗流程

清洗主要发生在采集器阶段：

- RSS/Atom XML 被解析为条目。
- 标题、摘要、正文经过 `clean_text` 去除多余空白和 HTML 噪声。
- 发布时间统一解析为 datetime。
- RSS 的 `description`、`summary`、`content` 等字段被映射到统一字段。
- 不具备标题或 URL 的条目会被跳过。
- 没有摘要但有正文，或没有正文但有摘要的条目仍可进入系统。

### 5.3 归一化流程

每个采集器输出最终都会变成 `RawSourceItem`：

```text
RSS item / API payload / JSON payload
  -> collector-specific parser
  -> make_raw_source_item
  -> RawSourceItem Pydantic validation
```

归一化保证：

- 后续流程不关心来源原始格式。
- 所有条目都有统一字段。
- 原始载荷仍保存在 `raw_payload`，用于审计和前端查看。

### 5.4 AI 相关性筛选

当前使用关键词规则判断是否 AI 相关。

英文关键词包括：

- AI
- artificial intelligence
- generative AI
- LLM
- large language model
- agent
- OpenAI
- Anthropic
- Claude
- Gemini
- DeepMind
- multimodal
- alignment

中文关键词包括：

- 人工智能
- 生成式AI
- 生成式 AI
- 大模型
- 大语言模型
- 智能体
- 多模态
- 算力
- 芯片
- 机器学习
- 深度学习

筛选输出：

```json
{
  "is_ai_related": true,
  "relevance_score": 0.5,
  "matched_keywords": ["OpenAI", "LLM"],
  "topics": ["company", "llm"]
}
```

### 5.5 去重策略

系统当前使用三层去重：

1. URL 去重  
   去除尾部 `/`，忽略 fragment。

2. 标题去重  
   对标题做大小写归一化和符号清理。

3. 内容哈希去重  
   对标题、摘要、正文组合生成 SHA256。

这样可以处理：

- 同一 URL 的 UTM 变体。
- 多源聚合中标题完全相同的重复报道。
- URL 不同但内容一致的重复项。

### 5.6 热度排序与来源限制

去重后不直接按时间截断，而是按热度选择。

当前热度分数考虑：

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

这解决了两个问题：

- 防止 Google News 或某个媒体来源占满日报。
- 保证中文来源不会被英文高频来源完全挤出。

### 5.7 事件抽取和聚类

事件抽取流程：

```text
RawSourceItem
  -> 合并 title / summary / content / tags
  -> 关键词判断 category
  -> 已知公司、模型、主题实体识别
  -> 生成 Event
```

事件聚类流程：

- 类别必须一致。
- 发布时间相差不超过 2 天。
- 标题 token Jaccard 相似度达到阈值，或标题相似且实体重合。
- 聚类后合并相关 source ids、实体、时间窗口和分数。

### 5.8 洞察、风险和日报分析

洞察分析：

- 使用事件摘要、来源标题、实体和类别生成 key points。
- 输出为什么重要、影响公司/领域、机会和风险。

风险分析：

- 按舆情、政策、安全、商业、技术五个维度打分。
- 使用风险关键词触发不同维度。
- 计算 `overall_risk`。

日报分析：

- `hot_topics`：按重要性、风险、来源覆盖、实体、来源权重、时效性排序。
- `deep_dives`：对 Top 事件生成背景和影响分析。
- `trend_judgments`：按技术、应用、政策、资本方向聚合事件。
- `risk_opportunity_notes`：基于风险分数和机会字段生成行动提示。

### 5.9 前端展示流程

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

## 6. 当前限制和后续改进

当前限制：

- 部分来源受网络、证书或反爬限制影响。
- 机器之心 RSS 当前 XML 解析失败。
- Reddit 当前返回 403。
- 当前分析主要是规则化实现，还未接入外部 LLM 做高级自然语言推理。

后续改进：

- 增加更稳定的中文 RSS 或 API 来源。
- 为 Google News RSS 解析原始媒体来源名和真实跳转 URL。
- 增加文章正文抽取器，提升摘要之外的正文质量。
- 接入 LLM 进行结构化输出增强，但必须保留规则 fallback。
- 增加历史趋势分析，比较今日与 7 日/30 日平均水平。
