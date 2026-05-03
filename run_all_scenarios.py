#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from abcagentchat.batch_control import (
    control_path,
    now_iso,
    read_json,
    request_stop,
    status_path,
    terminate_pgid,
    write_json,
)
from abcagentchat.layout import framework_root, process_root
from abcagentchat.monitor import MONITOR_HTML
from abcagentchat.scenario import load_scenario


def cert_file() -> str:
    if os.environ.get("SSL_CERT_FILE"):
        return os.environ["SSL_CERT_FILE"]
    try:
        import certifi  # type: ignore

        return certifi.where()
    except Exception:
        pass
    for candidate in (
        "/Library/Frameworks/Python.framework/Versions/3.12/lib/python3.12/site-packages/certifi/cacert.pem",
        "/opt/homebrew/lib/python3.11/site-packages/certifi/cacert.pem",
    ):
        if Path(candidate).exists():
            return candidate
    return ""


def child_env() -> dict[str, str]:
    env = os.environ.copy()
    cert = cert_file()
    if cert:
        env.setdefault("SSL_CERT_FILE", cert)
        env.setdefault("REQUESTS_CA_BUNDLE", cert)
    return env


def scenario_index(path: Path) -> int:
    prefix = path.stem.split("_", 1)[0]
    try:
        return int(prefix)
    except ValueError:
        return 9999


def make_case(path: Path, batch_run_dir: Path, *, loops: int) -> dict[str, Any]:
    scenario = load_scenario(path, loops_override=loops)
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
        "updated_at",
    ):
        if key in status:
            case[key] = status[key]


def update_from_metrics(case: dict[str, Any]) -> None:
    metrics = read_json(process_root(Path(case["run_dir"])) / "metrics.json")
    transcript = metrics.get("transcript") or {}
    if transcript:
        case["call_count"] = transcript.get("call_count", case.get("call_count", 0))
        case["total_tokens"] = transcript.get("total_tokens", case.get("total_tokens", 0))
    case["audit_passed"] = bool(metrics.get("passed")) if metrics else False
    case["audit_strict_passed"] = bool(metrics.get("strict_passed")) if metrics else False
    case["audit_warning_count"] = int(metrics.get("warning_count") or 0) if metrics else 0
    case["audit_warnings"] = metrics.get("warnings") or []


def append_summary(batch_run_dir: Path, cases: list[dict[str, Any]]) -> None:
    lines = [
        "# ABCagentchat Batch Run",
        "",
        f"- Batch: `{batch_run_dir.name}`",
        f"- Updated: {now_iso()}",
        f"- Total cases: {len(cases)}",
        "",
        "| # | Status | Scenario | Calls | Tokens | Errors | PID | PGID |",
        "|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for case in cases:
        lines.append(
            "| {index} | {status} | `{slug}` | {calls} | {tokens} | {errors} | {pid} | {pgid} |".format(
                index=case.get("index", ""),
                status=case.get("status", ""),
                slug=case.get("slug", ""),
                calls=case.get("call_count", 0) or 0,
                tokens=case.get("total_tokens", 0) or 0,
                errors=case.get("error_count", 0) or 0,
                pid=case.get("pid", "") or "",
                pgid=case.get("pgid", "") or "",
            )
        )
    path = framework_root(batch_run_dir) / "SUMMARY.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def batch_payload(
    batch_root: Path,
    *,
    batch_id: str,
    started_at: str,
    cases: list[dict[str, Any]],
    status: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    previous = read_json(status_path(batch_root))
    done = sum(1 for item in cases if item.get("status") in {"done", "completed_with_warnings"})
    warnings = sum(1 for item in cases if item.get("status") == "completed_with_warnings")
    failed = sum(1 for item in cases if item.get("status") in {"error", "failed"})
    stopped = sum(1 for item in cases if item.get("status") == "stopped")
    running = [item for item in cases if item.get("status") in {"running", "starting"}]
    payload = {
        "status": status,
        "batch_id": batch_id,
        "started_at": started_at,
        "updated_at": now_iso(),
        "total_cases": len(cases),
        "done_count": done,
        "warning_count": warnings,
        "failed_count": failed,
        "stopped_count": stopped,
        "running_case": running[0]["slug"] if running else "",
        "running_cases": [item["slug"] for item in running],
        "parallelism": args.parallel,
        "poll_seconds": args.poll_seconds,
        "stop_requested": bool((read_json(control_path(batch_root))).get("stop_requested")),
        "batch_pid": os.getpid(),
        "batch_pgid": os.getpgrp(),
        "cases": cases,
    }
    for key in ("monitor_pid", "monitor_pgid", "monitor_url", "monitor_server"):
        if key in previous:
            payload[key] = previous[key]
    return payload


def write_batch_status(
    batch_root: Path,
    batch_run_dir: Path,
    *,
    batch_id: str,
    started_at: str,
    cases: list[dict[str, Any]],
    status: str,
    args: argparse.Namespace,
) -> None:
    payload = batch_payload(batch_root, batch_id=batch_id, started_at=started_at, cases=cases, status=status, args=args)
    write_json(status_path(batch_root), payload)
    write_json(batch_run_dir / "batch_status.json", payload)
    append_summary(batch_run_dir, cases)


def build_case_command(root: Path, args: argparse.Namespace, case: dict[str, Any]) -> list[str]:
    cmd = [
        sys.executable,
        str(root / "run_simulation.py"),
        str(root / case["scenario"]),
        "--loops",
        str(args.loops),
        "--max-loops",
        str(args.loops),
        "--max-subcycles",
        str(args.max_subcycles),
        "--rounds-per-subcycle",
        str(args.rounds_per_subcycle),
        "--planning-max-tokens",
        str(args.planning_max_tokens),
        "--planning-context-chars",
        str(args.planning_context_chars),
        "--profile",
        args.profile,
        "--timeout",
        str(args.timeout),
        "--enable-monitor",
        "--out",
        str(Path(case["run_dir"])),
        "--keep-runs",
        "0",
    ]
    if args.summary_round and not args.no_summary_round:
        cmd.append("--summary-round")
    if args.dry_run:
        cmd.append("--dry-run")
    return cmd


def start_case(root: Path, args: argparse.Namespace, case: dict[str, Any], batch_log: Any) -> subprocess.Popen[str]:
    case["status"] = "starting"
    case["started_at"] = now_iso()
    case["updated_at"] = case["started_at"]
    case["current_step"] = "starting"
    run_dir = Path(case["run_dir"])
    run_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = process_root(run_dir) / "run.log"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_case_command(root, args, case)

    print(f"[case {case['index']:02d}] start {case['slug']}", flush=True)
    batch_log.write(f"[{now_iso()}] start {case['slug']}\n")
    batch_log.flush()

    stdout_log = stdout_path.open("a", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=root,
            env=child_env(),
            stdout=stdout_log,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
    finally:
        stdout_log.close()
    case["pid"] = proc.pid
    try:
        case["pgid"] = os.getpgid(proc.pid)
    except ProcessLookupError:
        case["pgid"] = proc.pid
    case["status"] = "running"
    case["current_step"] = "running"
    return proc


def finish_case(root: Path, case: dict[str, Any], return_code: int, *, stopping: bool, batch_log: Any) -> None:
    run_dir = Path(case["run_dir"])
    case["return_code"] = return_code
    update_from_child_status(case)
    if stopping:
        case["status"] = "stopped"
        case["current_step"] = "stopped by request"
    elif return_code == 0:
        audit_path = process_root(run_dir) / "audit.log"
        audit = subprocess.run(
            [sys.executable, str(root / "audit_run.py"), str(run_dir), "--write"],
            cwd=root,
            env=child_env(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        audit_path.write_text(audit.stdout, encoding="utf-8")
        update_from_metrics(case)
        case["audit_return_code"] = audit.returncode
        if audit.returncode == 0 and case.get("audit_passed"):
            case["status"] = "done" if not case.get("audit_warning_count") else "completed_with_warnings"
            case["current_step"] = "audit passed" if case["status"] == "done" else "completed with audit warnings"
        else:
            case["status"] = "failed"
            case["current_step"] = "audit failed"
    else:
        case["status"] = "failed"
        case["current_step"] = f"run failed with code {return_code}"

    case["completed_at"] = now_iso()
    case["updated_at"] = case["completed_at"]
    print(
        f"[case {case['index']:02d}] {case['status']} calls={case.get('call_count', 0)} "
        f"tokens={case.get('total_tokens', 0)} errors={case.get('error_count', 0)}",
        flush=True,
    )
    batch_log.write(f"[{now_iso()}] {case['status']} {case['slug']}\n")
    batch_log.flush()


def final_batch_status(cases: list[dict[str, Any]], *, stopping: bool) -> str:
    if stopping or any(item.get("status") == "stopped" for item in cases):
        return "stopped"
    terminal_ok = {"done", "completed_with_warnings"}
    if all(item.get("status") in terminal_ok for item in cases):
        if any(item.get("status") == "completed_with_warnings" for item in cases):
            return "completed_with_warnings"
        return "done"
    return "failed"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ABCagentchat scenarios with parallel batch monitoring.")
    parser.add_argument("--scenarios-dir", type=Path, default=Path("scenarios"))
    parser.add_argument("--out", type=Path, default=Path("runs/nightly-all-tests"))
    parser.add_argument("--batch-id", default=datetime.now().strftime("batch-%Y%m%d-%H%M%S"))
    parser.add_argument("--loops", type=int, default=3)
    parser.add_argument("--parallel", type=int, default=3)
    parser.add_argument("--profile", choices=["quality", "long-run"], default="long-run")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--max-subcycles", type=int, default=3)
    parser.add_argument("--rounds-per-subcycle", type=int, default=3)
    parser.add_argument("--summary-round", action="store_true", help="Enable the optional fourth role summary round.")
    parser.add_argument("--no-summary-round", action="store_true", help="Compatibility flag; summary rounds are disabled by default.")
    parser.add_argument("--planning-max-tokens", type=int, default=8192)
    parser.add_argument("--planning-context-chars", type=int, default=16000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument(
        "--enable-monitor",
        action="store_true",
        help="Compatibility flag; batch and case monitor pages are always generated.",
    )
    return parser.parse_args()


def main() -> int:
    root = Path(__file__).resolve().parent
    args = parse_args()
    args.parallel = max(1, int(args.parallel or 1))
    scenarios = sorted((root / args.scenarios_dir).glob("*.md"), key=scenario_index)
    if not scenarios:
        raise SystemExit(f"No scenarios found in {args.scenarios_dir}")

    batch_root = (root / args.out).resolve()
    batch_run_dir = batch_root / args.batch_id
    batch_run_dir.mkdir(parents=True, exist_ok=True)
    (batch_root / "monitor.html").write_text(MONITOR_HTML, encoding="utf-8")
    (batch_run_dir / "monitor.html").write_text(MONITOR_HTML, encoding="utf-8")
    write_json(control_path(batch_root), {"stop_requested": False, "updated_at": now_iso()})

    cases = [make_case(path, batch_run_dir, loops=args.loops) for path in scenarios]
    pending = list(cases)
    active: dict[subprocess.Popen[str], dict[str, Any]] = {}
    started_at = now_iso()
    stopping = False
    write_batch_status(batch_root, batch_run_dir, batch_id=args.batch_id, started_at=started_at, cases=cases, status="running", args=args)

    batch_log_path = process_root(batch_run_dir) / "batch.log"
    batch_log_path.parent.mkdir(parents=True, exist_ok=True)
    with batch_log_path.open("a", encoding="utf-8") as batch_log:
        print(
            f"[batch] id={args.batch_id} cases={len(cases)} parallel={args.parallel} out={batch_root}",
            flush=True,
        )
        batch_log.write(f"[{now_iso()}] batch start cases={len(cases)} parallel={args.parallel}\n")
        batch_log.flush()

        while pending or active:
            control = read_json(control_path(batch_root))
            if control.get("stop_requested") and not stopping:
                stopping = True
                batch_log.write(f"[{now_iso()}] stop requested: {control.get('stop_reason') or 'requested'}\n")
                batch_log.flush()
                for proc, case in list(active.items()):
                    case["current_step"] = "stopping"
                    terminate_pgid(case.get("pgid"), timeout=5.0)
                for case in pending:
                    case["status"] = "stopped"
                    case["current_step"] = "stopped before start"
                    case["completed_at"] = now_iso()
                pending.clear()

            while not stopping and pending and len(active) < args.parallel:
                case = pending.pop(0)
                proc = start_case(root, args, case, batch_log)
                active[proc] = case

            for proc, case in list(active.items()):
                return_code = proc.poll()
                if return_code is None:
                    update_from_child_status(case)
                    continue
                active.pop(proc)
                finish_case(root, case, int(return_code), stopping=stopping, batch_log=batch_log)
                if case["status"] not in {"done", "completed_with_warnings"} and args.stop_on_error and not stopping:
                    request_stop(batch_root, reason=f"stop-on-error: {case['slug']}", stop_monitor=False)

            write_batch_status(
                batch_root,
                batch_run_dir,
                batch_id=args.batch_id,
                started_at=started_at,
                cases=cases,
                status="stopping" if stopping and active else "running",
                args=args,
            )
            if active or pending:
                time.sleep(args.poll_seconds)

    final_status = final_batch_status(cases, stopping=stopping)
    write_batch_status(batch_root, batch_run_dir, batch_id=args.batch_id, started_at=started_at, cases=cases, status=final_status, args=args)
    print(f"[batch] {final_status} summary={framework_root(batch_run_dir) / 'SUMMARY.md'}", flush=True)
    return 0 if final_status in {"done", "completed_with_warnings"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
