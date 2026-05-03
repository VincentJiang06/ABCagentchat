#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from abcagentchat.metrics import audit_run_dir, write_metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit an ABCagentchat run directory.")
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--write", action="store_true", help="Write process/metrics.json into the run directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    metrics = write_metrics(run_dir) if args.write else audit_run_dir(run_dir)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0 if metrics["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
