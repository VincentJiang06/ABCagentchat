# ABCagentchat

ABCagentchat is a proposal-deliberation testbed. The first milestone is a set of Markdown scenarios for testing whether multi-agent discussion can preserve facts, respect procedural limits, surface stakeholder tradeoffs, revise proposals, and produce executable recommendations.

This repository currently focuses on **social proposal deliberation**, not student-union-only simulation. The first scenario set uses a 90/10 split:

- 9 scenarios adapted from public Chinese urban governance, community governance, public service, and association-style policy topics.
- 1 university scenario as a lightweight control case.

All scenarios are fictionalized. Source links are provided for traceability, but organizations, characters, budgets, meetings, and decisions are simulated.

## Scenario Format

Each file in `scenarios/` uses this structure:

```markdown
---
title: ...
loops: 2
domain: ...
source_refs:
  - title: ...
    url: ...
primary_tests:
  - fact_retention
  - procedural_boundary
---

# 真实议题来源摘要

# 虚构化场景设定

# 初始讨论内容

# 已知硬约束

# 争议焦点

# 四类角色建议方向

# 期望观察点
```

## Scenario Set

1. `01_ebike_charging_governance.md`
2. `02_old_community_elevator.md`
3. `03_complete_community_priorities.md`
4. `04_platform_worker_rights.md`
5. `05_community_eldercare_station.md`
6. `06_primary_health_chronic_disease.md`
7. `07_property_service_supervision.md`
8. `08_urban_underground_space.md`
9. `09_embedded_community_services.md`
10. `10_university_ai_academic_integrity.md`

## Deliberation Boundaries

Simulations should explicitly distinguish:

- What the fictional meeting can decide.
- What must be submitted to a competent authority, owners' assembly, industry association, platform enterprise, or school authority.
- Which source facts are hard constraints rather than negotiable preferences.

## Run The Simulator

Create a local `.env` from `.env.example`:

```bash
cp .env.example .env
```

Fill in:

```env
DEEPSEEK_COORDINATOR_KEY=...
DEEPSEEK_ROLE_A_KEY=...
DEEPSEEK_ROLE_B_KEY=...
DEEPSEEK_ROLE_C_KEY=...
DEEPSEEK_ROLE_D_KEY=...
```

Run one scenario:

```bash
python3 run_simulation.py scenarios/01_ebike_charging_governance.md
```

Override loop count:

```bash
python3 run_simulation.py scenarios/01_ebike_charging_governance.md --loops 1
```

Run a long simulation with smaller token ceilings:

```bash
python3 run_simulation.py scenarios/11_university_evening_self_study.md --loops 50 --profile long-run
```

Run without API calls to verify local file generation:

```bash
python3 run_simulation.py scenarios/01_ebike_charging_governance.md --loops 1 --dry-run
```

Outputs are written under `runs/<timestamp>-<title>/` by default:

```text
input.md
run_config.json
transcript.jsonl
loop_01/
  compact.md
  personas.raw.json
  personas.json
  personas.md
  discussion_round_01.jsonl
  discussion_round_02.jsonl
  discussion_round_03.jsonl
  stage_report.md
final_summary.md
```

## Runtime Design

- Coordinator key handles compact, persona generation, stage reports, and final summary.
- Role A/B/C/D keys are fixed to the four generated roles.
- Role calls run sequentially so the terminal output is easy to inspect.
- Reasoning content is never written back into context; only visible output is stored and reused.
- Context garbage collection keeps recent discussion text bounded while preserving full local artifacts.
- Local run garbage collection keeps the newest 10 runs by default; change with `--keep-runs`.
- Every run writes `metrics.json` with artifact checks, call counts, token totals, length-stop counts, and per-role round coverage.
- `--profile long-run` keeps the same workflow but lowers token ceilings for many-loop runs.

## Testing And Auditing

Run the block test suite:

```bash
python3 -m unittest -v tests/test_blocks.py
```

Audit an existing run:

```bash
python3 audit_run.py runs/real-complex-platform-worker-rights --write
```

The audit passes only when:

- all expected run files exist,
- all three discussion rounds have exactly four role entries,
- the transcript call count matches the loop count,
- there are no recorded API errors,
- no call stopped because of output length,
- every transcript entry has a non-empty preview.
