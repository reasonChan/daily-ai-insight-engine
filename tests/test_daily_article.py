from __future__ import annotations

from datetime import date

from backend.app.agents.daily_narrative_agent import DailyNarrativeAgent
from backend.app.schemas.analysis import Event, EventEntities, Insight, RiskAssessment
from backend.app.schemas.daily_analysis import (
    DailyAnalysis,
    EventDeepDive,
    HotTopic,
    RiskOpportunityNote,
    TrendJudgment,
)
from backend.app.schemas.source import RawSourceItem


def _source_item(
    item_id: str,
    title: str,
    summary: str,
    source_name: str = "Test Source",
    language: str = "zh",
) -> RawSourceItem:
    return RawSourceItem(
        id=item_id,
        source_type="tech_media",
        medium_type="article",
        source_name=source_name,
        source_url=f"https://example.com/{item_id}",
        title=title,
        summary=summary,
        language=language,
        published_at="2026-06-14T08:00:00Z",
    )


def _event(
    event_id: str,
    title: str,
    summary: str,
    category: str,
    source_ids: list[str],
    companies: list[str],
    topics: list[str],
    importance_score: float,
    risk_score: float,
) -> Event:
    return Event(
        id=event_id,
        title=title,
        summary=summary,
        category=category,
        entities=EventEntities(companies=companies, topics=topics),
        related_source_item_ids=source_ids,
        first_seen_at="2026-06-14T08:00:00Z",
        latest_seen_at="2026-06-14T09:00:00Z",
        importance_score=importance_score,
        risk_score=risk_score,
    )


def _insight(
    insight_id: str,
    event_id: str,
    why_it_matters: str,
    source_ids: list[str],
    opportunities: list[str] | None = None,
    risks: list[str] | None = None,
) -> Insight:
    return Insight(
        id=insight_id,
        event_id=event_id,
        key_points=["智能体应用正在进入工作流", "治理要求影响模型分发"],
        why_it_matters=why_it_matters,
        affected_companies=["OpenAI", "Anthropic"],
        affected_sectors=["enterprise_ai", "ai_safety"],
        opportunities=opportunities or ["企业智能体工作流工具"],
        risks=risks or ["合规和安全评估压力上升"],
        confidence=0.83,
        evidence_source_item_ids=source_ids,
    )


def _risk(risk_id: str, event_id: str, source_ids: list[str], overall_risk: float) -> RiskAssessment:
    return RiskAssessment(
        id=risk_id,
        event_id=event_id,
        public_opinion_risk=0.22,
        policy_risk=overall_risk,
        security_risk=0.42,
        business_risk=0.31,
        technical_risk=0.28,
        overall_risk=overall_risk,
        risk_factors=["模型访问限制", "智能体安全边界"],
        evidence_source_item_ids=source_ids,
    )


def _analysis() -> DailyAnalysis:
    return DailyAnalysis(
        report_date=date(2026, 6, 14),
        hot_topics=[
            HotTopic(
                rank=1,
                title="Agent safety and policy pressure rise",
                category="safety",
                importance_score=0.91,
                hot_score=0.87,
                reason="importance=0.91; source_coverage=2; entities=OpenAI, Anthropic",
                supporting_event_ids=["evt_agent_safety", "evt_policy"],
                evidence_source_item_ids=["src_cn_agent", "src_en_policy"],
            )
        ],
        deep_dives=[
            EventDeepDive(
                event_id="evt_agent_safety",
                title="Agent systems move into enterprise workflows",
                background="智能体系统从演示阶段进入企业工作流，需要更强的安全评估。",
                impact_analysis="这会影响模型供应商、企业采购和第三方安全工具的优先级。",
                affected_entities=["OpenAI", "Anthropic"],
                evidence=["中文科技媒体和英文政策来源都提到智能体治理"],
                evidence_source_item_ids=["src_cn_agent", "src_en_policy"],
                confidence=0.82,
            )
        ],
        trend_judgments=[
            TrendJudgment(
                direction="application",
                judgment="企业智能体应用继续升温",
                logic="产品事件和安全事件同时出现，说明应用落地正在和治理能力绑定。",
                supporting_event_ids=["evt_agent_product", "evt_agent_safety"],
                evidence_source_item_ids=["src_cn_agent", "src_cn_product"],
                signal_strength=0.84,
                confidence=0.8,
            ),
            TrendJudgment(
                direction="policy",
                judgment="模型治理约束增强",
                logic="政策信号和风险评估共同指向更强的合规要求。",
                supporting_event_ids=["evt_policy"],
                evidence_source_item_ids=["src_en_policy"],
                signal_strength=0.78,
                confidence=0.76,
            ),
        ],
        risk_opportunity_notes=[
            RiskOpportunityNote(
                type="risk",
                title="智能体安全和模型分发限制需要持续观察",
                rationale="高风险事件集中在安全和政策方向，可能影响企业采购节奏。",
                related_event_ids=["evt_agent_safety", "evt_policy"],
                evidence_source_item_ids=["src_cn_agent", "src_en_policy"],
                priority=0.82,
            )
        ],
        evidence_source_item_ids=["src_cn_agent", "src_cn_product", "src_en_policy"],
    )


def _article_inputs():
    source_items = [
        _source_item(
            "src_cn_agent",
            "智能体安全成为企业采用 AI 的核心议题",
            "多家 AI 公司强调智能体协作场景下的安全评估和权限控制。",
            source_name="机器之心",
            language="zh",
        ),
        _source_item(
            "src_cn_product",
            "企业 AI 工作流工具加速落地",
            "新的 AI 产品把模型能力嵌入客服、研发和办公流程。",
            source_name="量子位",
            language="zh",
        ),
        _source_item(
            "src_en_policy",
            "Regulators tighten expectations for frontier AI deployment",
            "Policy makers are asking model providers for stronger safeguards before broad deployment.",
            source_name="Tech Policy Daily",
            language="en",
        ),
    ]
    events = [
        _event(
            "evt_agent_safety",
            "Agent safety becomes a board-level issue",
            "智能体从单点工具走向多步骤协作后，企业开始重视权限、审计和安全边界。",
            "safety",
            ["src_cn_agent"],
            ["OpenAI", "Anthropic"],
            ["智能体", "AI安全"],
            0.91,
            0.46,
        ),
        _event(
            "evt_agent_product",
            "Enterprise AI workflow tools launch",
            "AI 产品正在从聊天入口转向具体业务流程，企业更关注可落地的工作流改造。",
            "product",
            ["src_cn_product"],
            ["OpenAI"],
            ["企业应用", "工作流"],
            0.84,
            0.22,
        ),
        _event(
            "evt_policy",
            "Frontier AI policy pressure increases",
            "监管机构要求前沿模型部署具备更清晰的安全评估、访问控制和责任边界。",
            "policy",
            ["src_en_policy"],
            ["Anthropic"],
            ["政策治理", "模型分发"],
            0.79,
            0.51,
        ),
    ]
    insights = [
        _insight(
            "ins_agent_safety",
            "evt_agent_safety",
            "智能体能力扩张带来的不是单一功能升级，而是企业治理、权限控制和安全评估体系的同步升级。",
            ["src_cn_agent"],
            risks=["智能体行为不可预测", "权限边界不清晰"],
        ),
        _insight(
            "ins_agent_product",
            "evt_agent_product",
            "应用层竞争会从模型参数转向能否嵌入真实业务流程并产生稳定 ROI。",
            ["src_cn_product"],
        ),
        _insight(
            "ins_policy",
            "evt_policy",
            "政策约束会改变模型分发、API 访问和跨区域企业采购的节奏。",
            ["src_en_policy"],
            risks=["模型出海受限", "合规成本上升"],
        ),
    ]
    risks = [
        _risk("risk_agent_safety", "evt_agent_safety", ["src_cn_agent"], 0.46),
        _risk("risk_agent_product", "evt_agent_product", ["src_cn_product"], 0.22),
        _risk("risk_policy", "evt_policy", ["src_en_policy"], 0.51),
    ]
    return events, insights, risks, source_items, _analysis()


def test_daily_narrative_agent_outputs_article_contract():
    events, insights, risks, source_items, daily_analysis = _article_inputs()

    article = DailyNarrativeAgent().write(
        report_date=date(2026, 6, 14),
        events=events,
        insights=insights,
        risks=risks,
        source_items=source_items,
        daily_analysis=daily_analysis,
    )

    assert article.title
    assert article.lead
    assert article.body_sections
    assert article.trend_outlook
    assert article.risk_opportunity
    assert article.generated_by == "rule_based"
    assert all(section.heading and section.content for section in article.body_sections)


def test_daily_narrative_article_is_chinese_dominant_without_machine_fields():
    events, insights, risks, source_items, daily_analysis = _article_inputs()

    article = DailyNarrativeAgent().write(
        report_date=date(2026, 6, 14),
        events=events,
        insights=insights,
        risks=risks,
        source_items=source_items,
        daily_analysis=daily_analysis,
    )

    article_text = "\n".join(
        [
            article.title,
            article.subtitle or "",
            article.lead,
            *[section.heading for section in article.body_sections],
            *[section.content for section in article.body_sections],
            article.trend_outlook,
            article.risk_opportunity,
        ]
    )
    chinese_chars = sum("\u4e00" <= char <= "\u9fff" for char in article_text)
    ascii_letters = sum(char.isascii() and char.isalpha() for char in article_text)

    assert chinese_chars > ascii_letters
    assert chinese_chars >= 80
    assert "importance=" not in article_text
    assert "source_coverage=" not in article_text
    assert "entities=" not in article_text


def test_daily_narrative_article_keeps_traceable_evidence_source_ids():
    events, insights, risks, source_items, daily_analysis = _article_inputs()
    source_ids = {item.id for item in source_items}

    article = DailyNarrativeAgent().write(
        report_date=date(2026, 6, 14),
        events=events,
        insights=insights,
        risks=risks,
        source_items=source_items,
        daily_analysis=daily_analysis,
    )

    assert article.evidence_source_item_ids
    assert set(article.evidence_source_item_ids).issubset(source_ids)
    assert any(section.evidence_source_item_ids for section in article.body_sections)
    for section in article.body_sections:
        assert section.related_event_ids
        assert section.evidence_source_item_ids
        assert set(section.evidence_source_item_ids).issubset(source_ids)
