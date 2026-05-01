from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_SCENARIO_LOOPS = 5


@dataclass(frozen=True)
class Scenario:
    path: Path
    title: str
    loops: int
    domain: str
    source_refs: list[dict[str, str]]
    primary_tests: list[str]
    body: str


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value.isdigit():
        return int(value)
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return value.strip('"').strip("'")


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, flags=re.S)
    if not match:
        return {}, text
    raw_meta, body = match.groups()
    meta: dict[str, Any] = {}
    current_key: str | None = None
    current_item: dict[str, str] | None = None
    for raw_line in raw_meta.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            current_item = None
            if value:
                meta[key] = _parse_scalar(value)
            else:
                meta[key] = []
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            item = stripped[2:]
            if ":" in item:
                key, value = item.split(":", 1)
                current_item = {key.strip(): str(_parse_scalar(value))}
                meta.setdefault(current_key or "items", []).append(current_item)
            else:
                meta.setdefault(current_key or "items", []).append(item.strip())
                current_item = None
            continue
        if current_item is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            current_item[key.strip()] = str(_parse_scalar(value))
    return meta, body


def load_scenario(path: Path, loops_override: int | None = None) -> Scenario:
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    title = str(meta.get("title") or path.stem)
    loops = loops_override if loops_override is not None else int(meta.get("loops") or DEFAULT_SCENARIO_LOOPS)
    source_refs = meta.get("source_refs") or []
    if not isinstance(source_refs, list):
        source_refs = []
    primary_tests = meta.get("primary_tests") or []
    if not isinstance(primary_tests, list):
        primary_tests = []
    return Scenario(
        path=path,
        title=title,
        loops=loops,
        domain=str(meta.get("domain") or "proposal_deliberation"),
        source_refs=source_refs,
        primary_tests=[str(item) for item in primary_tests],
        body=body.strip(),
    )
