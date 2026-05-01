# ABCagentchat Module Debug Plan

本计划用于逐块检查模块是否可用。建议先 dry-run，再做 1 loop 真实短测。

## 1. Scenario / Background

目标：确认原始议题和历史 compact 能稳定注入后续循环。

检查命令：

```bash
python3 run_simulation.py scenarios/11_university_evening_self_study.md --loops 2 --dry-run --out runs/debug-background --keep-runs 0
```

检查文件：

- `runs/debug-background/loop_01/background_context.md` 应包含原始议题，历史 compact 为空。
- `runs/debug-background/loop_02/background_context.md` 应包含原始议题和“第 1 个循环 compact”。
- 第 N 个循环应包含第 1 到 N-1 个循环的 compact。

通过标准：

- 原始议题没有丢失。
- 历史 compact 按循环顺序追加。
- 没有把三轮角色全文无限塞入跨循环背景，只保留 compact 和近期摘要。

## 2. Compact

目标：确认 compact 不只记录结论，也记录论证路径和政治/治理观点。

检查文件：

- `loop_XX/compact.md`

通过标准：

- 包含事实状态、程序红线、可决定事项、外部审批事项。
- 包含角色可见论证路径。
- 包含自治、秩序、效率、公平、专业责任、心理安全等治理取向冲突。
- 保留数字、门槛、时间点、责任主体。

## 3. Planning / Role Design

目标：确认每轮角色会基于当前 compact 和历史 compact 背景重新设计。

检查文件：

- `loop_XX/discussion_plan.raw.json`
- `loop_XX/discussion_plan.json`
- `loop_XX/discussion_plan.md`
- 如 JSON 修复触发，检查 `discussion_plan.repaired.json` 和 `warnings.jsonl`。

通过标准：

- 每个 subcycle 正好有 A/B/C/D 四个角色。
- 每个角色包含 `political_viewpoint`、`reasoning_focus`、`authority_boundary`。
- 分组理由能回应当前循环的分歧，而不是固定模板。

## 4. Role Conversation

目标：确认单个子循环内三轮讨论按 DeepSeek 多轮方式显式拼接。

检查文件：

- `loop_XX/subcycle_YY_*/discussion_round_01.jsonl`
- `loop_XX/subcycle_YY_*/discussion_round_02.jsonl`
- `loop_XX/subcycle_YY_*/discussion_round_03.jsonl`
- `transcript.jsonl`

通过标准：

- 每个 discussion round 有 4 行。
- `transcript.jsonl` 中同一 subcycle 的 role assistant_count 应递增：
  - 第 1 轮 A/B/C/D: `0,1,2,3`
  - 第 2 轮 A/B/C/D: `4,5,6,7`
  - 第 3 轮 A/B/C/D: `8,9,10,11`
- role request 中 `thinking.type` 为 `disabled`，且 `reasoning_effort` 为 `null`。

## 5. Reports

目标：确认阶段报告和最终总结只用 Markdown 阅读即可。

检查文件：

- `loop_XX/stage_report.md`
- `final_summary.md`

通过标准：

- 阶段报告包含共识、分歧、治理观点差异、角色论证变化、修订建议、行动清单、外部审批事项。
- 最终总结包含最终议案、硬约束、立场变化、保留分歧、时间表、风险清单。

## 6. Metrics / Audit

目标：确认产物完整性和调用链路可量化。

检查命令：

```bash
python3 audit_run.py runs/debug-background --write
```

通过标准：

- `metrics.json` 中 `passed=true`。
- `call_count_matches=true`。
- `all_rounds_have_four_roles=true`。
- `has_no_length_stops=true`。
- `has_no_errors=true`。

## 7. Real Smoke Test

目标：最小成本验证真实 API。

检查命令：

```bash
python3 run_simulation.py scenarios/11_university_evening_self_study.md \
  --loops 1 \
  --max-subcycles 1 \
  --rounds-per-subcycle 3 \
  --coordinator-max-tokens 8192 \
  --role-max-tokens 2048 \
  --stage-max-tokens 8192 \
  --final-max-tokens 8192 \
  --timeout 600 \
  --out runs/debug-real-smoke \
  --keep-runs 0
```

通过标准：

- `metrics.json` 通过。
- `transcript.jsonl` 显示 coordinator thinking enabled/max。
- `transcript.jsonl` 显示 role thinking disabled/no reasoning_effort。
- 三轮 role assistant_count 递增正确。
