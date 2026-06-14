from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Set

from backend.app.schemas import RawSourceItem, RelevanceResult


@dataclass(frozen=True)
class KeywordRule:
    keyword: str
    topic: str
    weight: float = 1.0


DEFAULT_KEYWORD_RULES: Sequence[KeywordRule] = (
    KeywordRule("AI", "ai"),
    KeywordRule("artificial intelligence", "ai"),
    KeywordRule("generative AI", "generative_ai", 1.2),
    KeywordRule("LLM", "llm", 1.2),
    KeywordRule("large language model", "llm", 1.2),
    KeywordRule("agent", "agents"),
    KeywordRule("agents", "agents"),
    KeywordRule("OpenAI", "company"),
    KeywordRule("Anthropic", "company"),
    KeywordRule("Claude", "model"),
    KeywordRule("Gemini", "model"),
    KeywordRule("DeepMind", "company"),
    KeywordRule("multimodal", "multimodal"),
    KeywordRule("alignment", "safety"),
    KeywordRule("\u4eba\u5de5\u667a\u80fd", "ai"),
    KeywordRule("\u751f\u6210\u5f0fAI", "generative_ai", 1.2),
    KeywordRule("\u751f\u6210\u5f0f AI", "generative_ai", 1.2),
    KeywordRule("\u5927\u6a21\u578b", "llm", 1.2),
    KeywordRule("\u5927\u8bed\u8a00\u6a21\u578b", "llm", 1.2),
    KeywordRule("\u667a\u80fd\u4f53", "agents"),
    KeywordRule("\u591a\u6a21\u6001", "multimodal"),
    KeywordRule("\u7b97\u529b", "compute"),
    KeywordRule("\u82af\u7247", "compute"),
    KeywordRule("\u673a\u5668\u5b66\u4e60", "machine_learning"),
    KeywordRule("\u6df1\u5ea6\u5b66\u4e60", "machine_learning"),
)


class AIRelevanceFilter:
    def __init__(self, keyword_rules: Iterable[KeywordRule] = DEFAULT_KEYWORD_RULES) -> None:
        self.keyword_rules = tuple(keyword_rules)

    def evaluate(self, item: RawSourceItem) -> RelevanceResult:
        text = self._combined_text(item)
        matched_keywords: List[str] = []
        topics: Set[str] = set()
        score_units = 0.0

        for rule in self.keyword_rules:
            if self._contains_keyword(text, rule.keyword):
                matched_keywords.append(rule.keyword)
                topics.add(rule.topic)
                score_units += rule.weight

        relevance_score = min(score_units / 6.0, 1.0)
        return RelevanceResult(
            is_ai_related=bool(matched_keywords),
            relevance_score=round(relevance_score, 4),
            matched_keywords=matched_keywords,
            topics=sorted(topics),
        )

    def filter(self, items: Iterable[RawSourceItem]) -> List[RawSourceItem]:
        return [item for item in items if self.evaluate(item).is_ai_related]

    def evaluate_many(self, items: Iterable[RawSourceItem]) -> Dict[str, RelevanceResult]:
        return {item.id: self.evaluate(item) for item in items}

    @staticmethod
    def _combined_text(item: RawSourceItem) -> str:
        parts = [item.title, item.summary or "", item.content or "", " ".join(item.tags)]
        return "\n".join(parts)

    @staticmethod
    def _contains_keyword(text: str, keyword: str) -> bool:
        if re.search(r"[\u4e00-\u9fff]", keyword):
            return keyword in text
        pattern = r"(?<![A-Za-z0-9])" + re.escape(keyword) + r"(?![A-Za-z0-9])"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None


def evaluate_ai_relevance(item: RawSourceItem) -> RelevanceResult:
    return AIRelevanceFilter().evaluate(item)


def evaluate_ai_relevance(item: RawSourceItem) -> RelevanceResult:
    return AIRelevanceFilter().evaluate(item)
