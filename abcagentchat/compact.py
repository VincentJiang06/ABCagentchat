from __future__ import annotations

from .background import compact_archive_context, previous_reports_context
from .prompts import COORDINATOR_SYSTEM, compact_prompt
from .scenario import Scenario


def compact_messages(
    scenario: Scenario,
    loop_index: int,
    compact_history: list[str],
    previous_reports: list[str],
    recent_discussion: str,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": COORDINATOR_SYSTEM},
        {
            "role": "user",
            "content": compact_prompt(
                scenario,
                loop_index,
                compact_archive_context(scenario, compact_history),
                previous_reports_context(previous_reports),
                recent_discussion,
            ),
        },
    ]
