from __future__ import annotations

from .prompts import COORDINATOR_SYSTEM, final_summary_prompt, stage_report_prompt
from .scenario import Scenario


def stage_report_messages(scenario: Scenario, loop_index: int, compact: str, discussion: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": COORDINATOR_SYSTEM},
        {"role": "user", "content": stage_report_prompt(scenario, loop_index, compact, discussion)},
    ]


def final_summary_messages(scenario: Scenario, stage_reports: list[str], full_timeline: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": COORDINATOR_SYSTEM},
        {"role": "user", "content": final_summary_prompt(scenario, stage_reports, full_timeline)},
    ]
