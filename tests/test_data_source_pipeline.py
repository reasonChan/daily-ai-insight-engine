from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from backend.app.collectors.base import SourceCollector
from backend.app.core.config import SourceConfig, load_sources_config
from backend.app.pipelines.collection import CollectionPipeline
from backend.app.schemas.source import CollectorResult, RawSourceItem
from backend.app.services.dedup import deduplicate_items
from backend.app.services.relevance import evaluate_ai_relevance


class FakeRegistry:
    def resolve(self, source: SourceConfig) -> SourceCollector:
        return FakeCollector()


class FakeCollector(SourceCollector):
    def collect(self, source: SourceConfig, limit: int) -> CollectorResult:
        published = datetime(2026, 6, 14, tzinfo=timezone.utc)
        return CollectorResult(
            items=[
                RawSourceItem(
                    source_type=source.type,
                    medium_type=source.medium,
                    source_name=source.name,
                    source_url="https://example.com/ai-agent",
                    title="OpenAI agent platform update",
                    summary="A new AI agent workflow for LLM applications.",
                    language=source.language,
                    published_at=published,
                ),
                RawSourceItem(
                    source_type=source.type,
                    medium_type=source.medium,
                    source_name=source.name,
                    source_url="https://example.com/not-ai",
                    title="Quarterly office lease roundup",
                    summary="Real estate market updates.",
                    language=source.language,
                    published_at=published,
                ),
                RawSourceItem(
                    source_type=source.type,
                    medium_type=source.medium,
                    source_name=source.name,
                    source_url="https://example.com/ai-agent#utm",
                    title="OpenAI agent platform update",
                    summary="Duplicate of the AI agent story.",
                    language=source.language,
                    published_at=published,
                ),
            ]
        )


class DataSourcePipelineTests(unittest.TestCase):
    def test_config_loader_reads_sources_yaml_subset(self) -> None:
        config = load_sources_config("configs/sources.yaml")
        self.assertGreaterEqual(len(config.sources), 10)
        self.assertTrue(config.sources[0].enabled)

    def test_relevance_filter_matches_english_and_chinese(self) -> None:
        item = RawSourceItem(
            source_type="tech_media",
            medium_type="article",
            source_name="fixture",
            source_url="https://example.com/1",
            title="大模型 agent benchmark",
            summary="人工智能 and LLM evaluation",
            language="zh",
            published_at=datetime(2026, 6, 14, tzinfo=timezone.utc),
        )
        result = evaluate_ai_relevance(item)
        self.assertTrue(result.is_ai_related)
        self.assertIn("llm", result.topics)

    def test_deduplicate_by_url_title_and_hash(self) -> None:
        base = RawSourceItem(
            source_type="tech_media",
            medium_type="article",
            source_name="fixture",
            source_url="https://example.com/a/",
            title="OpenAI releases model",
            summary="AI content",
            language="en",
            published_at=datetime(2026, 6, 14, tzinfo=timezone.utc),
        )
        duplicate_url = base.model_copy(update={"source_url": "https://example.com/a"})
        duplicate_title = base.model_copy(update={"source_url": "https://example.com/b"})
        result = deduplicate_items([base, duplicate_url, duplicate_title])
        self.assertEqual(len(result.items), 1)
        self.assertEqual(len(result.duplicate_source_urls), 2)

    def test_pipeline_writes_sqlite_chunks_and_summary_offline(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            config_path = root / "sources.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "sources:",
                        "  - name: Fixture AI",
                        "    type: tech_media",
                        "    medium: article",
                        "    method: rss",
                        "    language: en",
                        "    enabled: true",
                    ]
                ),
                encoding="utf-8",
            )
            db_path = root / "source_items.sqlite"
            chunks_path = root / "chunks.jsonl"
            summary_path = root / "summary.json"

            summary, items = CollectionPipeline(registry=FakeRegistry()).run(
                config_path=config_path,
                db_path=db_path,
                chunks_path=chunks_path,
                summary_path=summary_path,
                per_source_limit=5,
                target_limit=20,
            )

            self.assertEqual(summary.candidate_count, 3)
            self.assertEqual(summary.ai_related_count, 2)
            self.assertEqual(summary.deduplicated_count, 1)
            self.assertEqual(summary.stored_count, 1)
            self.assertEqual(len(items), 1)
            with closing(sqlite3.connect(db_path)) as conn:
                count = conn.execute("SELECT COUNT(*) FROM source_items").fetchone()[0]
            self.assertEqual(count, 1)
            chunks = chunks_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(chunks), 1)
            self.assertEqual(json.loads(chunks[0])["metadata"]["source_type"], "tech_media")
            self.assertTrue(summary_path.exists())


if __name__ == "__main__":
    unittest.main()
