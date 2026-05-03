# ABCagentchat Example Batch: batch-20260503-004056-full-20

This folder is a curated example export from one long ABCagentchat batch run. It intentionally contains only the 19 completed deliberation examples, not the full raw `runs/` directory.

Included for each case:

- `final_summary/`: reader-facing final summary package.
- `process/loop_XX_stage_report.md`: three loop-level stage reports.
- `process/metrics.json` and `process/audit.log`: lightweight audit evidence.
- `framework/`: original scenario/config/index files used for the case.

Excluded on purpose: raw transcripts, full run logs, monitor HTML, compact background bundles, and local server artifacts.

## Batch Stats

- Completed cases: 19
- Stopped cases: 20_online_social_relationships
- Total calls: 1101
- Total tokens: 67,007,874
- Audit: all completed cases passed blocking checks; warnings are retained in `metrics.json`.

## Read The 19 Final Summaries

| # | Title | Slug | Calls | Tokens | Final | Full | Process |
|---:|---|---|---:|---:|---|---|---|
| 01 | 电动自行车社区充电收费与安全治理议案 | `01_ebike_charging_governance` | 49 | 3,034,033 | [final](./01_ebike_charging_governance/final_summary/final_summary.md) | [full](./01_ebike_charging_governance/final_summary/00_full_final_summary.md) | [process](./01_ebike_charging_governance/final_summary/02_process_analysis.md) |
| 02 | 老旧小区加装电梯与低楼层补偿议案 | `02_old_community_elevator` | 49 | 2,830,753 | [final](./02_old_community_elevator/final_summary/final_summary.md) | [full](./02_old_community_elevator/final_summary/00_full_final_summary.md) | [process](./02_old_community_elevator/final_summary/02_process_analysis.md) |
| 03 | 完整社区建设项目排序议案 | `03_complete_community_priorities` | 60 | 3,852,209 | [final](./03_complete_community_priorities/final_summary/final_summary.md) | [full](./03_complete_community_priorities/final_summary/00_full_final_summary.md) | [process](./03_complete_community_priorities/final_summary/02_process_analysis.md) |
| 04 | 新就业形态骑手权益协商议案 | `04_platform_worker_rights` | 49 | 2,906,459 | [final](./04_platform_worker_rights/final_summary/final_summary.md) | [full](./04_platform_worker_rights/final_summary/00_full_final_summary.md) | [process](./04_platform_worker_rights/final_summary/02_process_analysis.md) |
| 05 | 社区养老服务站资源配置议案 | `05_community_eldercare_station` | 83 | 6,046,302 | [final](./05_community_eldercare_station/final_summary/final_summary.md) | [full](./05_community_eldercare_station/final_summary/00_full_final_summary.md) | [process](./05_community_eldercare_station/final_summary/02_process_analysis.md) |
| 06 | 基层慢病筛查与社区健康服务议案 | `06_primary_health_chronic_disease` | 49 | 2,721,919 | [final](./06_primary_health_chronic_disease/final_summary/final_summary.md) | [full](./06_primary_health_chronic_disease/final_summary/00_full_final_summary.md) | [process](./06_primary_health_chronic_disease/final_summary/02_process_analysis.md) |
| 07 | 城市地下空间与公共通道使用议案 | `07_urban_underground_space` | 49 | 2,916,096 | [final](./07_urban_underground_space/final_summary/final_summary.md) | [full](./07_urban_underground_space/final_summary/00_full_final_summary.md) | [process](./07_urban_underground_space/final_summary/02_process_analysis.md) |
| 08 | 社区嵌入式服务设施运营议案 | `08_embedded_community_services` | 49 | 2,929,819 | [final](./08_embedded_community_services/final_summary/final_summary.md) | [full](./08_embedded_community_services/final_summary/00_full_final_summary.md) | [process](./08_embedded_community_services/final_summary/02_process_analysis.md) |
| 09 | 大学 AI 学术诚信与学生权益建议议案 | `09_university_ai_academic_integrity` | 60 | 3,302,055 | [final](./09_university_ai_academic_integrity/final_summary/final_summary.md) | [full](./09_university_ai_academic_integrity/final_summary/00_full_final_summary.md) | [process](./09_university_ai_academic_integrity/final_summary/02_process_analysis.md) |
| 10 | 大学是否应该有晚自习议案 | `10_university_evening_self_study` | 49 | 2,951,724 | [final](./10_university_evening_self_study/final_summary/final_summary.md) | [full](./10_university_evening_self_study/final_summary/00_full_final_summary.md) | [process](./10_university_evening_self_study/final_summary/02_process_analysis.md) |
| 11 | AI 创作内容是否算作艺术议案 | `11_ai_created_art_status` | 61 | 4,316,020 | [final](./11_ai_created_art_status/final_summary/final_summary.md) | [full](./11_ai_created_art_status/final_summary/00_full_final_summary.md) | [process](./11_ai_created_art_status/final_summary/02_process_analysis.md) |
| 12 | AI 应该如何进一步监管议案 | `12_ai_regulation_next_steps` | 60 | 4,162,543 | [final](./12_ai_regulation_next_steps/final_summary/final_summary.md) | [full](./12_ai_regulation_next_steps/final_summary/00_full_final_summary.md) | [process](./12_ai_regulation_next_steps/final_summary/02_process_analysis.md) |
| 13 | AI 是否应被用于青少年教育议案 | `13_ai_teen_education_use` | 83 | 5,804,391 | [final](./13_ai_teen_education_use/final_summary/final_summary.md) | [full](./13_ai_teen_education_use/final_summary/00_full_final_summary.md) | [process](./13_ai_teen_education_use/final_summary/02_process_analysis.md) |
| 14 | 色情内容与软色情是否对社会有害议案 | `14_sexual_content_social_harm` | 72 | 3,277,607 | [final](./14_sexual_content_social_harm/final_summary/final_summary.md) | [full](./14_sexual_content_social_harm/final_summary/00_full_final_summary.md) | [process](./14_sexual_content_social_harm/final_summary/02_process_analysis.md) |
| 15 | 元宇宙概念对现实社会冲击议案 | `15_metaverse_real_world_impact` | 49 | 2,675,429 | [final](./15_metaverse_real_world_impact/final_summary/final_summary.md) | [full](./15_metaverse_real_world_impact/final_summary/00_full_final_summary.md) | [process](./15_metaverse_real_world_impact/final_summary/02_process_analysis.md) |
| 16 | AI 生产力爆炸后是否可能达成共产主义社会议案 | `16_ai_productivity_communism` | 49 | 2,739,759 | [final](./16_ai_productivity_communism/final_summary/final_summary.md) | [full](./16_ai_productivity_communism/final_summary/00_full_final_summary.md) | [process](./16_ai_productivity_communism/final_summary/02_process_analysis.md) |
| 17 | 新儒家理论是否具有合理性议案 | `17_new_confucianism_reasonableness` | 61 | 3,561,250 | [final](./17_new_confucianism_reasonableness/final_summary/final_summary.md) | [full](./17_new_confucianism_reasonableness/final_summary/00_full_final_summary.md) | [process](./17_new_confucianism_reasonableness/final_summary/02_process_analysis.md) |
| 18 | 中国未来二十年影响力扩张路径议案 | `18_china_next_20_years_expansion` | 60 | 3,825,436 | [final](./18_china_next_20_years_expansion/final_summary/final_summary.md) | [full](./18_china_next_20_years_expansion/final_summary/00_full_final_summary.md) | [process](./18_china_next_20_years_expansion/final_summary/02_process_analysis.md) |
| 19 | 槟榔是否应被视为毒品或成瘾性风险品议案 | `19_betel_nut_drug_classification` | 60 | 3,154,070 | [final](./19_betel_nut_drug_classification/final_summary/final_summary.md) | [full](./19_betel_nut_drug_classification/final_summary/00_full_final_summary.md) | [process](./19_betel_nut_drug_classification/final_summary/02_process_analysis.md) |

## How To Read

Start with each case's `final_summary/final_summary.md`. For deeper inspection, read `final_summary/02_process_analysis.md` and then the three `process/loop_XX_stage_report.md` files. The stage reports are the best way to verify that the final answer came from a staged multi-role debate rather than a single-shot summary.
