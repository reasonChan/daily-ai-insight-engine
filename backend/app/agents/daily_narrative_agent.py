from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime, timezone
from typing import Iterable

from backend.app.schemas.analysis import Event, Insight, RiskAssessment
from backend.app.schemas.daily_analysis import DailyAnalysis, EventDeepDive, HotTopic, TrendJudgment
from backend.app.schemas.daily_article import ArticleSection, DailyArticle
from backend.app.schemas.source import RawSourceItem


_CATEGORY_LABELS = {
    "model": "模型能力",
    "product": "产品应用",
    "research": "研究进展",
    "funding": "资本动态",
    "policy": "政策监管",
    "safety": "安全治理",
    "infrastructure": "基础设施",
    "company": "公司战略",
    "other": "综合信号",
}

_TREND_LABELS = {
    "technology": "技术",
    "application": "应用",
    "policy": "政策",
    "capital": "资本",
}

_MACHINE_FIELD_PATTERN = re.compile(
    r"\b(?:importance|source_coverage|entities|avg_importance|max_risk|categories|top_entities|risk)\s*=",
    flags=re.IGNORECASE,
)


class DailyNarrativeAgent:
    """Writes a Chinese narrative article from structured daily analysis signals."""

    def write(
        self,
        report_date: date,
        events: list[Event],
        insights: list[Insight],
        risks: list[RiskAssessment],
        source_items: list[RawSourceItem],
        daily_analysis: DailyAnalysis,
    ) -> DailyArticle:
        source_by_id = {item.id: item for item in source_items if item.id}
        event_by_id = {event.id: event for event in events}
        insight_by_event_id = {insight.event_id: insight for insight in insights}
        risk_by_event_id = {risk.event_id: risk for risk in risks}

        hot_topics = sorted(daily_analysis.hot_topics, key=lambda item: item.rank)[:5]
        deep_dives = daily_analysis.deep_dives[:3]
        trend_judgments = sorted(
            daily_analysis.trend_judgments,
            key=lambda item: item.signal_strength,
            reverse=True,
        )
        risk_notes = sorted(
            daily_analysis.risk_opportunity_notes,
            key=lambda item: item.priority,
            reverse=True,
        )

        lead_categories = _top_categories(hot_topics, events)
        top_entities = _top_entities(events, hot_topics)
        title = _build_title(lead_categories, trend_judgments)
        subtitle = _build_subtitle(report_date, len(source_items), len(events), lead_categories)
        lead = _sanitize(
            _build_lead(
                report_date=report_date,
                hot_topics=hot_topics,
                trend_judgments=trend_judgments,
                top_entities=top_entities,
                source_items=source_items,
            )
        )

        body_sections = [
            section
            for section in (
                _mainline_section(hot_topics, event_by_id, risk_by_event_id, source_by_id),
                _deep_dive_section(deep_dives, event_by_id, insight_by_event_id, risk_by_event_id, source_by_id),
                _trend_section(trend_judgments, event_by_id),
            )
            if section is not None
        ]

        risk_opportunity = _sanitize(_risk_opportunity_text(risk_notes, risk_by_event_id, event_by_id))
        evidence_ids = _unique(
            [
                *daily_analysis.evidence_source_item_ids,
                *(source_id for section in body_sections for source_id in section.evidence_source_item_ids),
                *(source_id for note in risk_notes[:4] for source_id in note.evidence_source_item_ids),
            ]
        )

        return DailyArticle(
            report_date=report_date,
            title=_sanitize(title),
            subtitle=_sanitize(subtitle),
            lead=lead,
            body_sections=body_sections,
            trend_outlook=_sanitize(_trend_outlook_text(trend_judgments, events)),
            risk_opportunity=risk_opportunity,
            evidence_source_item_ids=evidence_ids,
            generated_by="rule_based",
            generated_at=datetime.now(timezone.utc),
        )


def _build_title(categories: list[str], trends: list[TrendJudgment]) -> str:
    if categories:
        primary = "、".join(categories[:2])
    elif trends:
        primary = "、".join(_TREND_LABELS.get(item.direction, item.direction) for item in trends[:2])
    else:
        primary = "AI 行业信号"
    return f"{primary}成为今日 AI 领域主线"


def _build_subtitle(report_date: date, source_count: int, event_count: int, categories: list[str]) -> str:
    category_text = "、".join(categories[:3]) if categories else "综合动态"
    return f"{report_date.isoformat()} 基于 {source_count} 条来源与 {event_count} 个结构化事件生成，重点观察{category_text}。"


def _build_lead(
    report_date: date,
    hot_topics: list[HotTopic],
    trend_judgments: list[TrendJudgment],
    top_entities: list[str],
    source_items: list[RawSourceItem],
) -> str:
    zh_count = sum(1 for item in source_items if item.language == "zh")
    en_count = sum(1 for item in source_items if item.language == "en")
    topic_text = _topic_phrase(hot_topics)
    trend_text = _trend_phrase(trend_judgments)
    entity_text = f"，其中 {'、'.join(top_entities[:4])} 等主体反复出现" if top_entities else ""
    return (
        f"{report_date.isoformat()} 的 AI 信息流显示，今天的核心并不是单点新闻发布，而是{topic_text}正在形成共同主线。"
        f"从 {len(source_items)} 条来源看，中文来源 {zh_count} 条、英文来源 {en_count} 条，信号主要落在{trend_text}{entity_text}。"
        "这意味着行业关注点正在从“发生了什么”转向“这些变化会如何影响模型能力、应用落地与治理边界”。"
    )


def _mainline_section(
    hot_topics: list[HotTopic],
    event_by_id: dict[str, Event],
    risk_by_event_id: dict[str, RiskAssessment],
    source_by_id: dict[str, RawSourceItem],
) -> ArticleSection | None:
    if not hot_topics:
        return None
    related_event_ids = _unique(event_id for topic in hot_topics[:4] for event_id in topic.supporting_event_ids)
    evidence_ids = _unique(source_id for topic in hot_topics[:4] for source_id in topic.evidence_source_item_ids)
    events = [event_by_id[event_id] for event_id in related_event_ids if event_id in event_by_id]
    categories = _top_categories(hot_topics, events)
    strongest = hot_topics[0]
    evidence_names = _source_names(evidence_ids, source_by_id)
    avg_importance = _avg(event.importance_score for event in events)
    max_risk = max((risk_by_event_id.get(event.id).overall_risk if risk_by_event_id.get(event.id) else event.risk_score for event in events), default=0)

    content = (
        f"今日最强的行业信号集中在{_join_cn(categories) or '综合 AI 动态'}。"
        f"排名靠前的事件围绕“{_story_label(strongest.title, events[0] if events else None)}”展开，并与后续多个事件共同指向同一条主线：AI 产业正在把能力扩张、产品分发和治理约束放在同一个框架内权衡。"
        f"从结构化评分看，相关事件的平均重要性约为 {_score_label(avg_importance)}，最高风险处于 {_score_label(max_risk)} 区间，说明它们不只是信息热度较高，也可能影响企业采用、监管讨论或技术路线选择。"
        f"{' 主要证据来自' + _join_cn(evidence_names[:3]) + '等来源。' if evidence_names else ''}"
    )
    return ArticleSection(
        heading="今日主线",
        content=_sanitize(content),
        related_event_ids=related_event_ids,
        evidence_source_item_ids=evidence_ids,
    )


def _deep_dive_section(
    deep_dives: list[EventDeepDive],
    event_by_id: dict[str, Event],
    insight_by_event_id: dict[str, Insight],
    risk_by_event_id: dict[str, RiskAssessment],
    source_by_id: dict[str, RawSourceItem],
) -> ArticleSection | None:
    if not deep_dives:
        return None
    paragraphs: list[str] = []
    related_event_ids: list[str] = []
    evidence_ids: list[str] = []

    for index, dive in enumerate(deep_dives[:3], start=1):
        event = event_by_id.get(dive.event_id)
        insight = insight_by_event_id.get(dive.event_id)
        risk = risk_by_event_id.get(dive.event_id)
        related_event_ids.append(dive.event_id)
        evidence_ids.extend(dive.evidence_source_item_ids)
        category = _CATEGORY_LABELS.get(event.category if event else "other", "综合信号")
        entity_text = _join_cn(dive.affected_entities[:4]) or "相关企业与开发者生态"
        impact = insight.why_it_matters if insight else dive.impact_analysis
        impact = _clean_source_sentence(impact)
        risk_text = ""
        if risk and risk.overall_risk >= 0.35:
            risk_text = f"同时，风险信号处于 {_score_label(risk.overall_risk)} 水平，主要需要关注{_join_cn(risk.risk_factors[:2]) or '政策、技术或商业不确定性'}。"
        source_names = _source_names(dive.evidence_source_item_ids, source_by_id)
        evidence_text = f"这一判断由{_join_cn(source_names[:2])}等来源支撑。" if source_names else ""
        paragraphs.append(
            f"{index}. 在{category}方向，“{_story_label(dive.title, event)}”的意义不在于单条消息本身，而在于它影响了{entity_text}对下一阶段投入的判断。"
            f"{impact} {risk_text}{evidence_text}"
        )

    return ArticleSection(
        heading="关键事件深度分析",
        content=_sanitize(" ".join(paragraphs)),
        related_event_ids=_unique(related_event_ids),
        evidence_source_item_ids=_unique(evidence_ids),
    )


def _trend_section(trends: list[TrendJudgment], event_by_id: dict[str, Event]) -> ArticleSection | None:
    if not trends:
        return None
    related_event_ids = _unique(event_id for trend in trends[:4] for event_id in trend.supporting_event_ids)
    evidence_ids = _unique(source_id for trend in trends[:4] for source_id in trend.evidence_source_item_ids)
    clauses: list[str] = []
    for trend in trends[:4]:
        label = _TREND_LABELS.get(trend.direction, trend.direction)
        events = [event_by_id[event_id] for event_id in trend.supporting_event_ids if event_id in event_by_id]
        categories = [_CATEGORY_LABELS.get(event.category, event.category) for event in events]
        strength = _score_label(trend.signal_strength)
        clauses.append(
            f"{label}方向的信号强度为{strength}，主要由{_join_cn(_unique(categories)[:3]) or '多类事件'}支撑，说明该方向已经具备连续观察价值"
        )
    return ArticleSection(
        heading="趋势判断",
        content=_sanitize("；".join(clauses) + "。"),
        related_event_ids=related_event_ids,
        evidence_source_item_ids=evidence_ids,
    )


def _trend_outlook_text(trends: list[TrendJudgment], events: list[Event]) -> str:
    if not trends:
        return "短期看，AI 行业仍需要继续观察模型能力、产品落地、政策监管和资本投入之间的互动。"
    top = trends[0]
    label = _TREND_LABELS.get(top.direction, top.direction)
    event_count = len(top.supporting_event_ids)
    high_risk_count = sum(1 for event in events if event.risk_score >= 0.4)
    return (
        f"短期看，{label}方向是最值得跟踪的变量，因为它获得了 {event_count} 个结构化事件支撑，信号强度处于{_score_label(top.signal_strength)}区间。"
        f"如果后续相关事件继续增加，行业叙事可能从单点创新转向更系统的生态竞争。"
        f"{' 同时，高风险事件数量不低，治理与合规会成为落地速度的重要约束。' if high_risk_count else ' 当前风险压力相对可控，但仍需观察政策与安全讨论是否升温。'}"
    )


def _risk_opportunity_text(notes, risk_by_event_id: dict[str, RiskAssessment], event_by_id: dict[str, Event]) -> str:
    if not notes:
        return "当前日报未识别出显著风险预警，但仍建议持续关注模型安全、内容合规和企业采购节奏。"
    risk_notes = [note for note in notes if note.type == "risk"]
    opportunity_notes = [note for note in notes if note.type == "opportunity"]
    parts: list[str] = []
    if risk_notes:
        related_titles = [_story_label(event_by_id[event_id].title, event_by_id[event_id]) for note in risk_notes[:2] for event_id in note.related_event_ids if event_id in event_by_id]
        parts.append(
            f"风险侧需要优先关注{_join_cn(related_titles[:2]) or '高优先级事件'}，这些信号可能影响模型访问、企业部署和监管沟通节奏。"
        )
    if opportunity_notes:
        related_titles = [_story_label(event_by_id[event_id].title, event_by_id[event_id]) for note in opportunity_notes[:2] for event_id in note.related_event_ids if event_id in event_by_id]
        parts.append(
            f"机会侧则集中在{_join_cn(related_titles[:2]) or '高重要性应用场景'}，更适合寻找能把 AI 能力嵌入具体工作流的产品与服务。"
        )
    if not parts:
        max_risk = max((risk.overall_risk for risk in risk_by_event_id.values()), default=0)
        parts.append(f"整体风险处于{_score_label(max_risk)}区间，机会主要来自高重要性事件的后续商业化扩散。")
    return "".join(parts)


def _top_categories(hot_topics: list[HotTopic], events: list[Event]) -> list[str]:
    counts: Counter[str] = Counter()
    counts.update(_CATEGORY_LABELS.get(topic.category, topic.category) for topic in hot_topics)
    counts.update(_CATEGORY_LABELS.get(event.category, event.category) for event in events)
    return [category for category, _ in counts.most_common(3)]


def _top_entities(events: list[Event], hot_topics: list[HotTopic]) -> list[str]:
    counts: Counter[str] = Counter()
    for event in events:
        counts.update(event.entities.companies)
        counts.update(event.entities.products)
        counts.update(event.entities.models)
        counts.update(event.entities.topics)
    for topic in hot_topics:
        for token in re.findall(r"[A-Z][A-Za-z0-9.-]{2,}", topic.title):
            counts[token] += 1
    return [entity for entity, _ in counts.most_common(6)]


def _topic_phrase(hot_topics: list[HotTopic]) -> str:
    if not hot_topics:
        return "多条分散信号"
    categories = _top_categories(hot_topics, [])
    return _join_cn(categories) or "AI 行业多个方向"


def _trend_phrase(trends: list[TrendJudgment]) -> str:
    if not trends:
        return "技术、应用、政策与资本的交叉地带"
    return _join_cn([_TREND_LABELS.get(trend.direction, trend.direction) for trend in trends[:3]])


def _source_names(source_ids: list[str], source_by_id: dict[str, RawSourceItem]) -> list[str]:
    return _unique(source_by_id[source_id].source_name for source_id in source_ids if source_id in source_by_id)


def _clean_source_sentence(text: str) -> str:
    cleaned = _MACHINE_FIELD_PATTERN.sub("", text or "")
    cleaned = re.sub(r"Supporting coverage includes:.*?(?:\.|$)", "", cleaned)
    cleaned = re.sub(r"Risk signal is elevated at [0-9.]+:?", "风险信号有所抬升：", cleaned)
    cleaned = cleaned.strip()
    if not cleaned or _is_mostly_english(cleaned):
        return "该事件可能改变相关主体对产品节奏、技术投入或治理要求的判断。"
    return cleaned


def _sanitize(text: str | None) -> str:
    if not text:
        return ""
    cleaned = _MACHINE_FIELD_PATTERN.sub("", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _story_label(title: str, event: Event | None) -> str:
    if title and not _is_mostly_english(title):
        return title
    if event is None:
        return _CATEGORY_LABELS.get("other", "AI 行业事件")
    entities = _unique([*event.entities.companies, *event.entities.products, *event.entities.models, *event.entities.topics])
    category = _CATEGORY_LABELS.get(event.category, "AI 行业")
    if entities:
        return f"{_join_cn(entities[:2])}相关{category}事件"
    return f"{category}方向的重要事件"


def _is_mostly_english(text: str) -> bool:
    letters = re.findall(r"[A-Za-z]", text)
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    return len(letters) >= 12 and len(letters) > len(cjk) * 2


def _score_label(value: float | None) -> str:
    if value is None:
        return "中等"
    if value >= 0.75:
        return "高"
    if value >= 0.45:
        return "中高"
    if value >= 0.25:
        return "中等"
    return "偏低"


def _avg(values: Iterable[float]) -> float:
    numbers = list(values)
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)


def _join_cn(values: list[str]) -> str:
    filtered = [value for value in values if value]
    if not filtered:
        return ""
    if len(filtered) == 1:
        return filtered[0]
    return "、".join(filtered)


def _unique(values) -> list:
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
