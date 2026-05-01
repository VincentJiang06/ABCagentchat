from __future__ import annotations

from .gc import trim_text
from .scenario import Scenario


DEFAULT_FULL_RECENT_COMPACTS = 4
GRADIENT_COMPACT_EXCERPT_CHARS = (
    (8, 4000),
    (20, 1600),
    (10_000, 500),
)


def recent_context(text: str, max_chars: int) -> str:
    return trim_text(text, max_chars)


def previous_reports_context(previous_reports: list[str], keep: int = 3) -> str:
    return "\n\n".join(previous_reports[-keep:]) if previous_reports else "暂无上一阶段报告。"


def split_compact_history(
    compact_history: list[str],
    recent_count: int = DEFAULT_FULL_RECENT_COMPACTS,
) -> tuple[list[str], list[str]]:
    older_count = max(0, len(compact_history) - recent_count)
    return compact_history[:older_count], compact_history[older_count:]


def compact_excerpt(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head_chars = max(200, int(max_chars * 0.7))
    tail_chars = max(100, max_chars - head_chars)
    return (
        text[:head_chars].rstrip()
        + "\n\n...[中间内容按梯度省略，保留开头账本结构和末尾防遗忘信息]...\n\n"
        + text[-tail_chars:].lstrip()
    )


def gradient_excerpt_limit(distance_from_latest: int) -> int:
    for max_distance, char_limit in GRADIENT_COMPACT_EXCERPT_CHARS:
        if distance_from_latest <= max_distance:
            return char_limit
    return GRADIENT_COMPACT_EXCERPT_CHARS[-1][1]


def compact_archive_context(
    scenario: Scenario,
    compact_history: list[str],
    *,
    earlier_summary: str = "",
    recent_count: int = DEFAULT_FULL_RECENT_COMPACTS,
) -> str:
    older, recent = split_compact_history(compact_history, recent_count=recent_count)
    parts = [
        "# 原始议题全文",
        scenario.body,
        "# 历史 compact 档案",
    ]
    if not compact_history:
        parts.append("暂无历史 compact。")
    else:
        if older:
            parts.append(
                f"\n## 第 1-{len(older)} 个循环 compact 滚动开放讨论账本摘要\n"
                f"{earlier_summary or '更早 compact 摘要尚未生成。'}"
            )
            parts.append("\n# 历史 compact 梯度摘录")
            latest_index = len(compact_history)
            for index, compact in enumerate(older, start=1):
                distance = latest_index - index + 1
                char_limit = gradient_excerpt_limit(distance)
                parts.append(
                    f"\n## 第 {index} 个循环 compact（梯度摘录，距最新 {distance - 1} 轮，最多 {char_limit} 字符）\n"
                    f"{compact_excerpt(compact, char_limit)}"
                )
            parts.append("\n# 最近 compact 全文")
        start_index = len(older) + 1
        for index, compact in enumerate(recent, start=start_index):
            parts.append(f"\n## 第 {index} 个循环 compact（全文）\n{compact}")
    return "\n\n".join(parts)
