from __future__ import annotations

import json
import sqlite3

from backend.app.cli import load_fixture_items, run_collection_pipeline
from backend.app.pipelines.collection import select_hot_items
from backend.app.rag import chunk_source_item, write_chunks
from backend.app.storage import RawSourceItem, SQLiteMetadataStore


def test_sqlite_store_creates_table_and_upserts_item(tmp_path):
    item = RawSourceItem(
        id="item-1",
        source_type="official",
        medium_type="blog",
        source_name="OpenAI Blog",
        source_url="https://example.com/item-1",
        title="OpenAI LLM update",
        summary="A generative AI update.",
        content="",
        language="en",
        published_at="2026-06-01T00:00:00Z",
        collected_at="2026-06-14T00:00:00Z",
        raw_payload={"version": 1},
    )
    store = SQLiteMetadataStore(tmp_path / "metadata.sqlite")
    store.upsert_item(item, ai_relevance_score=0.75)
    store.upsert_item(item, ai_relevance_score=0.9)

    with sqlite3.connect(tmp_path / "metadata.sqlite") as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(source_items)").fetchall()
        }

    assert store.count_items() == 1
    stored = store.fetch_item("item-1")
    assert stored is not None
    assert stored["ai_relevance_score"] == 0.9
    assert {
        "id",
        "source_type",
        "medium_type",
        "source_name",
        "source_url",
        "title",
        "summary",
        "content",
        "language",
        "published_at",
        "collected_at",
        "raw_payload_json",
        "content_hash",
        "ai_relevance_score",
    }.issubset(columns)


def test_rag_chunk_generation_and_file_output(tmp_path):
    item = load_fixture_items("tests/fixtures/raw_source_items.json")[0]
    chunks = chunk_source_item(item, max_chars=80)
    paths = write_chunks(chunks, tmp_path / "rag")

    assert paths
    first = json.loads(paths[0].read_text(encoding="utf-8"))
    assert first["text"].startswith("Title: OpenAI announces")
    assert "Content:" in first["text"]
    assert first["metadata"]["source_item_id"] == item.id
    assert first["metadata"]["url"] == item.source_url


def test_collection_pipeline_uses_offline_fixture(tmp_path):
    items = load_fixture_items("tests/fixtures/raw_source_items.json")
    summary = run_collection_pipeline(
        items=items,
        db_path=tmp_path / "source_items.sqlite",
        rag_dir=tmp_path / "rag",
    )

    assert summary["candidate_count"] == 4
    assert summary["ai_related_count"] == 3
    assert summary["deduplicated_count"] == 2
    assert summary["stored_count"] == 2
    assert summary["chunk_count"] >= 2
    assert SQLiteMetadataStore(tmp_path / "source_items.sqlite").count_items() == 2
    assert len(list((tmp_path / "rag").glob("*.json"))) == summary["chunk_count"]


def test_select_hot_items_limits_each_source_to_three():
    items = [
        RawSourceItem(
            id=f"same-{index}",
            source_type="tech_media",
            medium_type="article",
            source_name="Same Source",
            source_url=f"https://example.com/same-{index}",
            title=f"AI model update {index}",
            summary="AI LLM agent update.",
            content="AI LLM agent update. " * (index + 1),
            language="en",
            published_at=f"2026-06-1{index}T00:00:00Z",
        )
        for index in range(5)
    ]
    items.append(
        RawSourceItem(
            id="other-1",
            source_type="official",
            medium_type="blog",
            source_name="Other Source",
            source_url="https://example.com/other-1",
            title="OpenAI AI release",
            summary="OpenAI announces an AI release.",
            content="OpenAI announces an AI release.",
            language="en",
            published_at="2026-06-15T00:00:00Z",
        )
    )
    relevance_by_id = {f"same-{index}": index / 10 for index in range(5)}
    relevance_by_id["other-1"] = 0.2

    selected = select_hot_items(
        items,
        relevance_by_id=relevance_by_id,
        target_limit=20,
        max_items_per_source=3,
    )

    same_source_ids = [item.id for item in selected if item.source_name == "Same Source"]
    assert len(same_source_ids) == 3
    assert set(same_source_ids) == {"same-2", "same-3", "same-4"}
    assert any(item.id == "other-1" for item in selected)


def test_select_hot_items_keeps_chinese_diversity_floor():
    items = [
        RawSourceItem(
            id=f"en-{index}",
            source_type="official",
            medium_type="blog",
            source_name=f"English Source {index}",
            source_url=f"https://example.com/en-{index}",
            title=f"OpenAI AI platform update {index}",
            summary="OpenAI AI LLM platform update.",
            content="OpenAI AI LLM platform update.",
            language="en",
            published_at=f"2026-06-1{index}T00:00:00Z",
        )
        for index in range(5)
    ]
    items.extend(
        RawSourceItem(
            id=f"zh-{index}",
            source_type="aggregator",
            medium_type="ranking_item",
            source_name="中文来源",
            source_url=f"https://example.com/zh-{index}",
            title=f"人工智能大模型进展 {index}",
            summary="人工智能和大模型产业进展。",
            content="人工智能和大模型产业进展。",
            language="zh",
            published_at=f"2026-06-1{index}T01:00:00Z",
        )
        for index in range(4)
    )
    relevance_by_id = {item.id or "": 0.9 if item.language == "en" else 0.2 for item in items}

    selected = select_hot_items(
        items,
        relevance_by_id=relevance_by_id,
        target_limit=6,
        max_items_per_source=3,
        min_chinese_items=3,
    )

    assert sum(1 for item in selected if item.language == "zh") == 3
    assert sum(1 for item in selected if item.source_name == "中文来源") == 3
