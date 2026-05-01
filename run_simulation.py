#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from abcagentchat.config import AppConfig
from abcagentchat.scenario import load_scenario
from abcagentchat.simulator import RunOptions, Simulator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a multi-agent proposal deliberation simulation.")
    parser.add_argument("scenario", nargs="?", help="Path to a scenario Markdown file.")
    parser.add_argument("--loops", type=int, help="Override scenario loop count.")
    parser.add_argument("--out", type=Path, help="Output directory for this run.")
    parser.add_argument("--keep-runs", type=int, default=10, help="Keep only the newest N auto-created runs.")
    parser.add_argument("--timeout", type=int, default=600, help="Per-request timeout in seconds.")
    parser.add_argument("--dry-run", action="store_true", help="Run without network/API calls.")
    parser.add_argument("--recent-context-chars", type=int, default=32000)
    parser.add_argument("--max-loops", type=int, default=10, help="Hard cap for discussion loops.")
    parser.add_argument("--max-subcycles", type=int, default=3, help="Maximum discussion subcycles per loop.")
    parser.add_argument("--rounds-per-subcycle", type=int, default=3, help="Role speaking rounds per subcycle.")
    parser.add_argument("--no-summary-round", action="store_true", help="Disable the fourth parallel role summary round.")
    parser.add_argument("--enable-monitor", action="store_true", help="Write monitor.html/status.json. Disabled by default.")
    parser.add_argument(
        "--profile",
        choices=["quality", "long-run"],
        default="quality",
        help="quality keeps large token ceilings; long-run uses smaller ceilings for many-loop runs.",
    )
    parser.add_argument("--coordinator-max-tokens", type=int)
    parser.add_argument("--role-max-tokens", type=int)
    parser.add_argument("--stage-max-tokens", type=int)
    parser.add_argument("--final-max-tokens", type=int)
    return parser.parse_args()


def main() -> int:
    root = Path(__file__).resolve().parent
    args = parse_args()
    if not args.scenario:
        print("Available scenarios:")
        for path in sorted((root / "scenarios").glob("*.md")):
            print(f"  {path}")
        return 0

    scenario = load_scenario(Path(args.scenario).resolve(), loops_override=args.loops)
    profile_defaults = {
        "quality": {
            "coordinator_max_tokens": None,
            "role_max_tokens": None,
            "stage_max_tokens": None,
            "final_max_tokens": None,
        },
        "long-run": {
            "coordinator_max_tokens": 65536,
            "role_max_tokens": 4096,
            "stage_max_tokens": 65536,
            "final_max_tokens": 65536,
        },
    }[args.profile]
    options = RunOptions(
        output_dir=args.out.resolve() if args.out else None,
        keep_runs=args.keep_runs,
        dry_run=args.dry_run,
        timeout=args.timeout,
        recent_context_chars=args.recent_context_chars,
        max_loops=args.max_loops,
        max_subcycles=args.max_subcycles,
        rounds_per_subcycle=args.rounds_per_subcycle,
        role_summary_round=not args.no_summary_round,
        coordinator_max_tokens=args.coordinator_max_tokens or profile_defaults["coordinator_max_tokens"],
        role_max_tokens=args.role_max_tokens or profile_defaults["role_max_tokens"],
        stage_max_tokens=args.stage_max_tokens or profile_defaults["stage_max_tokens"],
        final_max_tokens=args.final_max_tokens or profile_defaults["final_max_tokens"],
        enable_monitor=args.enable_monitor,
    )
    config = None if args.dry_run else AppConfig.from_env(root, timeout=args.timeout)
    simulator = Simulator(root=root, config=config, options=options)
    simulator.run(scenario)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
