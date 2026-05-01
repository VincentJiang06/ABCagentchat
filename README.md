# ABCagentchat

ABCagentchat is an open-ended deliberation simulator for testing long-running multi-agent discussion. It focuses on whether a simulated meeting can preserve facts, respect authority boundaries, surface political and governance tradeoffs, keep strong disagreement visible, rotate perspectives when useful, and produce auditable reports.

The current scenario set is mostly social governance and public-service deliberation, with one university scenario as a control case. All organizations, characters, meetings, budgets, and decisions are fictionalized.

## Runtime Model Strategy

- Coordinator calls use `deepseek-v4-pro` with thinking enabled and `reasoning_effort=max`.
- Role A/B/C/D calls use `deepseek-v4-flash` with thinking enabled and `reasoning_effort=high`.
- Compact, planning, compact-archive, stage-report, and final-summary calls explicitly request `reasoning_effort=max` and use large output ceilings so the coordinator can keep richer context and produce more careful visible analysis.
- The DeepSeek chat API is stateless, so every role subcycle explicitly sends accumulated `messages`: the shared background is placed once in the subcycle system prompt, while later role calls include short role/task prompts plus previous assistant outputs from completed rounds in the same subcycle.
- Role discussion is round-parallel by default. In each subcycle, A/B/C/D speak at the same time from the same frozen context; after all four finish, their outputs are appended in A/B/C/D order before the next round starts. The default subcycle has three discussion rounds plus a fourth role-summary round.
- Planning is encouraged to rotate the A/B/C/D perspective cards across loops instead of keeping four fixed personas forever. If a perspective continues across loops, the plan should explain why that perspective still adds a necessary conflict, evidence memory, or value position.
- Prompts emphasize abstract problem framing, strong opposing views, steelmanning, minority positions, and irreducible disagreement. They avoid treating every discussion as if it already produced a clean result.
- Cross-loop background injects the original issue plus a gradient compact archive: the latest four loop compacts in full, older compacts as decreasing excerpts, and a max-effort rolling open-discussion ledger summary for the oldest material. For example, loop 10 receives the original issue, a max-effort summary of earlier loops, compact excerpts that shrink with distance, and full compacts from loops 6-9 before new roles start their three-round discussion.
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
python3 run_simulation.py scenarios/11_university_evening_self_study.md --loops 10 --dry-run --out runs/dry-10-check
```

Useful controls:

```bash
--max-loops 10
--max-subcycles 3
--rounds-per-subcycle 3
--no-summary-round
--recent-context-chars 32000
--role-max-tokens 4096
--coordinator-max-tokens 65536
--stage-max-tokens 65536
--final-max-tokens 65536
--enable-monitor
```

## Output Layout

Each run writes a local directory under `runs/`:

```text
input.md
run_config.json
transcript.jsonl
metrics.json
run_index.md
compact_archive_summary.md   # created once older compacts are summarized
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
    discussion_round_04.jsonl  # role self-summary and remaining doubts
  stage_report.md
final_summary.md
final/
  final_summary.md
  process_timeline.md
  output_tree.md
```

The default reading surface is Markdown plus JSONL. Web monitoring is paused by default; pass `--enable-monitor` only if you explicitly want `monitor.html` and `status.json`.

## Architecture

- `api.py`: DeepSeek payload construction, thinking mode, request metadata, response parsing.
- `background.py`: original issue, gradient compact archive, previous reports, and bounded recent-history context.
- `compact.py`: loop compact messages; compact output is treated as a persistent open-discussion state ledger.
- `planning.py`: subcycle and rotating perspective design JSON parsing/rendering.
- `conversation.py`: explicit multi-round `messages` stitching.
- `roles.py`: round-parallel role calls and per-round JSONL records.
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
python3 audit_run.py runs/dry-10-check --write
```

The audit checks expected files, call counts, role coverage, errors, length stops, and empty previews.

## Deep Final Summary

After a full run completes, build a max-context evidence bundle and ask the coordinator model to produce a stronger final synthesis:

```bash
python3 summarize_run.py runs/case-real-evening-self-study-5loop --context-chars 900000 --max-output-tokens 65536
```

Dry-run the packer without calling the model:

```bash
python3 summarize_run.py runs/case-real-evening-self-study-5loop --dry-run
```

This writes:

```text
deep_summary/context_bundle.md
deep_summary/manifest.json
deep_summary/transcript.jsonl
deep_summary/final_package/index.md
deep_summary/final_package/00_raw_model_output.md
deep_summary/final_package/01_discussion_result.md
deep_summary/final_package/02_process_analysis.md
deep_summary/final_package/03_synthesized_document.md
deep_summary/final_package/manifest.json
deep_final_summary.md              # raw tagged model output for audit/debug
```

The bundle prioritizes original scenario/config/metrics, run index files, all loop compacts, all stage reports, discussion plans, fourth-round role self-summaries, then raw role rounds. The final package is split into three reader-facing documents: the deliberation result landscape, an objective process analysis, and a synthesized source document suitable for reading or filing. Use `--include-background` only when you explicitly want generated `background_context.md` files included; they are usually redundant and very large.
