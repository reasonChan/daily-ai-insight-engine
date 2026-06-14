"""GitHub Releases collector."""

from __future__ import annotations

import re
from typing import Any

from backend.app.collectors.base import SourceCollector
from backend.app.collectors.schema import (
    make_collection_result,
    make_error,
    make_raw_source_item,
    source_config_to_dict,
    to_collector_result,
)
from backend.app.collectors.utils import clean_text, parse_datetime, source_value
from backend.app.core.http import fetch_json


GITHUB_API_BASE = "https://api.github.com/repos"


def _repo_from_source(source: dict[str, Any]) -> str | None:
    if source.get("repo"):
        return str(source["repo"]).strip("/")
    url = str(source.get("url") or "")
    match = re.search(r"github\.com/([^/\s]+/[^/\s]+)", url)
    if match:
        return match.group(1).removesuffix(".git").strip("/")
    return None


def _release_signals(name: str, tag: str, body: str) -> dict[str, bool]:
    text = f"{name} {tag} {body}".lower()
    return {
        "is_major_release": bool(re.search(r"\bv?\d+\.0(?:\.0)?\b", tag.lower())),
        "contains_breaking_change": "breaking" in text or "breaking change" in text,
        "contains_security_fix": "security" in text or "cve-" in text,
    }


def collect(source: dict[str, Any], limit: int = 20) -> dict[str, Any]:
    repo = _repo_from_source(source)
    source_name = source_value(source, "name", f"GitHub Releases {repo or ''}".strip())
    if not repo:
        return make_error(source_name, "invalid_source_config", "GitHub release source requires repo or GitHub URL")

    result = fetch_json(f"{GITHUB_API_BASE}/{repo}/releases", params={"per_page": limit})
    if not result.get("ok"):
        error = result.get("error") or {"type": "unknown_error", "message": "GitHub releases fetch failed"}
        return make_error(source_name, error.get("type", "http_error"), error.get("message", ""), url=result.get("url"))

    releases = result.get("json") or []
    if not isinstance(releases, list):
        return make_error(source_name, "unexpected_payload", "GitHub releases API returned non-list payload")
    owner, project_name = repo.split("/", 1)
    items: list[dict[str, Any]] = []
    for release in releases[:limit]:
        if not isinstance(release, dict):
            continue
        title = clean_text(release.get("name") or release.get("tag_name") or "")
        source_url = release.get("html_url")
        body = clean_text(release.get("body")) or title
        tag_name = release.get("tag_name") or ""

        if not title or not source_url:
            continue

        assets = [
            {
                "name": asset.get("name"),
                "download_url": asset.get("browser_download_url"),
            }
            for asset in release.get("assets", [])
        ]
        signals = _release_signals(title, tag_name, body)
        items.append(
            make_raw_source_item(
                source_type="official",
                medium_type="release",
                source_name=source_name,
                source_url=source_url,
                title=title,
                summary=body[:500],
                content=body,
                language=source_value(source, "language", "en"),
                published_at=parse_datetime(release.get("published_at") or release.get("created_at")),
                raw_payload=release,
                item_id=str(release.get("id") or source_url),
                authors=[(release.get("author") or {}).get("login")] if (release.get("author") or {}).get("login") else [],
                item_type="github_release",
                repo=repo,
                owner=owner,
                project_name=project_name,
                release_name=title,
                tag_name=tag_name,
                body=body,
                assets=assets,
                signals=signals,
            )
        )

    return make_collection_result(source_name=source_name, items=items)


class GitHubReleaseCollector(SourceCollector):
    def collect(self, source: Any, limit: int):
        return to_collector_result(collect(source_config_to_dict(source), limit))
