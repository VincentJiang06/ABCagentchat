#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from abcagentchat.batch_control import now_iso, request_stop, status_path, stop_from_status, read_json, write_json


class MonitorHandler(SimpleHTTPRequestHandler):
    batch_root: Path
    serve_root: Path

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(self.serve_root), **kwargs)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/api/stop-batch":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "unknown endpoint"})
            return
        request_stop(self.batch_root, reason="monitor stop button", stop_monitor=True)
        result = stop_from_status(self.batch_root, stop_monitor=True, include_batch=True)
        self._send_json(HTTPStatus.OK, result)
        threading.Thread(target=self.server.shutdown, daemon=True).start()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve ABCagentchat monitor files with a stop-batch API.")
    parser.add_argument("--root", type=Path, default=Path("runs/nightly-all-tests"), help="Batch root used by the stop API.")
    parser.add_argument("--serve-root", type=Path, default=Path("."), help="Filesystem root served over HTTP.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def monitor_url_for(batch_root: Path, serve_root: Path, *, host: str, port: int) -> str:
    try:
        rel = batch_root.resolve().relative_to(serve_root.resolve())
        path = "/".join(rel.parts + ("monitor.html",))
    except ValueError:
        path = "monitor.html"
    return f"http://{host}:{port}/{path}"


def record_monitor_metadata(batch_root: Path, serve_root: Path, *, host: str, port: int) -> None:
    status = read_json(status_path(batch_root))
    status.update(
        {
            "monitor_pid": os.getpid(),
            "monitor_pgid": os.getpgrp(),
            "monitor_url": monitor_url_for(batch_root, serve_root, host=host, port=port),
            "monitor_server": "serve_monitor.py",
            "updated_at": now_iso(),
        }
    )
    write_json(status_path(batch_root), status)


def main() -> int:
    repo_root = Path(__file__).resolve().parent
    args = parse_args()
    batch_root = (repo_root / args.root).resolve() if not args.root.is_absolute() else args.root.resolve()
    serve_root = (repo_root / args.serve_root).resolve() if not args.serve_root.is_absolute() else args.serve_root.resolve()
    batch_root.mkdir(parents=True, exist_ok=True)
    record_monitor_metadata(batch_root, serve_root, host=args.host, port=args.port)

    handler = type(
        "ABCMonitorHandler",
        (MonitorHandler,),
        {"batch_root": batch_root, "serve_root": serve_root},
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"[monitor-server] {monitor_url_for(batch_root, serve_root, host=args.host, port=args.port)} serve_root={serve_root} batch_root={batch_root}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
