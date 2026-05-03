#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from abcagentchat.api import DeepSeekClient
from abcagentchat.config import AppConfig
from abcagentchat.deep_summary import (
    DEFAULT_DEEP_CONTEXT_CHARS,
    DEFAULT_PACKAGE_DIR,
    DEFAULT_DEEP_SUMMARY_MAX_TOKENS,
    append_deep_summary_transcript,
    build_context_bundle,
    deep_final_summary_messages,
    write_deep_summary_package,
    write_context_bundle,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and run a max-context final summary for an existing run.")
    parser.add_argument("run_dir", type=Path, help="Existing run directory, e.g. runs/case-real-evening-self-study-5loop")
    parser.add_argument(
        "--context-chars",
        type=int,
        default=DEFAULT_DEEP_CONTEXT_CHARS,
        help="Maximum characters packed into the final-summary context bundle. Use 0 for unlimited.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=DEFAULT_DEEP_SUMMARY_MAX_TOKENS,
        help="Maximum tokens for the deep final summary completion.",
    )
    parser.add_argument("--timeout", type=int, default=900, help="Per-request timeout in seconds.")
    parser.add_argument("--dry-run", action="store_true", help="Only write the context bundle and manifest; do not call the model.")
    parser.add_argument(
        "--include-background",
        action="store_true",
        help="Also include generated background_context.md files. Usually redundant and very large.",
    )
    parser.add_argument("--output", default="final summary/deep_final_summary.md", help="Output filename inside the run directory.")
    parser.add_argument(
        "--package-dir",
        default=DEFAULT_PACKAGE_DIR,
        help="Directory inside the run directory for split deep-summary deliverables.",
    )
    return parser.parse_args()


def main() -> int:
    root = Path(__file__).resolve().parent
    args = parse_args()
    run_dir = args.run_dir.resolve()
    if not run_dir.exists():
        raise SystemExit(f"Run directory does not exist: {run_dir}")

    max_chars = None if args.context_chars == 0 else args.context_chars
    bundle = build_context_bundle(run_dir, max_chars=max_chars, include_background=args.include_background)
    bundle_path, manifest_path = write_context_bundle(run_dir, bundle)
    print(f"[deep-summary] bundle={bundle_path}")
    print(f"[deep-summary] manifest={manifest_path}")
    print(
        "[deep-summary] "
        f"artifacts={bundle.manifest['artifact_count']} "
        f"included_chars={bundle.manifest['included_chars']} "
        f"estimated_tokens={bundle.manifest['estimated_included_tokens']}"
    )

    if args.dry_run:
        print("[deep-summary] dry-run; model call skipped")
        return 0

    config = AppConfig.from_env(root, timeout=args.timeout)
    client = DeepSeekClient(config.coordinator_key, config.coordinator_settings)
    result = client.chat(
        deep_final_summary_messages(bundle.text),
        max_tokens=args.max_output_tokens,
        temperature=0.5,
        reasoning_effort="max",
    )
    package_manifest = write_deep_summary_package(
        run_dir,
        result.content,
        package_dir=args.package_dir,
        raw_output=args.output,
    )
    request_meta = client.request_meta(max_tokens=args.max_output_tokens, temperature=0.5, reasoning_effort="max")
    append_deep_summary_transcript(run_dir, request_meta, result)
    print(
        "[deep-summary] "
        f"package={package_manifest['package_dir']} "
        f"raw_output={run_dir / args.output} "
        f"complete_sections={package_manifest['complete_sections']} "
        f"tokens={result.total_tokens} "
        f"finish_reason={result.finish_reason}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
