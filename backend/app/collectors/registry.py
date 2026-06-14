from __future__ import annotations

from backend.app.collectors.base import SourceCollector
from backend.app.collectors import arxiv, github_releases, hacker_news, reddit, rss
from backend.app.core.config import SourceConfig
from backend.app.schemas.source import CollectionFailure, CollectorResult, RawSourceItem


class FunctionCollector(SourceCollector):
    def __init__(self, collect_func):
        self.collect_func = collect_func

    def collect(self, source: SourceConfig, limit: int) -> CollectorResult:
        payload = self.collect_func(source.model_dump(), limit=limit)
        if not payload.get("ok"):
            error = payload.get("error") or {}
            return CollectorResult(
                failures=[
                    CollectionFailure(
                        source_name=payload.get("source_name") or source.name,
                        reason=error.get("message") or str(error) or "collector failed",
                    )
                ]
            )

        items = []
        failures = []
        for raw in payload.get("items", []):
            try:
                items.append(RawSourceItem.model_validate(raw))
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    CollectionFailure(
                        source_name=source.name,
                        reason=f"invalid collector item: {exc}",
                    )
                )
        return CollectorResult(items=items, failures=failures)


class CollectorRegistry:
    def __init__(self):
        self._rss = FunctionCollector(rss.collect)
        self._arxiv = FunctionCollector(arxiv.collect)
        self._hn = FunctionCollector(hacker_news.collect)
        self._reddit = FunctionCollector(reddit.collect)
        self._github = FunctionCollector(github_releases.collect)

    def resolve(self, source: SourceConfig) -> SourceCollector:
        name = source.name.lower()
        method = source.method.lower()
        if method == "rss":
            return self._rss
        if "arxiv" in name:
            return self._arxiv
        if "hacker news" in name or "hn" == name:
            return self._hn
        if "reddit" in name:
            return self._reddit
        if "github" in name or source.repo:
            return self._github
        if method == "json" and source.url and "reddit.com" in source.url:
            return self._reddit
        if method == "api":
            if source.query and "cat:" in source.query:
                return self._arxiv
            return self._hn
        return self._rss
