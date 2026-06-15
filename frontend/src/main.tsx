import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Database,
  ExternalLink,
  FileText,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type Health = {
  status: string;
  storage: { source_item_count: number; source_db_exists: boolean };
  reports: { latest_report_exists: boolean; latest_report: string | null };
  failed_source_count: number;
};

type SourceItem = {
  id: string;
  source_type: string;
  medium_type: string;
  source_name: string;
  source_url: string;
  title: string;
  summary: string;
  content?: string;
  raw_payload?: Record<string, unknown>;
  language: string;
  published_at: string;
  ai_relevance_score: number;
};

type EventItem = {
  id: string;
  title: string;
  summary?: string;
  category?: string;
  related_source_item_ids?: string[];
  importance_score?: number;
  risk_score?: number;
};

type HotTopic = {
  rank: number;
  title: string;
  category: string;
  importance_score: number;
  hot_score: number;
  reason: string;
  supporting_event_ids: string[];
  evidence_source_item_ids: string[];
};

type EventDeepDive = {
  event_id: string;
  title: string;
  background: string;
  impact_analysis: string;
  affected_entities: string[];
  evidence: string[];
  evidence_source_item_ids: string[];
  confidence: number;
};

type TrendJudgment = {
  direction: "technology" | "application" | "policy" | "capital";
  judgment: string;
  logic: string;
  supporting_event_ids: string[];
  evidence_source_item_ids: string[];
  signal_strength: number;
  confidence: number;
};

type RiskOpportunityNote = {
  type: "risk" | "opportunity";
  title: string;
  rationale: string;
  related_event_ids: string[];
  evidence_source_item_ids: string[];
  priority: number;
};

type DailyAnalysis = {
  report_date: string;
  hot_topics: HotTopic[];
  deep_dives: EventDeepDive[];
  trend_judgments: TrendJudgment[];
  risk_opportunity_notes: RiskOpportunityNote[];
  evidence_source_item_ids: string[];
  generated_at: string;
};

type DailyArticleSection = {
  heading: string;
  content: string;
  related_event_ids: string[];
  evidence_source_item_ids: string[];
};

type DailyArticle = {
  title: string;
  subtitle?: string | null;
  lead: string;
  body_sections: DailyArticleSection[];
  trend_outlook: string;
  risk_opportunity: string;
  evidence_source_item_ids: string[];
  generated_by: string;
  generated_at: string;
};

type Report = {
  report_date?: string;
  executive_summary?: string;
  top_events?: EventItem[];
  risk_alerts?: Array<Record<string, unknown>>;
  daily_analysis?: DailyAnalysis | null;
  daily_article?: DailyArticle | null;
  notable_source_items?: Array<{ id: string; language?: string }>;
  source_breakdown?: Record<string, number>;
  failed_sources?: Array<{ source_name?: string; reason?: string } | string>;
  generated_at?: string;
};

function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [sourceItems, setSourceItems] = useState<SourceItem[]>([]);
  const [sourceType, setSourceType] = useState("");
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadData(nextSourceType = sourceType) {
    setLoading(true);
    setError(null);
    try {
      const params = nextSourceType ? `?source_type=${encodeURIComponent(nextSourceType)}` : "";
      const [healthData, reportData, eventsData, sourceData] = await Promise.all([
        fetchJson<Health>("/health"),
        fetchJson<Report>("/reports/latest").catch(() => null),
        fetchJson<{ items: EventItem[] }>("/events"),
        fetchJson<{ items: SourceItem[] }>(`/source-items${params}`),
      ]);
      const nextEvents = eventsData.items ?? [];
      const nextSources = sourceData.items ?? [];
      setHealth(healthData);
      setReport(reportData);
      setEvents(nextEvents);
      setSourceItems(nextSources);
      setSelectedEventId((current) =>
        current && nextEvents.some((event) => event.id === current) ? current : nextEvents[0]?.id ?? null,
      );
      setSelectedSourceId((current) =>
        current && nextSources.some((item) => item.id === current) ? current : null,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法加载仪表盘数据。");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  const selectedEvent = useMemo(
    () => events.find((event) => event.id === selectedEventId) ?? events[0],
    [events, selectedEventId],
  );
  const selectedSource = useMemo(
    () => sourceItems.find((item) => item.id === selectedSourceId) ?? null,
    [sourceItems, selectedSourceId],
  );
  const linkedSourceItems = useMemo(() => {
    const ids = new Set(selectedEvent?.related_source_item_ids ?? []);
    return sourceItems.filter((item) => ids.has(item.id));
  }, [selectedEvent, sourceItems]);
  const displayedSourceItems = useMemo(() => {
    const reportSourceIds = new Set((report?.notable_source_items ?? []).map((item) => item.id));
    if (!reportSourceIds.size) {
      return sourceItems;
    }
    return sourceItems.filter((item) => reportSourceIds.has(item.id));
  }, [report, sourceItems]);
  const riskAlerts = report?.risk_alerts ?? [];
  const failedSources = report?.failed_sources ?? [];
  const analysis = report?.daily_analysis ?? null;
  const sourceTypes = Array.from(new Set(displayedSourceItems.map((item) => item.source_type))).sort();
  const languageBreakdown = useMemo(() => {
    return displayedSourceItems.reduce<Record<string, number>>((result, item) => {
      const label = languageLabel(item.language);
      result[label] = (result[label] ?? 0) + 1;
      return result;
    }, {});
  }, [displayedSourceItems]);

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">本地分析工作台</p>
          <h1>每日 AI 洞察引擎</h1>
        </div>
        <button className="iconButton" onClick={() => loadData()} title="刷新仪表盘数据" aria-label="刷新仪表盘数据">
          <RefreshCw size={18} />
        </button>
      </header>

      {error ? <div className="banner">{error}</div> : null}

      <section className="metrics">
        <Metric icon={<Activity size={18} />} label="API 状态" value={statusLabel(health?.status, loading)} />
        <Metric icon={<Database size={18} />} label="日报来源" value={displayedSourceItems.length || health?.storage.source_item_count || sourceItems.length} />
        <Metric icon={<FileText size={18} />} label="重点事件" value={report?.top_events?.length ?? events.length} />
        <Metric icon={<Sparkles size={18} />} label="热点数量" value={analysis?.hot_topics.length ?? 0} />
        <Metric icon={<ShieldAlert size={18} />} label="风险预警" value={riskAlerts.length} />
        <Metric icon={<AlertTriangle size={18} />} label="失败来源" value={health?.failed_source_count ?? failedSources.length} />
      </section>

      <section className="workspace">
        <DailyArticleView report={report} events={events} languageBreakdown={languageBreakdown} />

        <article className="panel">
          <div className="panelHeader">
            <div>
              <p className="eyebrow">风险区域</p>
              <h2>预警</h2>
            </div>
          </div>
          <div className="stack">
            {riskAlerts.length ? (
              riskAlerts.map((risk, index) => (
                <div className="riskRow" key={`${risk.id ?? risk.event_id ?? index}`}>
                  <strong>{String(risk.event_id ?? risk.id ?? "风险项")}</strong>
                  <span>{riskScoreLabel(risk.overall_risk)}</span>
                </div>
              ))
            ) : (
              <p className="muted">最新日报中暂无高风险预警。</p>
            )}
          </div>
        </article>
      </section>

      <DailyAnalysisView analysis={analysis} />

      <section className="grid">
        <article className="panel">
          <div className="panelHeader">
            <div>
              <p className="eyebrow">事件</p>
              <h2>重点信号</h2>
            </div>
          </div>
          <div className="eventList">
            {events.map((event) => (
              <button
                className={event.id === selectedEvent?.id ? "eventButton active" : "eventButton"}
                key={event.id}
                onClick={() => setSelectedEventId(event.id)}
              >
                <span>{event.title}</span>
                <small>
                  {categoryLabel(event.category)} / 风险 {formatScore(event.risk_score)}
                </small>
              </button>
            ))}
            {!events.length ? <p className="muted">暂无事件数据。</p> : null}
          </div>
        </article>

        <article className="panel detailPanel">
          <div className="panelHeader">
            <div>
              <p className="eyebrow">事件详情</p>
              <h2>{selectedEvent?.title ?? "请选择一个事件"}</h2>
            </div>
          </div>
          <p className="summary">{selectedEvent?.summary ?? "当前未选择事件。"}</p>
          <div className="linkedSources">
            {(linkedSourceItems.length ? linkedSourceItems : displayedSourceItems.slice(0, 3)).map((item) => (
              <SourceButton item={item} key={item.id} onClick={() => setSelectedSourceId(item.id)} />
            ))}
          </div>
        </article>
      </section>

      <section className="grid">
        <article className="panel">
          <div className="panelHeader">
            <div>
              <p className="eyebrow">来源条目</p>
              <h2>近期证据</h2>
            </div>
            <label className="filter" aria-label="按来源类型筛选">
              <Search size={16} />
              <select
                value={sourceType}
                onChange={(event) => {
                  setSourceType(event.target.value);
                  loadData(event.target.value);
                }}
              >
                <option value="">全部来源类型</option>
                {sourceTypes.map((type) => (
                  <option key={type} value={type}>
                    {sourceTypeLabel(type)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="sourceTable">
            {displayedSourceItems.map((item) => (
              <button className="sourceRow" key={item.id} onClick={() => setSelectedSourceId(item.id)}>
                <span>{item.title}</span>
                <small>{item.source_name}</small>
                <small>{languageLabel(item.language)}来源</small>
                <small>{formatDate(item.published_at)}</small>
              </button>
            ))}
            {!sourceItems.length ? <p className="muted">暂无来源条目。</p> : null}
          </div>
        </article>

        <SourceRawDataPanel source={selectedSource} />
      </section>

      <section className="panel">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">失败来源</p>
            <h2>采集问题</h2>
          </div>
        </div>
        <div className="stack">
          {failedSources.length ? (
            failedSources.map((failure, index) => {
              const label = typeof failure === "string" ? failure : `${failure.source_name ?? "来源"}：${failure.reason ?? "原因未知"}`;
              return (
                <div className="failureRow" key={index}>
                  {label}
                </div>
              );
            })
          ) : (
            <p className="muted">暂无失败来源。</p>
          )}
        </div>
      </section>
    </main>
  );
}

function DailyArticleView({
  report,
  events,
  languageBreakdown,
}: {
  report: Report | null;
  events: EventItem[];
  languageBreakdown: Record<string, number>;
}) {
  const article = report?.daily_article ?? null;
  const articleGeneratedAt = article?.generated_at || report?.generated_at;

  if (!article) {
    return (
      <article className="panel reportPanel">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">最新日报</p>
            <h2>{report?.report_date ?? "暂无日报"}</h2>
          </div>
          <span className="pill">{report?.generated_at ? formatDate(report.generated_at) : "等待生成"}</span>
        </div>
        <p className="summary">{report ? chineseExecutiveSummary(report, events) : "生成日报后，这里会展示中文文章。"}</p>
        <SourceBreakdown report={report} languageBreakdown={languageBreakdown} />
      </article>
    );
  }

  return (
    <article className="panel reportPanel dailyArticle">
      <div className="articleMetaRow">
        <div>
          <p className="eyebrow">最新日报</p>
          <span>{report?.report_date ?? "今日"}</span>
        </div>
        <span className="pill">{articleGeneratedAt ? formatDate(articleGeneratedAt) : "等待生成"}</span>
      </div>

      <header className="articleHeader">
        <h2>{article.title}</h2>
        {article.subtitle ? <p>{article.subtitle}</p> : null}
      </header>

      <p className="articleLead">{article.lead}</p>

      <div className="articleBody">
        {(article.body_sections ?? []).map((section, index) => (
          <section className="articleSection" key={`${section.heading}-${index}`}>
            <div className="sectionTitleRow">
              <h3>{section.heading}</h3>
              <span className="evidenceBadge">证据 {section.evidence_source_item_ids.length}</span>
            </div>
            <p>{section.content}</p>
          </section>
        ))}
        {article.body_sections?.length ? null : <p className="muted">正文段落生成中。</p>}
      </div>

      <section className="articleConclusion">
        <div>
          <h3>趋势判断</h3>
          <p>{article.trend_outlook}</p>
        </div>
        <div>
          <h3>风险与机会</h3>
          <p>{article.risk_opportunity}</p>
        </div>
      </section>

      <footer className="articleFooter">
        <span className="evidenceBadge">全文证据 {article.evidence_source_item_ids.length}</span>
        <span>生成方式：{generationLabel(article.generated_by)}</span>
      </footer>

      <SourceBreakdown report={report} languageBreakdown={languageBreakdown} />
    </article>
  );
}

function SourceBreakdown({
  report,
  languageBreakdown,
}: {
  report: Report | null;
  languageBreakdown: Record<string, number>;
}) {
  const sourceEntries = Object.entries(report?.source_breakdown ?? {});
  const languageEntries = Object.entries(languageBreakdown);

  if (!sourceEntries.length && !languageEntries.length) {
    return null;
  }

  return (
    <div className="breakdown sourceMetaBreakdown">
      {sourceEntries.map(([name, count]) => (
        <span key={name}>
          {sourceTypeLabel(name)}：<strong>{count}</strong>
        </span>
      ))}
      {languageEntries.map(([name, count]) => (
        <span key={name}>
          {name}来源：<strong>{count}</strong>
        </span>
      ))}
    </div>
  );
}

function DailyAnalysisView({ analysis }: { analysis: DailyAnalysis | null }) {
  if (!analysis) {
    return (
      <section className="panel">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">日报分析</p>
            <h2>等待结构化分析</h2>
          </div>
        </div>
        <p className="summary">后端生成含 daily_analysis 的日报后，这里会展示热点、深度总结、趋势判断和风险机会提示。</p>
      </section>
    );
  }

  return (
    <section className="analysisGrid">
      <article className="panel analysisPanel spanTwo">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">日报分析</p>
            <h2>今日 AI 领域主要热点</h2>
          </div>
          <span className="pill">{analysis.hot_topics.length} 条</span>
        </div>
        <div className="hotTopicList">
          {analysis.hot_topics.map((topic) => (
            <div className="hotTopic" key={`${topic.rank}-${topic.title}`}>
              <strong>{topic.rank}</strong>
              <div>
                <h3>{hotTopicHeadline(topic)}</h3>
                <p>{hotTopicReason(topic)}</p>
                <p className="originalTitle">原始标题：{topic.title}</p>
                <small>
                  {categoryLabel(topic.category)} / 热度 {formatScore(topic.hot_score)} / 证据 {topic.evidence_source_item_ids.length}
                </small>
              </div>
            </div>
          ))}
          {!analysis.hot_topics.length ? <p className="muted">暂无高置信热点。</p> : null}
        </div>
      </article>

      <article className="panel analysisPanel">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">深度总结</p>
            <h2>关键事件影响</h2>
          </div>
        </div>
        <div className="stack">
          {analysis.deep_dives.map((dive) => (
            <div className="analysisCard" key={dive.event_id}>
              <h3>{deepDiveHeadline(dive)}</h3>
              <p>{deepDiveSummary(dive)}</p>
              <p className="originalTitle">原始标题：{dive.title}</p>
              <small>置信度 {formatScore(dive.confidence)} / 证据 {dive.evidence_source_item_ids.length}</small>
            </div>
          ))}
          {!analysis.deep_dives.length ? <p className="muted">暂无足够证据形成深度总结。</p> : null}
        </div>
      </article>

      <article className="panel analysisPanel">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">趋势判断</p>
            <h2>方向洞察</h2>
          </div>
          <BarChart3 size={18} />
        </div>
        <div className="stack">
          {analysis.trend_judgments.map((trend) => (
            <div className="analysisCard" key={trend.direction}>
              <h3>{trendDirectionLabel(trend.direction)}</h3>
              <p>{trendSummary(trend)}</p>
              <p>{trendLogic(trend)}</p>
              <small>
                强度 {formatScore(trend.signal_strength)} / 置信度 {formatScore(trend.confidence)}
              </small>
            </div>
          ))}
          {!analysis.trend_judgments.length ? <p className="muted">暂无清晰趋势信号。</p> : null}
        </div>
      </article>

      <article className="panel analysisPanel spanTwo">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">风险与机会提示</p>
            <h2>行动关注点</h2>
          </div>
        </div>
        <div className="noteGrid">
          {analysis.risk_opportunity_notes.map((note, index) => (
            <div className={note.type === "risk" ? "noteCard riskNote" : "noteCard opportunityNote"} key={`${note.type}-${index}`}>
              <span>{note.type === "risk" ? "风险" : "机会"}</span>
              <h3>{noteHeadline(note)}</h3>
              <p>{noteRationale(note)}</p>
              <small>优先级 {formatScore(note.priority)}</small>
            </div>
          ))}
          {!analysis.risk_opportunity_notes.length ? <p className="muted">暂无显著风险或机会提示。</p> : null}
        </div>
      </article>
    </section>
  );
}

function SourceButton({ item, onClick }: { item: SourceItem; onClick: () => void }) {
  return (
    <button className="sourceChip" onClick={onClick}>
      <strong>{item.title}</strong>
      <span>
        {item.source_name} / {languageLabel(item.language)}来源
      </span>
    </button>
  );
}

function SourceRawDataPanel({ source }: { source: SourceItem | null }) {
  return (
    <article className="panel detailPanel">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">原始数据</p>
          <h2>{source ? "来源详情" : "点击来源查看"}</h2>
        </div>
        {source ? <span className="pill">{languageLabel(source.language)}来源</span> : null}
      </div>
      {source ? (
        <div className="rawData">
          <h3>{source.title}</h3>
          <dl>
            <div>
              <dt>来源名称</dt>
              <dd>{source.source_name}</dd>
            </div>
            <div>
              <dt>来源类型</dt>
              <dd>{sourceTypeLabel(source.source_type)}</dd>
            </div>
            <div>
              <dt>发布时间</dt>
              <dd>{formatDate(source.published_at)}</dd>
            </div>
            <div>
              <dt>AI 相关度</dt>
              <dd>{formatScore(source.ai_relevance_score)}</dd>
            </div>
          </dl>
          <section>
            <h4>摘要</h4>
            <p>{source.summary || "暂无摘要。"}</p>
          </section>
          <section>
            <h4>正文或原始内容</h4>
            <p>{source.content || source.summary || "暂无正文内容。"}</p>
          </section>
          <section>
            <h4>原始采集载荷</h4>
            <pre>{JSON.stringify(source.raw_payload ?? {}, null, 2)}</pre>
          </section>
          <a className="sourceLink" href={source.source_url} target="_blank" rel="noreferrer">
            打开本源链接 <ExternalLink size={15} />
          </a>
        </div>
      ) : (
        <p className="summary">默认隐藏原始数据。请在“近期证据”或事件详情中点击一条来源，再查看摘要、正文、采集载荷和本源链接。</p>
      )}
    </article>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string | number }) {
  return (
    <div className="metric">
      {icon}
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`${path} 返回 ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN");
}

function chineseExecutiveSummary(report: Report, events: EventItem[]) {
  const topEvents = report.top_events ?? events;
  const eventCount = topEvents.length || events.length;
  const riskCount = report.risk_alerts?.length ?? 0;
  const sourceTotal = Object.values(report.source_breakdown ?? {}).reduce((sum, count) => sum + count, 0);
  const date = report.report_date ? `${report.report_date} ` : "";
  const hotTopics = report.daily_analysis?.hot_topics ?? [];
  const trends = report.daily_analysis?.trend_judgments ?? [];
  const categories = Array.from(new Set(hotTopics.map((topic) => categoryLabel(topic.category)))).slice(0, 3);
  const trendNames = trends.map((trend) => trendDirectionLabel(trend.direction)).slice(0, 4);
  const sourceText = sourceTotal ? `共跟踪 ${sourceTotal} 条来源信息` : "已完成来源信息汇总";
  const eventText = `筛选出 ${eventCount} 个重点事件`;
  const riskText = riskCount ? `其中 ${riskCount} 个需要重点关注的风险预警` : "暂无高风险预警";
  const categoryText = categories.length ? `热点主要集中在${categories.join("、")}方向` : "热点方向暂不明显";
  const trendText = trendNames.length ? `趋势判断覆盖${trendNames.join("、")}` : "暂未形成稳定趋势判断";
  return `${date}${sourceText}，${eventText}，${categoryText}；${trendText}；${riskText}。`;
}

function hotTopicHeadline(topic: HotTopic) {
  const entities = extractEntities(topic.reason);
  const subject = entities.length ? entities.slice(0, 3).join("、") : categoryLabel(topic.category);
  return `${categoryLabel(topic.category)}热点：${subject}相关信号升温`;
}

function hotTopicReason(topic: HotTopic) {
  const metrics = extractRankMetrics(topic.reason);
  const parts = [
    `重要性 ${formatScore(metrics.importance ?? topic.importance_score)}`,
    `风险 ${formatScore(metrics.risk)}`,
    `来源覆盖 ${metrics.coverage ?? topic.evidence_source_item_ids.length} 条`,
  ];
  const entities = extractEntities(topic.reason);
  if (entities.length) {
    parts.push(`涉及 ${entities.slice(0, 4).join("、")}`);
  }
  return `入选逻辑：${parts.join("，")}。该事件在今日结构化信号中排序靠前，适合纳入日报重点观察。`;
}

function deepDiveHeadline(dive: EventDeepDive) {
  const entities = dive.affected_entities.slice(0, 3);
  return entities.length ? `关键事件：${entities.join("、")}相关影响` : "关键事件：需重点关注的 AI 行业信号";
}

function deepDiveSummary(dive: EventDeepDive) {
  const entityText = dive.affected_entities.length ? `影响对象包括 ${dive.affected_entities.slice(0, 4).join("、")}` : "影响对象仍需结合后续来源验证";
  return `背景与影响：该事件被纳入深度总结，是因为它关联 ${dive.evidence_source_item_ids.length} 条证据来源，${entityText}。当前置信度为 ${formatScore(dive.confidence)}，建议结合原始标题和来源内容继续复核。`;
}

function trendSummary(trend: TrendJudgment) {
  return `${trendDirectionLabel(trend.direction)}出现可观察信号，当前信号强度为 ${formatScore(trend.signal_strength)}，置信度为 ${formatScore(trend.confidence)}。`;
}

function trendLogic(trend: TrendJudgment) {
  const count = extractNumberBefore(trend.logic, "event");
  const avgImportance = extractMetric(trend.logic, "avg_importance");
  const maxRisk = extractMetric(trend.logic, "max_risk");
  const parts = [
    count ? `关联 ${count} 个事件` : `关联 ${trend.supporting_event_ids.length} 个事件`,
    `平均重要性 ${formatScore(avgImportance)}`,
    `最高风险 ${formatScore(maxRisk)}`,
    `证据来源 ${trend.evidence_source_item_ids.length} 条`,
  ];
  return `判断依据：${parts.join("，")}。`;
}

function noteHeadline(note: RiskOpportunityNote) {
  return note.type === "risk" ? "需要关注的潜在风险" : "值得跟踪的机会信号";
}

function noteRationale(note: RiskOpportunityNote) {
  const prefix = note.type === "risk" ? "风险依据" : "机会依据";
  return `${prefix}：关联 ${note.related_event_ids.length} 个事件、${note.evidence_source_item_ids.length} 条证据，优先级 ${formatScore(note.priority)}。建议查看对应原始来源确认细节。`;
}

function extractRankMetrics(reason: string) {
  return {
    importance: extractMetric(reason, "importance"),
    risk: extractMetric(reason, "risk"),
    coverage: extractMetric(reason, "source_coverage"),
  };
}

function extractMetric(text: string, key: string) {
  const match = text.match(new RegExp(`${key}=([0-9.]+)`));
  return match ? Number(match[1]) : undefined;
}

function extractNumberBefore(text: string, word: string) {
  const match = text.match(new RegExp(`([0-9]+)\\s+${word}`));
  return match ? Number(match[1]) : undefined;
}

function extractEntities(reason: string) {
  const match = reason.match(/entities=([^.;]+)/);
  if (!match) return [];
  return match[1]
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function statusLabel(status: string | undefined, loading: boolean) {
  if (loading && !status) return "加载中";
  if (status === "ok") return "正常";
  return status ?? "离线";
}

function languageLabel(value?: string) {
  if (value === "zh") return "中文";
  if (value === "en") return "英文";
  return "其他语言";
}

function sourceTypeLabel(value: string) {
  const labels: Record<string, string> = {
    official: "官方来源",
    aggregator: "聚合平台",
    tech_media: "科技媒体",
    social: "社交讨论",
  };
  return labels[value] ?? value;
}

function categoryLabel(value?: string) {
  const labels: Record<string, string> = {
    model: "模型",
    product: "产品",
    research: "研究",
    funding: "融资",
    policy: "政策",
    safety: "安全",
    infrastructure: "基础设施",
    company: "公司动态",
    other: "其他",
  };
  return labels[value ?? "other"] ?? value ?? "其他";
}

function trendDirectionLabel(value: string) {
  const labels: Record<string, string> = {
    technology: "技术方向",
    application: "应用方向",
    policy: "政策方向",
    capital: "资本方向",
  };
  return labels[value] ?? value;
}

function generationLabel(value?: string) {
  const labels: Record<string, string> = {
    rule_based: "规则生成",
    llm: "大模型生成",
    hybrid: "混合生成",
  };
  return labels[value ?? ""] ?? value ?? "未知";
}

function formatScore(value?: number) {
  return typeof value === "number" ? value.toFixed(2).replace(/\.?0+$/, "") : "0";
}

function riskScoreLabel(value: unknown) {
  if (typeof value === "number") return `总风险 ${formatScore(value)}`;
  if (typeof value === "string" && value) return `总风险 ${value}`;
  return "待复核";
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
