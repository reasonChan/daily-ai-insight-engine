from __future__ import annotations

from backend.app.collectors.base import SourceCollector, failure_result
from backend.app.core.config import SourceConfig
from backend.app.core.http import HttpClient
from backend.app.schemas.source import CollectorResult, RawSourceItem, utc_now


class GitHubReleaseCollector(SourceCollector):
    def __init__(self, http_client: HttpClient | None = None):
        self.http_client = http_client or HttpClient()

    def collect(self, source: SourceConfig, limit: int) -> CollectorResult:
        repo = source.repo or source.query
        if not repo and source.url and "github.com" in source.url:
            parts = source.url.rstrip("/").split("/")
            if len(parts) >= 5:
                repo = "/".join(parts[-2:])
        if not repo:
            return failure_result(source, "GitHub release source requires repo/query/url")

        url = f"https://api.github.com/repos/{repo}/releases?per_page={limit}"
        try:
            payload = self.http_client.get_json(url)
            if not isinstance(payload, list):
                return failure_result(source, "GitHub releases API returned non-list payload")
            items = []
            for release in payload[:limit]:
                title = release.get("name") or release.get("tag_name") or repo
                body = release.get("body") or title
                items.append(
                    RawSourceItem(
                        source_type="official",
                        medium_type="release",
                        source_name=source.name,
                        source_url=release.get("html_url") or f"https://github.com/{repo}/releases",
                        title=title,
                        summary=body[:700],
                        content=body,
                        language=source.language if source.language in {"zh", "en"} else "en",
                        published_at=release.get("published_at") or release.get("created_at"),
                        collected_at=utc_now(),
                        tags=["github_release", repo],
                        raw_payload=release,
                    )
                )
            return CollectorResult(items=items)
        except Exception as exc:  # noqa: BLE001
            return failure_result(source, str(exc))

