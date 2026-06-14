from __future__ import annotations

from abc import ABC, abstractmethod

from backend.app.core.config import SourceConfig
from backend.app.schemas.source import CollectorResult


class SourceCollector(ABC):
    @abstractmethod
    def collect(self, source: SourceConfig, limit: int) -> CollectorResult:
        raise NotImplementedError


def failure_result(source: SourceConfig, reason: str) -> CollectorResult:
    from backend.app.schemas.source import CollectionFailure

    return CollectorResult(
        failures=[CollectionFailure(source_name=source.name, reason=reason)]
    )

