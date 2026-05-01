# Block Test Report

Date: 2026-05-01

## Scope

This report covers the architecture re-check and block testing pass after the first complex real API run.

## Architecture Status

The base architecture is complete for the current milestone:

- `run_simulation.py`: CLI entrypoint.
- `abcagentchat/config.py`: `.env` and five-key configuration.
- `abcagentchat/api.py`: DeepSeek chat-completions client.
- `abcagentchat/scenario.py`: Markdown scenario/frontmatter loader.
- `abcagentchat/prompts.py`: coordinator and role prompts.
- `abcagentchat/simulator.py`: compact, persona generation, 3-round discussion, stage report, final summary.
- `abcagentchat/gc.py`: context and run-directory garbage collection helpers.
- `abcagentchat/metrics.py`: run metrics and artifact audit.
- `audit_run.py`: CLI audit for existing run directories.
- `tests/test_blocks.py`: block-level tests.

## Issues Found And Closed

| Issue | Root Cause | Fix |
|---|---|---|
| No machine-readable run metrics | Metrics only existed in `transcript.jsonl` and manual reports | Added `metrics.json`, `abcagentchat/metrics.py`, and `audit_run.py` |
| No block tests | Previous validation relied on dry-run commands | Added parser, utility, GC, dry-run integration, and audit failure tests |
| Test output too noisy | Dry-run integration printed full progress into test output | Suppressed simulator stdout inside the unit test |
| GC test had weak ordering | Directory mtimes were implicit | Set explicit mtimes and assert the old directory is removed |
| Long-run observability risk | Real API output could buffer until process completion | Simulator progress prints now use `flush=True` |

## Verification Results

Commands run:

```bash
python3 -m py_compile run_simulation.py audit_run.py abcagentchat/*.py tests/test_blocks.py
python3 -m unittest -v tests/test_blocks.py
python3 audit_run.py runs/real-complex-platform-worker-rights --write
python3 run_simulation.py scenarios/02_old_community_elevator.md --loops 1 --dry-run --out runs/block-dry-elevator
python3 audit_run.py runs/block-dry-elevator
```

Results:

- Compile: pass.
- Unit/block tests: 7/7 pass.
- Scenario structure audit: 10/10 scenarios have required metadata and sections.
- Real complex run audit: pass.
- Fresh dry-run audit: pass.

## Metrics Checks Now Enforced

Each completed run now checks:

- expected files exist,
- no API error log is present,
- transcript call count matches the loop count,
- every discussion round has exactly four role entries,
- no call stopped by length,
- every call has a non-empty content preview.

## Remaining Engineering Risks

- There is still no real API scoring harness for semantic quality; current audit verifies structure and operational health.
- No Git repository has been initialized in `/Users/vincent/playground/ABCagentchat` yet, so version control/push is not complete.
- The default high-quality Pro/max settings are expensive and slow; add a fast preset before large-scale batch testing.

