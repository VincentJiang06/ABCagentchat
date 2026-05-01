#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from abcagentchat.monitor import MONITOR_HTML
from abcagentchat.scenario import load_scenario


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def scenario_index(path: Path) -> int:
    prefix = path.stem.split("_", 1)[0]
    try:
        return int(prefix)
    except ValueError:
        return 9999


def make_case(path: Path, batch_run_dir: Path) -> dict[str, Any]:
    scenario = load_scenario(path)
    run_dir = batch_run_dir / path.stem
    return {
        "index": scenario_index(path),
        "slug": path.stem,
        "title": scenario.title,
        "scenario": str(path),
        "run_dir": str(run_dir),
        "monitor_url": f"{batch_run_dir.name}/{path.stem}/monitor.html",
        "status": "pending",
        "current_loop": 0,
        "total_loops": scenario.loops,
        "call_count": 0,
        "total_tokens": 0,
        "error_count": 0,
        "current_step": "pending",
    }


def batch_payload(batch_id: str, started_at: str, cases: list[dict[str, Any]], status: str) -> dict[str, Any]:
    done = sum(1 for item in cases if item.get("status") == "done")
    failed = sum(1 for item in cases if item.get("status") in {"error", "failed"})
    running = [item for item in cases if item.get("status") == "running"]
    return {
        "status": status,
        "batch_id": batch_id,
        "started_at": started_at,
        "updated_at": now_iso(),
        "total_cases": len(cases),
        "done_count": done,
        "failed_count": failed,
        "running_case": running[0]["slug"] if running else "",
        "cases": cases,
    }


def update_from_child_status(case: dict[str, Any]) -> None:
    status = read_json(Path(case["run_dir"]) / "status.json")
    if not status:
        return
    for key in (
        "current_loop",
        "total_loops",
        "call_count",
        "total_tokens",
        "error_count",
        "current_step",
    ):
        if key in status:
            case[key] = status[key]


def update_from_metrics(case: dict[str, Any]) -> None:
    metrics = read_json(Path(case["run_dir"]) / "metrics.json")
    transcript = metrics.get("transcript") or {}
    if transcript:
        case["call_count"] = transcript.get("call_count", case.get("call_count", 0))
        case["total_tokens"] = transcript.get("total_tokens", case.get("total_tokens", 0))
    case["audit_passed"] = bool(metrics.get("passed")) if metrics else False


def append_summary(batch_run_dir: Path, cases: list[dict[str, Any]]) -> None:
    lines = [
        "# ABCagentchat Batch Run",
        "",
        f"- Batch: `{batch_run_dir.name}`",
        f"- Updated: {now_iso()}",
        f"- Total cases: {len(cases)}",
        "",
        "| # | Status | Scenario | Calls | Tokens | Errors |",
        "|---:|---|---|---:|---:|---:|",
    ]
    for case in cases:
        lines.append(
            "| {index} | {status} | `{slug}` | {calls} | {tokens} | {errors} |".format(
                index=case.get("index", ""),
                status=case.get("status", ""),
                slug=case.get("slug", ""),
                calls=case.get("call_count", 0) or 0,
                tokens=case.get("total_tokens", 0) or 0,
                errors=case.get("error_count", 0) or 0,
            )
        )
    (batch_run_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run all ABCagentchat scenarios sequentially with batch monitoring.")
    parser.add_argument("--scenarios-dir", type=Path, default=Path("scenarios"))
    parser.add_argument("--out", type=Path, default=Path("runs/nightly-all-tests"))
    parser.add_argument("--batch-id", default=datetime.now().strftime("batch-%Y%m%d-%H%M%S"))
    parser.add_argument("--loops", type=int, default=5)
    parser.add_argument("--profile", choices=["quality", "long-run"], default="long-run")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stop-on-error", action="store_true")
    return parser.parse_args()


def main() -> int:
    root = Path(__file__).resolve().parent
    args = parse_args()
    scenarios = sorted((root / args.scenarios_dir).glob("*.md"), key=scenario_index)
    if not scenarios:
        raise SystemExit(f"No scenarios found in {args.scenarios_dir}")

    batch_root = (root / args.out).resolve()
    batch_run_dir = batch_root / args.batch_id
    batch_run_dir.mkdir(parents=True, exist_ok=True)
    (batch_root / "monitor.html").write_text(MONITOR_HTML, encoding="utf-8")
    (batch_run_dir / "monitor.html").write_text(MONITOR_HTML, encoding="utf-8")

    cases = [make_case(path, batch_run_dir) for path in scenarios]
    started_at = now_iso()
    status_path = batch_root / "batch_status.json"
    write_json(status_path, batch_payload(args.batch_id, started_at, cases, "running"))
    append_summary(batch_run_dir, cases)

    batch_log_path = batch_run_dir / "batch.log"
    with batch_log_path.open("a", encoding="utf-8") as batch_log:
        print(f"[batch] id={args.batch_id} cases={len(cases)} out={batch_root}", flush=True)
        batch_log.write(f"[{now_iso()}] batch start cases={len(cases)}\n")
        batch_log.flush()

        for case in cases:
            case["status"] = "running"
            case["started_at"] = now_iso()
            case["current_step"] = "starting"
            write_json(status_path, batch_payload(args.batch_id, started_at, cases, "running"))
            append_summary(batch_run_dir, cases)

            run_dir = Path(case["run_dir"])
            run_dir.mkdir(parents=True, exist_ok=True)
            stdout_path = run_dir / "run.log"
            cmd = [
                sys.executable,
                str(root / "run_simulation.py"),
                str(root / case["scenario"]),
                "--loops",
                str(args.loops),
                "--max-loops",
                str(args.loops),
                "--profile",
                args.profile,
                "--timeout",
                str(args.timeout),
                "--enable-monitor",
                "--out",
                str(run_dir),
                "--keep-runs",
                "0",
            ]
            if args.dry_run:
                cmd.append("--dry-run")

            print(f"[case {case['index']:02d}] start {case['slug']}", flush=True)
            batch_log.write(f"[{now_iso()}] start {case['slug']}\n")
            batch_log.flush()

            with stdout_path.open("a", encoding="utf-8") as stdout_log:
                proc = subprocess.Popen(
                    cmd,
                    cwd=root,
                    stdout=stdout_log,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                while proc.poll() is None:
                    update_from_child_status(case)
                    write_json(status_path, batch_payload(args.batch_id, started_at, cases, "running"))
                    append_summary(batch_run_dir, cases)
                    time.sleep(args.poll_seconds)
                return_code = proc.returncode

            case["return_code"] = return_code
            update_from_child_status(case)
            if return_code == 0:
                audit_path = run_dir / "audit.log"
                audit = subprocess.run(
                    [sys.executable, str(root / "audit_run.py"), str(run_dir), "--write"],
                    cwd=root,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )
                audit_path.write_text(audit.stdout, encoding="utf-8")
                update_from_metrics(case)
                case["audit_return_code"] = audit.returncode
                case["status"] = "done" if audit.returncode == 0 and case.get("audit_passed") else "failed"
                case["current_step"] = "audit passed" if case["status"] == "done" else "audit failed"
            else:
                case["status"] = "failed"
                case["current_step"] = f"run failed with code {return_code}"

            case["completed_at"] = now_iso()
            write_json(status_path, batch_payload(args.batch_id, started_at, cases, "running"))
            append_summary(batch_run_dir, cases)
            print(
                f"[case {case['index']:02d}] {case['status']} calls={case.get('call_count', 0)} "
                f"tokens={case.get('total_tokens', 0)} errors={case.get('error_count', 0)}",
                flush=True,
            )
            batch_log.write(f"[{now_iso()}] {case['status']} {case['slug']}\n")
            batch_log.flush()

            if case["status"] != "done" and args.stop_on_error:
                break

    final_status = "done" if all(item.get("status") == "done" for item in cases) else "failed"
    write_json(status_path, batch_payload(args.batch_id, started_at, cases, final_status))
    append_summary(batch_run_dir, cases)
    print(f"[batch] {final_status} summary={batch_run_dir / 'SUMMARY.md'}", flush=True)
    return 0 if final_status == "done" else 1


if __name__ == "__main__":
    raise SystemExit(main())
