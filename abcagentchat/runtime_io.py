from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .api import ChatResult


def safe_slug(value: str) -> str:
    value = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", value.strip())
    value = value.strip("-._")
    return value[:80] or "scenario"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def result_summary(result: ChatResult) -> dict[str, Any]:
    return {
        "elapsed_seconds": round(result.elapsed_seconds, 3),
        "finish_reason": result.finish_reason,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "reasoning_tokens": result.reasoning_tokens,
        "visible_answer_tokens_estimate": result.visible_answer_tokens_estimate,
        "total_tokens": result.total_tokens,
    }
