from __future__ import annotations

import json
from pathlib import Path
from typing import Any


EXPECTED_LOOP_FILES = [
    "background_context.md",
    "compact.md",
    "discussion_plan.raw.json",
    "discussion_plan.json",
    "discussion_plan.md",
    "stage_report.md",
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def summarize_transcript(transcript_path: Path) -> dict[str, Any]:
    rows = load_jsonl(transcript_path)
    usage_rows = [row.get("usage") or {} for row in rows]
    by_type: dict[str, int] = {}
    by_client: dict[str, int] = {}
    for row in rows:
        by_type[row.get("call_type", "unknown")] = by_type.get(row.get("call_type", "unknown"), 0) + 1
        by_client[row.get("client_key", "unknown")] = by_client.get(row.get("client_key", "unknown"), 0) + 1
    return {
        "call_count": len(rows),
        "by_type": by_type,
        "by_client": by_client,
        "prompt_tokens": sum(int(usage.get("prompt_tokens") or 0) for usage in usage_rows),
        "completion_tokens": sum(int(usage.get("completion_tokens") or 0) for usage in usage_rows),
        "reasoning_tokens": sum(int(usage.get("reasoning_tokens") or 0) for usage in usage_rows),
        "total_tokens": sum(int(usage.get("total_tokens") or 0) for usage in usage_rows),
        "elapsed_seconds": round(sum(float(usage.get("elapsed_seconds") or 0) for usage in usage_rows), 3),
        "length_stops": sum(1 for usage in usage_rows if usage.get("finish_reason") == "length"),
        "empty_or_missing_previews": sum(1 for row in rows if not str(row.get("content_preview") or "").strip()),
    }


def audit_run_dir(run_dir: Path) -> dict[str, Any]:
    run_config_path = run_dir / "run_config.json"
    run_config = json.loads(run_config_path.read_text(encoding="utf-8")) if run_config_path.exists() else {}
    loops = int((run_config.get("scenario") or {}).get("loops") or 0)
    options = run_config.get("options") or {}
    rounds_per_subcycle = int(options.get("rounds_per_subcycle") or 1)
    transcript = summarize_transcript(run_dir / "transcript.jsonl")
    expected_calls = 1 if loops else None
    optional_repair_calls = int((transcript.get("by_type") or {}).get("planning_repair") or 0)
    if expected_calls is not None:
        expected_calls += optional_repair_calls

    missing_files: list[str] = []
    if not (run_dir / "input.md").exists():
        missing_files.append("input.md")
    if not (run_dir / "run_config.json").exists():
        missing_files.append("run_config.json")
    if not (run_dir / "transcript.jsonl").exists():
        missing_files.append("transcript.jsonl")
    if not (run_dir / "final_summary.md").exists():
        missing_files.append("final_summary.md")

    round_line_counts: dict[str, int] = {}
    for index in range(1, loops + 1):
        loop_dir = run_dir / f"loop_{index:02d}"
        for name in EXPECTED_LOOP_FILES:
            path = loop_dir / name
            if not path.exists():
                missing_files.append(str(path.relative_to(run_dir)))
        plan_path = loop_dir / "discussion_plan.json"
        groups = []
        if plan_path.exists():
            groups = (json.loads(plan_path.read_text(encoding="utf-8")).get("groups") or [])
        if expected_calls is not None:
            expected_calls += 3 + len(groups) * rounds_per_subcycle * 4
        for subcycle_index, group in enumerate(groups, start=1):
            group_id = str(group.get("group_id") or subcycle_index)
            subcycle_dirs = sorted(loop_dir.glob(f"subcycle_{subcycle_index:02d}_*"))
            if not subcycle_dirs:
                missing_files.append(f"loop_{index:02d}/subcycle_{subcycle_index:02d}_{group_id}")
                continue
            subcycle_dir = subcycle_dirs[0]
            for round_index in range(1, rounds_per_subcycle + 1):
                round_path = subcycle_dir / f"discussion_round_{round_index:02d}.jsonl"
                if not round_path.exists():
                    missing_files.append(str(round_path.relative_to(run_dir)))
                    continue
                round_line_counts[str(round_path.relative_to(run_dir))] = len(load_jsonl(round_path))

    failed_rounds = {
        path: count for path, count in round_line_counts.items() if count != 4
    }
    errors_path = run_dir / "errors.jsonl"
    errors = load_jsonl(errors_path)
    checks = {
        "has_expected_files": not missing_files,
        "has_no_errors": not errors,
        "call_count_matches": expected_calls is None or transcript["call_count"] == expected_calls,
        "all_rounds_have_four_roles": not failed_rounds,
        "has_no_length_stops": transcript["length_stops"] == 0,
        "has_no_empty_previews": transcript["empty_or_missing_previews"] == 0,
    }
    return {
        "run_dir": str(run_dir),
        "loops": loops,
        "expected_calls": expected_calls,
        "checks": checks,
        "passed": all(checks.values()),
        "missing_files": missing_files,
        "failed_rounds": failed_rounds,
        "error_count": len(errors),
        "transcript": transcript,
    }


def write_metrics(run_dir: Path) -> dict[str, Any]:
    metrics = audit_run_dir(run_dir)
    (run_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metrics
