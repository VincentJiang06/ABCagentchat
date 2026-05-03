# ABCagentchat

ABCagentchat 是一个面向复杂公共议题的多角色深度审议模拟框架。它不是用来快速生成几段观点，而是让多个价值立场在长程上下文中持续交叉质询、钢人化反方、暴露假共识，并最终产出可审计的研究包。

本仓库包含完整框架、20 个议题脚本，以及一次真实长跑批次整理出的精选 examples：`examples/batch-20260503-004056-full-20`。其中 1-19 号议题已完成，20 号按人工要求在启动前停止。建议直接从各议题的 `final_summary.md` 或 `00_full_final_summary.md` 开始阅读。

## 为什么值得看

这套流程的核心价值，是把一个看似具体的政策问题逐步推进到更深的道德、制度和执行边界：

- 谁承担代价，谁拥有定义权？
- 程序正义是在保护弱者，还是在给权力合法化？
- 退出权、监督权、知情权在真实权力关系中是否真的可达？
- 不可量化的尊严、心理安全、信任、照护成本，是否被治理工具默认为零？
- 一个方案看起来“可执行”，到底是法律上可执行，还是事实上可落实？

每个完成流程都包含三轮以上的长程讨论、阶段报告、最终总结与审计指标。原始 `runs/` 目录在本地保留但默认不提交；GitHub 上的 `examples/` 只保留适合阅读和审计的精选材料。最终产物不是单一结论，而是一份包含共识、条件共识、明确反对、不可化约分歧、条款级矩阵和证据缺口的研究档案。

## 精选 examples 批次

仓库不会上传完整 `runs/` 原始运行目录。完整运行目录包含 transcript、run.log、monitor 页面、compact 背景和本地运行状态，体量大且不适合作为 GitHub 阅读入口。

本仓库改为提交一个精选样例包：

```text
examples/batch-20260503-004056-full-20/
  README.md
  batch_summary.json
  01_.../
    framework/              # 输入议题、运行配置、索引
    process/                # 三轮 stage_report + metrics/audit
    final_summary/           # 可读最终研究包
  ...
```

批次摘要：

- Batch: `batch-20260503-004056-full-20`
- 完成议题：19
- 人工停止：20_online_social_relationships
- 总调用：1101
- 总 tokens：67,007,874
- 审计状态：19 个完成流程的 blocking checks 全部通过；warning 来自长度截断和 preview 缺失，不代表运行失败。

## 19 个完成议题

优先阅读每一行的 `final_summary.md`。如果想看完整研究包，可以进入同一目录下的 `00_full_final_summary.md`、`01_discussion_result.md`、`02_process_analysis.md`、`03_synthesized_document.md` 和 `04_evidence_and_next_steps.md`。

| # | 议题 | Final summary | Full package |
|---:|---|---|---|
| 01 | 电动自行车社区充电收费与安全治理议案 | [final_summary.md](examples/batch-20260503-004056-full-20/01_ebike_charging_governance/final_summary/final_summary.md) | [完整包](examples/batch-20260503-004056-full-20/01_ebike_charging_governance/final_summary/00_full_final_summary.md) |
| 02 | 老旧小区加装电梯与低楼层补偿议案 | [final_summary.md](examples/batch-20260503-004056-full-20/02_old_community_elevator/final_summary/final_summary.md) | [完整包](examples/batch-20260503-004056-full-20/02_old_community_elevator/final_summary/00_full_final_summary.md) |
| 03 | 完整社区建设项目排序议案 | [final_summary.md](examples/batch-20260503-004056-full-20/03_complete_community_priorities/final_summary/final_summary.md) | [完整包](examples/batch-20260503-004056-full-20/03_complete_community_priorities/final_summary/00_full_final_summary.md) |
| 04 | 新就业形态骑手权益协商议案 | [final_summary.md](examples/batch-20260503-004056-full-20/04_platform_worker_rights/final_summary/final_summary.md) | [完整包](examples/batch-20260503-004056-full-20/04_platform_worker_rights/final_summary/00_full_final_summary.md) |
| 05 | 社区养老服务站资源配置议案 | [final_summary.md](examples/batch-20260503-004056-full-20/05_community_eldercare_station/final_summary/final_summary.md) | [完整包](examples/batch-20260503-004056-full-20/05_community_eldercare_station/final_summary/00_full_final_summary.md) |
| 06 | 基层慢病筛查与社区健康服务议案 | [final_summary.md](examples/batch-20260503-004056-full-20/06_primary_health_chronic_disease/final_summary/final_summary.md) | [完整包](examples/batch-20260503-004056-full-20/06_primary_health_chronic_disease/final_summary/00_full_final_summary.md) |
| 07 | 城市地下空间与公共通道使用议案 | [final_summary.md](examples/batch-20260503-004056-full-20/07_urban_underground_space/final_summary/final_summary.md) | [完整包](examples/batch-20260503-004056-full-20/07_urban_underground_space/final_summary/00_full_final_summary.md) |
| 08 | 社区嵌入式服务设施运营议案 | [final_summary.md](examples/batch-20260503-004056-full-20/08_embedded_community_services/final_summary/final_summary.md) | [完整包](examples/batch-20260503-004056-full-20/08_embedded_community_services/final_summary/00_full_final_summary.md) |
| 09 | 大学 AI 学术诚信与学生权益建议议案 | [final_summary.md](examples/batch-20260503-004056-full-20/09_university_ai_academic_integrity/final_summary/final_summary.md) | [完整包](examples/batch-20260503-004056-full-20/09_university_ai_academic_integrity/final_summary/00_full_final_summary.md) |
| 10 | 大学是否应该有晚自习议案 | [final_summary.md](examples/batch-20260503-004056-full-20/10_university_evening_self_study/final_summary/final_summary.md) | [完整包](examples/batch-20260503-004056-full-20/10_university_evening_self_study/final_summary/00_full_final_summary.md) |
| 11 | AI 创作内容是否算作艺术议案 | [final_summary.md](examples/batch-20260503-004056-full-20/11_ai_created_art_status/final_summary/final_summary.md) | [完整包](examples/batch-20260503-004056-full-20/11_ai_created_art_status/final_summary/00_full_final_summary.md) |
| 12 | AI 应该如何进一步监管议案 | [final_summary.md](examples/batch-20260503-004056-full-20/12_ai_regulation_next_steps/final_summary/final_summary.md) | [完整包](examples/batch-20260503-004056-full-20/12_ai_regulation_next_steps/final_summary/00_full_final_summary.md) |
| 13 | AI 是否应被用于青少年教育议案 | [final_summary.md](examples/batch-20260503-004056-full-20/13_ai_teen_education_use/final_summary/final_summary.md) | [完整包](examples/batch-20260503-004056-full-20/13_ai_teen_education_use/final_summary/00_full_final_summary.md) |
| 14 | 色情内容与软色情是否对社会有害议案 | [final_summary.md](examples/batch-20260503-004056-full-20/14_sexual_content_social_harm/final_summary/final_summary.md) | [完整包](examples/batch-20260503-004056-full-20/14_sexual_content_social_harm/final_summary/00_full_final_summary.md) |
| 15 | 元宇宙概念对现实社会冲击议案 | [final_summary.md](examples/batch-20260503-004056-full-20/15_metaverse_real_world_impact/final_summary/final_summary.md) | [完整包](examples/batch-20260503-004056-full-20/15_metaverse_real_world_impact/final_summary/00_full_final_summary.md) |
| 16 | AI 生产力爆炸后是否可能达成共产主义社会议案 | [final_summary.md](examples/batch-20260503-004056-full-20/16_ai_productivity_communism/final_summary/final_summary.md) | [完整包](examples/batch-20260503-004056-full-20/16_ai_productivity_communism/final_summary/00_full_final_summary.md) |
| 17 | 新儒家理论是否具有合理性议案 | [final_summary.md](examples/batch-20260503-004056-full-20/17_new_confucianism_reasonableness/final_summary/final_summary.md) | [完整包](examples/batch-20260503-004056-full-20/17_new_confucianism_reasonableness/final_summary/00_full_final_summary.md) |
| 18 | 中国未来二十年影响力扩张路径议案 | [final_summary.md](examples/batch-20260503-004056-full-20/18_china_next_20_years_expansion/final_summary/final_summary.md) | [完整包](examples/batch-20260503-004056-full-20/18_china_next_20_years_expansion/final_summary/00_full_final_summary.md) |
| 19 | 槟榔是否应被视为毒品或成瘾性风险品议案 | [final_summary.md](examples/batch-20260503-004056-full-20/19_betel_nut_drug_classification/final_summary/final_summary.md) | [完整包](examples/batch-20260503-004056-full-20/19_betel_nut_drug_classification/final_summary/00_full_final_summary.md) |

## 单个流程的产物结构

每个议题运行目录都按四类材料组织：

```text
framework/
  input.md
  run_config.json
  run_index.md

compact and planning/
  loop_01/
    background_context.md
    compact.md
    discussion_plan.json
    discussion_plan.md
  loop_02/
  loop_03/

process/
  transcript.jsonl
  run.log
  warnings.jsonl
  metrics.json
  audit.log
  loop_01/
    stage_report.md
    subcycle_01_a/discussion_round_01.jsonl
    subcycle_01_a/discussion_round_02.jsonl
    subcycle_01_a/discussion_round_03.jsonl

final summary/
  final_summary.md
  00_full_final_summary.md
  01_discussion_result.md
  02_process_analysis.md
  03_synthesized_document.md
  04_evidence_and_next_steps.md
```

阅读建议：

1. 先读 `final summary/final_summary.md`，获得议题结论。
2. 再读 `final summary/02_process_analysis.md`，理解三轮讨论如何推进。
3. 如果需要审计模型是否真的讨论过这些内容，读 examples 中的 `process/loop_XX_stage_report.md` 和 `process/metrics.json`；完整 raw transcript 只保留在本地 `runs/` 中，不提交到仓库。
4. 如果要复现实验设置，读 `framework/run_config.json` 和 `framework/input.md`。

## 架构

ABCagentchat 的主流程由一个 coordinator 和四个 role agents 组成。

```text
scenario markdown
    │
    ▼
framework input + run config
    │
    ▼
loop compact ──► planning ──► A/B/C/D round-parallel discussion
    │                         │
    │                         ├─ round 1: 初始观点
    │                         ├─ round 2: 互相辩论
    │                         └─ round 3: 更强压力测试
    │
    ▼
stage report
    │
    ├─ loop 1
    ├─ loop 2
    └─ loop 3
    │
    ▼
final summary package
```

主要模块：

- `abcagentchat/api.py`: DeepSeek API payload、thinking 开关、响应解析。
- `abcagentchat/orchestrator.py`: 单个议题的主循环。
- `abcagentchat/roles.py`: A/B/C/D 角色并行发言与 JSONL 记录。
- `abcagentchat/planning.py`: 每轮讨论计划解析和渲染。
- `abcagentchat/compact.py`: 跨 loop 的状态压缩。
- `abcagentchat/reports.py`: 阶段报告和最终总结。
- `abcagentchat/monitor.py`: 本地监控页面。
- `abcagentchat/metrics.py`: 产物完整性与 transcript 审计。
- `run_all_scenarios.py`: 批量并发调度器。
- `stop_batch.py`: 批量运行停止控制。
- `serve_monitor.py`: 静态监控服务。

## 模型策略

当前默认策略：

- Coordinator: `deepseek-v4-pro`，thinking enabled，用于 compact、planning、stage report、final summary。
- Role A/B/C/D: non-thinking `deepseek-v4-pro`，用于高频角色发言。
- 默认 loops: `3`。
- 默认 role rounds: `3`，分别是初始观点、相互辩论、更激烈的压力测试。
- 默认 batch parallelism: `3`。

这个策略刻意把“长程整合”交给 coordinator，把“多立场交锋”交给非 thinking role agents，以控制速度，同时保留最终研究包的结构深度。

## 运行

创建 `.env`：

```env
DEEPSEEK_COORDINATOR_KEY=...
DEEPSEEK_ROLE_A_KEY=...
DEEPSEEK_ROLE_B_KEY=...
DEEPSEEK_ROLE_C_KEY=...
DEEPSEEK_ROLE_D_KEY=...
```

运行单个议题：

```bash
python3 run_simulation.py scenarios/10_university_evening_self_study.md --loops 3 --enable-monitor
```

批量运行全部场景：

```bash
python3 run_all_scenarios.py --parallel 3 --loops 3 --enable-monitor
python3 serve_monitor.py --root runs/nightly-all-tests --port 8765
```

停止批量运行：

```bash
python3 stop_batch.py
```

审计运行结果：

```bash
python3 audit_run.py runs/nightly-all-tests/batch-20260503-004056-full-20/13_ai_teen_education_use --write
python3 -m unittest discover -s tests
```

## 研究边界

这些样例是模型生成的审议模拟，不是真实政策调研。它们适合用来：

- 发现议题中的隐藏价值冲突。
- 生成利益相关方和缺席视角清单。
- 形成条款级风险矩阵。
- 检查某个政策建议是否存在假共识。
- 准备真实访谈、法务审查或公共听证的议程。

它们不应该被直接当作真实决策依据。任何涉及法律、预算、医疗、未成年人、公共安全、劳动权益或公共治理的结论，都需要真实数据、专业意见和责任主体复核。

