from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class SourceConfig(BaseModel):
    name: str
    type: str
    medium: str
    method: str
    language: str = "en"
    enabled: bool = True
    url: str | None = None
    query: str | None = None
    repo: str | None = None
    limit: int | None = None

    model_config = {"extra": "allow"}


class SourcesConfig(BaseModel):
    sources: list[SourceConfig] = Field(default_factory=list)


def load_sources_config(path: str | Path) -> SourcesConfig:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    data = _load_yaml_subset(text)
    return SourcesConfig.model_validate(data)


def _load_yaml_subset(text: str) -> dict[str, Any]:
    """Parse the simple YAML shape used by configs/sources.yaml.

    PyYAML is intentionally optional for the MVP runtime; this parser supports
    top-level keys with a list of flat dictionaries.
    """
    result: dict[str, Any] = {}
    current_list_name: str | None = None
    current_item: dict[str, Any] | None = None

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.strip()

        if not raw_line.startswith(" ") and stripped.endswith(":"):
            current_list_name = stripped[:-1]
            result[current_list_name] = []
            current_item = None
            continue

        if stripped.startswith("- "):
            if current_list_name is None:
                raise ValueError("YAML list item found before a list key")
            current_item = {}
            result[current_list_name].append(current_item)
            item_body = stripped[2:].strip()
            if item_body:
                key, value = _split_key_value(item_body)
                current_item[key] = _parse_scalar(value)
            continue

        if current_item is not None and ":" in stripped:
            key, value = _split_key_value(stripped)
            current_item[key] = _parse_scalar(value)

    return result


def _split_key_value(line: str) -> tuple[str, str]:
    key, value = line.split(":", 1)
    return key.strip(), value.strip()


def _parse_scalar(value: str) -> Any:
    if value == "":
        return None
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value

