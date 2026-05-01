# ABCagentchat Module Debug Plan

本计划用于逐块检查模块是否可用。建议先 dry-run，再做 1 loop 真实短测。

## 1. Scenario / Background

目标：确认原始议题和历史 compact 能稳定注入后续循环。标准问题锁定为 5 个循环，最近四个 compact 会以全文进入最后一轮背景；超过 5 循环的 archive 压缩逻辑只作为单元测试覆盖。

检查命令：

```bash
python3 run_simulation.py scenarios/10_university_evening_self_study.md --loops 5 --dry-run --out runs/debug-background --keep-runs 0
```

检查文件：

- `runs/debug-background/loop_01/background_context.md` 应包含原始议题，历史 compact 为空。
- `runs/debug-background/loop_02/background_context.md` 应包含原始议题和“第 1 个循环 compact”。
- `runs/debug-background/loop_05/background_context.md` 应完整保留第 1-4 个循环 compact。
- 标准 5 循环通常不会生成 `compact_archive_summary.md`；超过 5 循环时才会触发更早 compact 的滚动摘要。

通过标准：

- 原始议题没有丢失。
- 历史 compact 最近 4 个保留全文；超过标准 5 循环时，更早 compact 才以递减摘录进入背景，并由高质量滚动开放讨论账本统一兜底。
- 没有把三轮角色全文无限塞入跨循环背景，只保留 compact 和近期摘要。

## 2. Compact

目标：确认 compact 不只记录结论，而是生成可继承的开放讨论状态账本，记录论证路径、政治/治理观点、概念争点和不可化约分歧。

检查文件：

- `loop_XX/compact.md`

通过标准：

- 固定包含 `本轮思想变化摘要`、`稳定事实、概念边界与硬约束`、`抽象问题与概念争点`、`程序与权限边界`、`观点生态账本`、`强冲突议题与不可化约分歧`、`临时共识、条件共识与外部待定`、`防遗忘清单`。
- 每个重要事项能标注 `继承`、`新增`、`修订`、`废弃` 或 `外部待定`。
- 包含角色可见论证路径，不能只写支持/反对结论。
- 包含自治、秩序、效率、公平、专业责任、心理安全等治理取向冲突。
- 保留数字、门槛、时间点、责任主体和外部审批边界。

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

目标：确认单个子循环内按 DeepSeek 多轮方式显式拼接，同时 A/B/C/D 在同一轮并行发言，下一轮才看到上一轮四人的完整输出。

检查文件：

- `loop_XX/subcycle_YY_*/discussion_round_01.jsonl`
- `loop_XX/subcycle_YY_*/discussion_round_02.jsonl`
- `loop_XX/subcycle_YY_*/discussion_round_03.jsonl`
- `loop_XX/subcycle_YY_*/discussion_round_04.jsonl`
- `transcript.jsonl`

通过标准：

- 每个 discussion round 有 4 行。
- 每个 subcycle 的完整背景只应出现在 role request 的 system prompt 中；后续 user prompt 只包含角色人格和本次任务，不再重复写入完整背景、recent history 或当前轮摘要。
- `transcript.jsonl` 中同一 subcycle 的 role assistant_count 应按轮同步递增：
  - 第 1 轮 A/B/C/D: `0,0,0,0`
  - 第 2 轮 A/B/C/D: `4,4,4,4`
  - 第 3 轮 A/B/C/D: `8,8,8,8`
  - 第 4 轮总结 A/B/C/D: `12,12,12,12`
- 第 4 轮应要求四个角色总结自己的最终观点和仍有疑惑，而不是继续开启新争论。
- role request 中 `model` 为 `deepseek-v4-pro`，`thinking.type` 为 `disabled`，且不带 `reasoning_effort`。

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
python3 run_simulation.py scenarios/10_university_evening_self_study.md \
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
- `transcript.jsonl` 显示 role model 为 `deepseek-v4-pro`，thinking disabled，且不带 reasoning_effort。
- 三轮讨论加第 4 轮总结的 role assistant_count 按 `0/4/8/12` 同步递增。
