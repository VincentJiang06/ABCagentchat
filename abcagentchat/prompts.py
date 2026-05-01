from __future__ import annotations

from .scenario import Scenario


COORDINATOR_SYSTEM = """你是一个严谨的议案讨论协调器。你要帮助四个角色进行社会议案协商。
必须遵守：
1. 来源材料只作为背景，不等于当前模拟组织已有权力。
2. 真实政策红线不能被角色投票推翻。
3. 虚构人物不能声称代表真实部门。
4. 输出必须区分“本组织可决定”和“需提交主管部门/业主大会/行业协会/学校等外部主体”的事项。
5. 不展示思考过程，只输出可读结果。"""


ROLE_SYSTEM = """你是议案讨论中的一个固定角色。你必须严格扮演人格卡中的立场和权限。
讨论要求：
1. 回应当前 compact 和其他角色刚才的意见。
2. 推动议案从分歧走向可修订方案，而不是立即假共识。
3. 明确指出你支持、反对、要求修改或需要外部审批的部分。
4. 不编造真实政府部门、真实组织或真实会议结论。
5. 每次发言保持 350-700 中文字，具体、可执行、有立场。"""


def scenario_header(scenario: Scenario) -> str:
    refs = "\n".join(f"- {ref.get('title', '')}: {ref.get('url', '')}" for ref in scenario.source_refs)
    tests = ", ".join(scenario.primary_tests)
    return f"""场景标题：{scenario.title}
领域：{scenario.domain}
测试重点：{tests}
来源引用：
{refs or "- 无"}
"""


def compact_prompt(scenario: Scenario, loop_index: int, previous_reports: list[str], recent_discussion: str) -> str:
    reports = "\n\n".join(previous_reports[-3:]) if previous_reports else "暂无上一阶段报告。"
    recent = recent_discussion or "暂无角色讨论记录。"
    return f"""请为第 {loop_index} 个循环生成议案讨论 compact。

{scenario_header(scenario)}

原始场景：
{scenario.body}

上一阶段报告：
{reports}

最近讨论记录：
{recent}

请输出 Markdown，包含：
1. 当前事实状态
2. 真实政策或程序红线
3. 本组织可决定事项
4. 需外部主体决定或审批事项
5. 未解决分歧
6. 本循环四个角色应重点讨论的问题
7. 不得遗忘的数字、门槛、时间点、责任主体
"""


def persona_prompt(scenario: Scenario, compact: str) -> str:
    return f"""请根据场景和 compact 生成四个讨论角色。四个角色必须代表四类不同利益或职能，不要都站在同一边。

{scenario_header(scenario)}

场景正文：
{scenario.body}

当前 compact：
{compact}

请只输出 JSON，不要 Markdown。格式：
{{
  "roles": [
    {{
      "slot": "A",
      "name": "虚构姓名或角色名",
      "represents": "代表群体",
      "position": "核心立场",
      "goals": ["目标1", "目标2"],
      "red_lines": ["不能接受的事项"],
      "must_raise": ["本角色必须提出的问题"],
      "speaking_style": "发言风格",
      "authority_boundary": "本角色不能越权做什么决定"
    }}
  ]
}}
slot 必须正好是 A/B/C/D。
"""


def role_prompt(
    scenario: Scenario,
    compact: str,
    persona: dict[str, object],
    loop_index: int,
    round_index: int,
    current_round_context: str,
    recent_history: str,
) -> str:
    return f"""现在进行第 {loop_index} 个循环、第 {round_index} 轮讨论。

{scenario_header(scenario)}

当前 compact：
{compact}

你的人格卡：
{persona}

最近历史摘要：
{recent_history or "暂无。"}

本轮此前角色发言：
{current_round_context or "你是本轮第一个发言者。"}

请以你的角色身份发言。必须包含：
- 你对当前议案的判断
- 你回应了谁的观点
- 你要求新增、删除或修改的具体条款
- 哪些事项不能由本会直接决定
- 下一步可执行动作
"""


def stage_report_prompt(scenario: Scenario, loop_index: int, compact: str, discussion: str) -> str:
    return f"""请生成第 {loop_index} 个循环的阶段性报告。

{scenario_header(scenario)}

本轮 compact：
{compact}

三轮讨论记录：
{discussion}

请输出 Markdown，包含：
1. 本阶段共识
2. 本阶段仍有分歧
3. 议案草案修订建议
4. 本组织可直接执行的行动
5. 需要提交外部主体的事项
6. 风险和遗漏
7. 下一循环讨论重点
"""


def final_summary_prompt(scenario: Scenario, stage_reports: list[str], full_timeline: str) -> str:
    reports = "\n\n".join(stage_reports)
    return f"""请对整个议案讨论过程做最终总结。

{scenario_header(scenario)}

原始场景：
{scenario.body}

全部阶段报告：
{reports}

完整过程索引：
{full_timeline}

请输出 Markdown，包含：
1. 最终议案版本
2. 核心事实和硬约束
3. 四类角色立场变化
4. 最终共识与保留分歧
5. 可由本组织执行的行动清单
6. 需外部主体决定或审批的事项
7. 时间表
8. 风险清单
9. 这次模拟对议案讨论引擎的测试价值
"""

