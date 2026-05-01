#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import fields
from pathlib import Path
from typing import Any

from abcagentchat.background import DEFAULT_FULL_RECENT_COMPACTS, compact_archive_context, recent_context
from abcagentchat.config import AppConfig
from abcagentchat.metrics import summarize_transcript, write_metrics
from abcagentchat.monitor import NullMonitor, RunMonitor
from abcagentchat.roles import collect_discussion_parts, run_discussion_group
from abcagentchat.scenario import load_scenario
from abcagentchat.simulator import RunOptions, Simulator
from abcagentchat.runtime_io import write_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resume an interrupted ABCagentchat run directory.")
    parser.add_argument("run_dir", type=Path, help="Existing run directory.")
    parser.add_argument("--enable-monitor", action="store_true", help="Write monitor.html/status.json while resuming.")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def options_from_config(run_config: dict[str, Any], run_dir: Path, *, enable_monitor: bool) -> RunOptions:
    raw_options = dict(run_config.get("options") or {})
    allowed = {field.name for field in fields(RunOptions)}
    raw_options = {key: value for key, value in raw_options.items() if key in allowed}
    raw_options["output_dir"] = run_dir
    raw_options["enable_monitor"] = enable_monitor
    return RunOptions(**raw_options)


def load_completed_history(run_dir: Path, loops: int, recent_context_chars: int) -> tuple[list[str], list[str], list[str], str, int]:
    compact_history: list[str] = []
    previous_reports: list[str] = []
    timeline_items: list[str] = []
    recent_discussion = ""
    completed_loops = 0

    for loop_index in range(1, loops + 1):
        loop_dir = run_dir / f"loop_{loop_index:02d}"
        compact_path = loop_dir / "compact.md"
        report_path = loop_dir / "stage_report.md"
        if not compact_path.exists() or not report_path.exists():
            break
        compact = compact_path.read_text(encoding="utf-8")
        report = report_path.read_text(encoding="utf-8")
        compact_history.append(compact)
        previous_reports.append(report)
        timeline_items.append(f"loop_{loop_index:02d}: loop_{loop_index:02d}/stage_report.md")
        discussion_text = "\n\n".join(collect_discussion_parts(loop_dir))
        recent_discussion = recent_context(discussion_text + "\n\n" + report, recent_context_chars)
        completed_loops = loop_index

    return compact_history, previous_reports, timeline_items, recent_discussion, completed_loops


def discussion_plan(loop_dir: Path) -> dict[str, Any]:
    return load_json(loop_dir / "discussion_plan.json")


def seed_monitor(run_dir: Path, scenario_title: str, total_loops: int, current_loop: int, enabled: bool) -> RunMonitor | NullMonitor:
    if not enabled:
        return NullMonitor()
    monitor = RunMonitor(run_dir, scenario_title=scenario_title, total_loops=total_loops)
    transcript = summarize_transcript(run_dir / "transcript.jsonl")
    monitor.update(
        "running",
        f"resume from loop {current_loop}",
        current_loop=current_loop,
        call_count=transcript["call_count"],
        total_tokens=transcript["total_tokens"],
        by_type=transcript["by_type"],
    )
    return monitor


def main() -> int:
    root = Path(__file__).resolve().parent
    args = parse_args()
    run_dir = args.run_dir.resolve()
    run_config = load_json(run_dir / "run_config.json")
    loops = int((run_config.get("scenario") or {}).get("loops") or 0)
    scenario_path = Path((run_config.get("scenario") or {}).get("path") or (run_dir / "input.md"))
    scenario = load_scenario(scenario_path, loops_override=loops)
    options = options_from_config(run_config, run_dir, enable_monitor=args.enable_monitor)
    config = None if bool(run_config.get("dry_run")) else AppConfig.from_env(root, timeout=options.timeout)
    simulator = Simulator(root=root, config=config, options=options)

    compact_history, previous_reports, timeline_items, recent_discussion, completed_loops = load_completed_history(
        run_dir,
        loops,
        options.recent_context_chars,
    )
    start_loop = completed_loops + 1
    if start_loop > loops:
        print(f"[resume] run already has {loops} completed loops", flush=True)
        write_metrics(run_dir)
        return 0

    monitor = seed_monitor(run_dir, scenario.title, loops, start_loop, args.enable_monitor)
    transcript_path = run_dir / "transcript.jsonl"
    errors_path = run_dir / "errors.jsonl"
    compact_archive_summary_path = run_dir / "compact_archive_summary.md"
    compact_archive_summary = (
        compact_archive_summary_path.read_text(encoding="utf-8") if compact_archive_summary_path.exists() else ""
    )
    compact_archive_summary_count = max(0, len(compact_history) - DEFAULT_FULL_RECENT_COMPACTS) if compact_archive_summary else 0

    print(f"[resume] scenario={scenario.title}", flush=True)
    print(f"[resume] completed_loops={completed_loops} remaining={loops - completed_loops}", flush=True)
    print(f"[resume] output={run_dir}", flush=True)
    if args.enable_monitor:
        print(f"[monitor] file={run_dir / 'monitor.html'}", flush=True)

    for loop_index in range(start_loop, loops + 1):
        loop_dir = run_dir / f"loop_{loop_index:02d}"
        loop_dir.mkdir(parents=True, exist_ok=True)
        monitor.update("running", f"loop {loop_index}: resume", current_loop=loop_index)

        compact_path = loop_dir / "compact.md"
        plan_path = loop_dir / "discussion_plan.json"
        background_path = loop_dir / "background_context.md"

        if compact_path.exists():
            compact = compact_path.read_text(encoding="utf-8")
            print(f"[loop {loop_index}] compact exists; reusing", flush=True)
        else:
            compact_archive_summary, compact_archive_summary_count = simulator._refresh_compact_archive_summary(
                scenario=scenario,
                compact_history=compact_history,
                current_summary=compact_archive_summary,
                summarized_count=compact_archive_summary_count,
                loop_dir=loop_dir,
                transcript_path=transcript_path,
                errors_path=errors_path,
                monitor=monitor,
            )
            compact = simulator._run_compact(
                scenario,
                loop_index,
                compact_history,
                compact_archive_summary,
                previous_reports,
                recent_discussion,
                loop_dir,
                transcript_path,
                errors_path,
                monitor,
            )

        background_context = (
            background_path.read_text(encoding="utf-8")
            if background_path.exists()
            else compact_archive_context(scenario, compact_history, earlier_summary=compact_archive_summary)
        )
        if not background_path.exists():
            write_text(background_path, background_context)

        if plan_path.exists():
            plan = discussion_plan(loop_dir)
            print(f"[loop {loop_index}] planning exists; reusing", flush=True)
        else:
            plan = simulator._run_planning(
                scenario,
                compact,
                background_context,
                loop_index,
                loop_dir,
                transcript_path,
                errors_path,
                monitor,
            )

        loop_discussion_parts: list[str] = []
        for subcycle_index, group in enumerate(plan["groups"], start=1):
            print(f"[loop {loop_index}] subcycle={subcycle_index} title={group['title']}", flush=True)
            loop_discussion_parts.extend(
                run_discussion_group(
                    scenario=scenario,
                    compact=compact,
                    group=group,
                    loop_index=loop_index,
                    subcycle_index=subcycle_index,
                    rounds_per_subcycle=options.rounds_per_subcycle,
                    recent_history=recent_context(recent_discussion, options.recent_context_chars),
                    background_context=background_context,
                    loop_dir=loop_dir,
                    role_max_tokens=options.role_max_tokens,
                    preview_chars=options.preview_chars,
                    resume_existing=True,
                    include_summary_round=options.role_summary_round,
                    call_role=lambda client_key, call_type, messages, max_tokens, context_meta: simulator._call(
                        client_key=client_key,
                        call_type=call_type,
                        messages=messages,
                        transcript_path=transcript_path,
                        errors_path=errors_path,
                        max_tokens=max_tokens,
                        monitor=monitor,
                        context_meta=context_meta,
                    ),
                )
            )

        report_path = loop_dir / "stage_report.md"
        discussion_text = "\n\n".join(loop_discussion_parts)
        if report_path.exists():
            stage_report = report_path.read_text(encoding="utf-8")
            print(f"[loop {loop_index}] stage_report exists; reusing", flush=True)
        else:
            stage_report = simulator._run_stage_report(
                scenario,
                loop_index,
                compact,
                discussion_text,
                loop_dir,
                transcript_path,
                errors_path,
                monitor,
            )
        compact_history.append(compact)
        previous_reports.append(stage_report)
        recent_discussion = recent_context(discussion_text + "\n\n" + stage_report, options.recent_context_chars)
        timeline_items.append(f"loop_{loop_index:02d}: loop_{loop_index:02d}/stage_report.md")

    final_path = run_dir / "final_summary.md"
    if final_path.exists():
        final_summary = final_path.read_text(encoding="utf-8")
    else:
        final_summary = simulator._run_final_summary(
            scenario,
            previous_reports,
            timeline_items,
            run_dir,
            transcript_path,
            errors_path,
            monitor,
        )
    simulator._write_final_artifacts(run_dir, final_summary, timeline_items)
    print(f"[final] preview={final_summary[:options.preview_chars].replace(chr(10), ' ')}", flush=True)
    metrics = write_metrics(run_dir)
    monitor.update(
        "done",
        "completed",
        call_count=metrics["transcript"]["call_count"],
        total_tokens=metrics["transcript"]["total_tokens"],
        by_type=metrics["transcript"]["by_type"],
    )
    print(f"[metrics] passed={metrics['passed']} calls={metrics['transcript']['call_count']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
