from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence

try:
    import yaml
except ImportError:  # pragma: no cover - only used in very small local environments.
    yaml = None

from backend.app.schemas import CollectionSummary, FailedSource, RawSourceItem, SourceConfig
from backend.app.services import AIRelevanceFilter, SourceDeduplicator


class Collector(Protocol):
    def collect(self, config: SourceConfig) -> Sequence[RawSourceItem]:
        ...


CollectorFactory = Callable[[], Collector]


class EmptyCollector:
    """Placeholder adapter until concrete collectors are registered."""

    def collect(self, config: SourceConfig) -> Sequence[RawSourceItem]:
        return []


class CollectorRegistry:
    def __init__(self) -> None:
        self._factories: Dict[str, CollectorFactory] = {}
        self._fallback_factory: CollectorFactory = EmptyCollector

    def register(self, key: str, factory: CollectorFactory) -> None:
        self._factories[self._normalize_key(key)] = factory

    def get(self, config: SourceConfig) -> Collector:
        keys = (
            f"{config.source_type}:{config.method}",
            str(config.method),
            str(config.source_type),
        )
        for key in keys:
            factory = self._factories.get(self._normalize_key(key))
            if factory:
                return factory()
        return self._fallback_factory()

    @staticmethod
    def _normalize_key(key: str) -> str:
        return key.strip().lower()


class CollectionOrchestrator:
    def __init__(
        self,
        registry: Optional[CollectorRegistry] = None,
        relevance_filter: Optional[AIRelevanceFilter] = None,
        deduplicator: Optional[SourceDeduplicator] = None,
    ) -> None:
        self.registry = registry or CollectorRegistry()
        self.relevance_filter = relevance_filter or AIRelevanceFilter()
        self.deduplicator = deduplicator or SourceDeduplicator()

    def run(self, config_path: Path) -> CollectionSummary:
        started_at = datetime.now(timezone.utc)
        source_configs = self.load_source_configs(config_path)
        candidates: List[RawSourceItem] = []
        failed_sources: List[FailedSource] = []

        for source_config in source_configs:
            if not source_config.enabled:
                continue
            collector = self.registry.get(source_config)
            try:
                collected = collector.collect(source_config)
                candidates.extend(collected)
            except Exception as exc:  # collector boundary: report and continue.
                failed_sources.append(
                    FailedSource(source_name=source_config.name, reason=str(exc))
                )

        relevance_results = self.relevance_filter.evaluate_many(candidates)
        ai_related_items = [
            item for item in candidates if relevance_results[item.id].is_ai_related
        ]
        deduplication_result = self.deduplicator.deduplicate(ai_related_items)
        finished_at = datetime.now(timezone.utc)

        return CollectionSummary(
            started_at=started_at,
            finished_at=finished_at,
            candidate_count=len(candidates),
            ai_related_count=len(ai_related_items),
            deduplicated_count=len(deduplication_result.unique_items),
            stored_count=len(deduplication_result.unique_items),
            source_breakdown=self._source_breakdown(deduplication_result.unique_items),
            failed_sources=failed_sources,
        )

    @staticmethod
    def load_source_configs(config_path: Path) -> List[SourceConfig]:
        payload = _load_yaml(config_path)
        sources = payload.get("sources", [])
        if not isinstance(sources, list):
            raise ValueError("sources.yaml must contain a list under 'sources'")
        return [SourceConfig(**source) for source in sources]

    @staticmethod
    def _source_breakdown(items: Iterable[RawSourceItem]) -> Dict[str, int]:
        breakdown: Dict[str, int] = {}
        for item in items:
            key = str(item.source_type.value if hasattr(item.source_type, "value") else item.source_type)
            breakdown[key] = breakdown.get(key, 0) + 1
        return breakdown


def _load_yaml(config_path: Path) -> Mapping[str, Any]:
    with config_path.open("r", encoding="utf-8") as handle:
        if yaml is not None:
            payload = yaml.safe_load(handle) or {}
        else:
            payload = _load_sources_yaml_fallback(handle.read())
    if not isinstance(payload, Mapping):
        raise ValueError("sources.yaml must contain a mapping")
    return payload


def _load_sources_yaml_fallback(text: str) -> Mapping[str, Any]:
    sources: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip() or line.strip() == "sources:":
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            if current:
                sources.append(current)
            current = {}
            stripped = stripped[2:].strip()
            if stripped:
                key, value = _parse_yaml_pair(stripped)
                current[key] = value
            continue
        if current is not None and ":" in stripped:
            key, value = _parse_yaml_pair(stripped)
            current[key] = value

    if current:
        sources.append(current)
    return {"sources": sources}


def _parse_yaml_pair(text: str) -> tuple[str, Any]:
    key, value = text.split(":", 1)
    value = value.strip()
    if value.lower() == "true":
        parsed_value: Any = True
    elif value.lower() == "false":
        parsed_value = False
    elif value in {"", "null", "None"}:
        parsed_value = None
    else:
        parsed_value = value.strip("\"'")
    return key.strip(), parsed_value


def _model_to_dict(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return json.loads(model.json())


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run source collection orchestration.")
    parser.add_argument(
        "--config",
        default=str(Path("configs") / "sources.yaml"),
        help="Path to sources.yaml",
    )
    args = parser.parse_args(argv)

    summary = CollectionOrchestrator().run(Path(args.config))
    print(json.dumps(_model_to_dict(summary), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
