from __future__ import annotations

from .gc import trim_text
from .scenario import Scenario


def recent_context(text: str, max_chars: int) -> str:
    return trim_text(text, max_chars)


def previous_reports_context(previous_reports: list[str], keep: int = 3) -> str:
    return "\n\n".join(previous_reports[-keep:]) if previous_reports else "暂无上一阶段报告。"


def compact_archive_context(scenario: Scenario, compact_history: list[str]) -> str:
    parts = [
        "# 原始议题全文",
        scenario.body,
        "# 历史 compact 档案",
    ]
    if not compact_history:
        parts.append("暂无历史 compact。")
    else:
        for index, compact in enumerate(compact_history, start=1):
            parts.append(f"\n## 第 {index} 个循环 compact\n{compact}")
    return "\n\n".join(parts)
