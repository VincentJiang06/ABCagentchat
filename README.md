# ABCagentchat

ABCagentchat is a proposal-deliberation simulator for testing long-running multi-agent discussion. It focuses on whether a simulated meeting can preserve facts, respect authority boundaries, surface political and governance tradeoffs, revise proposals, and produce executable reports.

The current scenario set is mostly social governance and public-service deliberation, with one university scenario as a control case. All organizations, characters, meetings, budgets, and decisions are fictionalized.

## Runtime Model Strategy

- Coordinator calls use `deepseek-v4-pro` with thinking enabled and `reasoning_effort=max`.
- Role A/B/C/D calls use `deepseek-v4-pro` with thinking disabled.
- The DeepSeek chat API is stateless, so every role subcycle explicitly sends accumulated `messages`: later role calls include previous user prompts and assistant outputs from the same subcycle.
- Cross-loop background injects the original issue plus every previous loop compact. For example, loop 10 receives the original issue and compact results from loops 1-9 before new roles start their three-round discussion.
- Recent raw discussion is still bounded by `--recent-context-chars` to avoid unbounded transcript growth.

## Run

Create `.env` with the five keys:

```env
DEEPSEEK_COORDINATOR_KEY=...
DEEPSEEK_ROLE_A_KEY=...
DEEPSEEK_ROLE_B_KEY=...
DEEPSEEK_ROLE_C_KEY=...
DEEPSEEK_ROLE_D_KEY=...
```

Run a scenario:

```bash
python3 run_simulation.py scenarios/11_university_evening_self_study.md --loops 3
```

Dry-run without API calls:

```bash
python3 run_simulation.py scenarios/11_university_evening_self_study.md --loops 100 --dry-run --out runs/dry-100-check
```

Useful controls:

```bash
--max-loops 100
--max-subcycles 3
--rounds-per-subcycle 3
--recent-context-chars 32000
--role-max-tokens 4096
--enable-monitor
```

## Output Layout

Each run writes a local directory under `runs/`:

```text
input.md
run_config.json
transcript.jsonl
metrics.json
loop_01/
  background_context.md
  compact.md
  discussion_plan.raw.json
  discussion_plan.json
  discussion_plan.md
  subcycle_01_a/
    discussion_round_01.jsonl
    discussion_round_02.jsonl
    discussion_round_03.jsonl
  stage_report.md
final_summary.md
```

The default reading surface is Markdown plus JSONL. Web monitoring is paused by default; pass `--enable-monitor` only if you explicitly want `monitor.html` and `status.json`.

## Architecture

- `api.py`: DeepSeek payload construction, thinking mode, request metadata, response parsing.
- `background.py`: original issue, historical compact archive, previous reports, and bounded recent-history context.
- `compact.py`: loop compact messages.
- `planning.py`: subcycle and role design JSON parsing/rendering.
- `conversation.py`: explicit multi-round `messages` stitching.
- `roles.py`: role calls and per-round JSONL records.
- `reports.py`: stage reports and final summary messages.
- `orchestrator.py`: main loop orchestration.
- `monitor.py`: minimal local status dashboard.
- `metrics.py`: artifact and transcript audit.

See `DEBUG_PLAN.md` for a module-by-module manual inspection plan.

## Test And Audit

Run tests:

```bash
python3 -m unittest -v tests/test_blocks.py
```

Audit a run:

```bash
python3 audit_run.py runs/dry-100-check --write
```

The audit checks expected files, call counts, role coverage, errors, length stops, and empty previews.
