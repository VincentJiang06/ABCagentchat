from __future__ import annotations

import json
import os
import signal
import time
from datetime import datetime
from pathlib import Path
from typing import Any


CONTROL_FILENAME = "batch_control.json"
STATUS_FILENAME = "batch_status.json"


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


def control_path(batch_root: Path) -> Path:
    return batch_root / CONTROL_FILENAME


def status_path(batch_root: Path) -> Path:
    return batch_root / STATUS_FILENAME


def request_stop(batch_root: Path, *, reason: str = "requested", stop_monitor: bool = True) -> dict[str, Any]:
    requested_at = now_iso()
    control = read_json(control_path(batch_root))
    control.update(
        {
            "stop_requested": True,
            "stop_reason": reason,
            "stop_requested_at": requested_at,
            "stop_monitor": stop_monitor,
        }
    )
    write_json(control_path(batch_root), control)

    status = read_json(status_path(batch_root))
    if status:
        status.update(
            {
                "stop_requested": True,
                "stop_reason": reason,
                "stop_requested_at": requested_at,
                "updated_at": requested_at,
            }
        )
        write_json(status_path(batch_root), status)
    return control


def process_alive(pid: int | str | None) -> bool:
    try:
        value = int(pid or 0)
    except (TypeError, ValueError):
        return False
    if value <= 0:
        return False
    try:
        os.kill(value, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _wait_dead_pgid(pgid: int, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        time.sleep(0.1)
    try:
        os.killpg(pgid, 0)
        return False
    except ProcessLookupError:
        return True


def terminate_pgid(pgid: int | str | None, *, timeout: float = 5.0) -> dict[str, Any]:
    try:
        value = int(pgid or 0)
    except (TypeError, ValueError):
        return {"pgid": pgid, "action": "skipped", "reason": "invalid_pgid"}
    if value <= 0:
        return {"pgid": value, "action": "skipped", "reason": "invalid_pgid"}
    if value == os.getpgrp():
        return {"pgid": value, "action": "skipped", "reason": "current_process_group"}
    try:
        os.killpg(value, signal.SIGTERM)
    except ProcessLookupError:
        return {"pgid": value, "action": "already_dead"}
    except PermissionError as exc:
        return {"pgid": value, "action": "error", "error": str(exc)}
    if _wait_dead_pgid(value, timeout):
        return {"pgid": value, "action": "terminated"}
    try:
        os.killpg(value, signal.SIGKILL)
    except ProcessLookupError:
        return {"pgid": value, "action": "terminated_after_term"}
    except PermissionError as exc:
        return {"pgid": value, "action": "error", "error": str(exc)}
    return {"pgid": value, "action": "killed"}


def mark_running_cases_stopped(batch_root: Path, *, reason: str) -> dict[str, Any]:
    status = read_json(status_path(batch_root))
    if not status:
        return {}
    stopped_at = now_iso()
    for case in status.get("cases") or []:
        if str(case.get("status") or "").lower() in {"running", "starting", "pending"}:
            case["status"] = "stopped"
            case["current_step"] = reason
            case["completed_at"] = stopped_at
            case["updated_at"] = stopped_at
    status.update(
        {
            "status": "stopped",
            "stop_requested": True,
            "stop_reason": reason,
            "updated_at": stopped_at,
            "running_case": "",
            "running_cases": [],
        }
    )
    write_json(status_path(batch_root), status)
    return status


def stop_from_status(
    batch_root: Path,
    *,
    stop_monitor: bool = True,
    include_batch: bool = True,
    timeout: float = 5.0,
) -> dict[str, Any]:
    status = read_json(status_path(batch_root))
    results: list[dict[str, Any]] = []
    seen_pgids: set[int] = set()

    for case in status.get("cases") or []:
        case_status = str(case.get("status") or "").lower()
        if case_status not in {"running", "starting"}:
            continue
        try:
            pgid = int(case.get("pgid") or 0)
        except (TypeError, ValueError):
            pgid = 0
        if pgid and pgid not in seen_pgids:
            seen_pgids.add(pgid)
            results.append({"target": case.get("slug"), **terminate_pgid(pgid, timeout=timeout)})

    if include_batch:
        try:
            batch_pgid = int(status.get("batch_pgid") or 0)
        except (TypeError, ValueError):
            batch_pgid = 0
        if batch_pgid and batch_pgid not in seen_pgids:
            results.append({"target": "batch", **terminate_pgid(batch_pgid, timeout=timeout)})

    if stop_monitor:
        try:
            monitor_pgid = int(status.get("monitor_pgid") or 0)
        except (TypeError, ValueError):
            monitor_pgid = 0
        if monitor_pgid and monitor_pgid not in seen_pgids:
            results.append({"target": "monitor", **terminate_pgid(monitor_pgid, timeout=timeout)})

    updated = mark_running_cases_stopped(batch_root, reason="stopped by request")
    return {"status": updated.get("status") or "", "results": results}
