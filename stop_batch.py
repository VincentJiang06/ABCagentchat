#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from abcagentchat.batch_control import request_stop, stop_from_status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stop the current ABCagentchat batch run and its active child cases.")
    parser.add_argument("--batch-root", type=Path, default=Path("runs/nightly-all-tests"))
    parser.add_argument("--reason", default="manual stop")
    parser.add_argument("--keep-monitor", action="store_true", help="Do not stop the monitor server process.")
    parser.add_argument("--timeout", type=float, default=5.0)
    return parser.parse_args()


def main() -> int:
    root = Path(__file__).resolve().parent
    args = parse_args()
    batch_root = (root / args.batch_root).resolve() if not args.batch_root.is_absolute() else args.batch_root.resolve()
    stop_monitor = not args.keep_monitor
    request_stop(batch_root, reason=args.reason, stop_monitor=stop_monitor)
    result = stop_from_status(batch_root, stop_monitor=stop_monitor, include_batch=True, timeout=args.timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
