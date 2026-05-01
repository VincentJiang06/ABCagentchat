from __future__ import annotations

from .scenario import Scenario


COORDINATOR_SYSTEM = """你是一个严谨的议案讨论协调器。你要帮助多个四人小组进行议案协商。
必须遵守：
1. 来源材料只作为背景，不等于当前模拟组织已有权力。
2. 真实政策红线不能被角色投票推翻。
3. 虚构人物不能声称代表真实部门。
4. 输出必须区分“本组织可决定”和“需提交主管部门/业主大会/行业协会/学校等外部主体”的事项。
5. 不展示隐藏思考过程；可以总结角色可见的论证路径、价值取向、政治观点和治理假设。"""


ROLE_SYSTEM = """你是议案讨论中的一个固定角色。你必须严格扮演人格卡中的立场和权限。
讨论要求：
1. 回应当前 compact 和其他角色刚才的意见。
2. 推动议案从分歧走向可修订方案，而不是立即假共识。
3. 明确指出你支持、反对、要求修改或需要外部审批的部分。
4. 不编造真实政府部门、真实组织或真实会议结论。
5. 每次发言保持 450-900 中文字，具体、可执行、有立场。
6. 不要写成长报告；每个要求用一到两句话完成，避免长篇分节展开。"""


def scenario_header(scenario: Scenario) -> str:
    refs = "\n".join(f"- {ref.get('title', '')}: {ref.get('url', '')}" for ref in scenario.source_refs)
    tests = ", ".join(scenario.primary_tests)
    return f"""场景标题：{scenario.title}
领域：{scenario.domain}
测试重点：{tests}
来源引用：
{refs or "- 无"}
"""


def compact_prompt(
    scenario: Scenario,
    loop_index: int,
    compact_archive_context: str,
    previous_reports_context: str,
    recent_discussion: str,
) -> str:
    reports = previous_reports_context or "暂无上一阶段报告。"
    recent = recent_discussion or "暂无角色讨论记录。"
    return f"""请为第 {loop_index} 个循环生成议案讨论 compact。

{scenario_header(scenario)}

原始场景：
{scenario.body}

原始议题与历史 compact 档案：
{compact_archive_context}

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
6. 各角色可见论证路径：他们为什么这样判断，而不只记录结论
7. 各角色政治/治理观点：自治、效率、秩序、公平、专业责任、心理安全等取向如何冲突
8. 本循环子讨论组应重点讨论的问题
9. 不得遗忘的数字、门槛、时间点、责任主体
"""


def deliberation_plan_prompt(scenario: Scenario, compact: str, *, max_groups: int, background_context: str = "") -> str:
    return f"""请根据场景和 compact 设计本循环的子讨论结构和角色人格。

你最多可以设计 {max_groups} 个子讨论组。每个子讨论组必须包含 A/B/C/D 四个角色。
如果议题适合拆分，请拆分为同质小组和联合协商小组。例如“大学是否应该有晚自习”可拆成：
- a 教师/助教组：四个教授或教学执行者讨论学业支持与教学责任
- b 学生组：四类学生代表讨论自主权、宿舍生活、学习困难与权益
- c 联合协调组：学生、教师、管理、心理支持共同谈可执行修订

如果议题不适合拆分，可以只设计 1 个综合组。

{scenario_header(scenario)}

场景正文：
{scenario.body}

当前 compact：
{compact}

背景资料（原始议题 + 前序循环 compact 档案）：
{background_context or "暂无历史 compact。"}

角色设计要求：
- 每个角色都要有明确利益来源、政治/治理观点和论证习惯。
- 不要只写“支持/反对”，必须写清楚他/她重视什么价值，以及会如何推理。
- 同一组内四个角色不能都站在同一边。
- 每个角色必须有 authority_boundary，避免越权。
- 人格可以在每轮重写，但必须继承 compact 中已经形成的硬约束和重要分歧。

请只输出 JSON，不要 Markdown。格式：
{{
  "planning_note": "为什么本轮这样拆分",
  "groups": [
    {{
      "group_id": "a",
      "title": "子讨论组名称",
      "purpose": "本组为什么要单独讨论",
      "roles": [
        {{
          "slot": "A",
          "name": "虚构姓名或角色名",
          "represents": "代表群体",
          "political_viewpoint": "治理或政治价值取向",
          "reasoning_focus": "本角色主要如何推理和权衡",
          "position": "核心立场",
          "goals": ["目标1", "目标2"],
          "red_lines": ["不能接受的事项"],
          "must_raise": ["本角色必须提出的问题"],
          "speaking_style": "发言风格",
          "authority_boundary": "本角色不能越权做什么决定"
        }}
      ]
    }}
  ]
}}
每个 group 内 slot 必须正好是 A/B/C/D。
"""


def json_repair_prompt(raw_text: str) -> str:
    return f"""下面是一段应该为 JSON 的文本，但可能包含引号错误、未转义换行、尾随逗号或其他轻微格式问题。

请只输出修复后的合法 JSON，不要 Markdown，不要解释，不要改变字段含义。

原始文本：
{raw_text}
"""


def role_prompt(
    scenario: Scenario,
    compact: str,
    persona: dict[str, object],
    group: dict[str, object],
    loop_index: int,
    subcycle_index: int,
    round_index: int,
    current_round_context: str,
    recent_history: str,
    background_context: str = "",
) -> str:
    return f"""现在进行第 {loop_index} 个循环、第 {subcycle_index} 个子讨论组、第 {round_index} 轮讨论。

{scenario_header(scenario)}

本子讨论组：
{group}

当前 compact：
{compact}

背景资料（原始议题 + 前序循环 compact 档案）：
{background_context or "暂无历史 compact。"}

你的人格卡：
{persona}

最近历史摘要：
{recent_history or "暂无。"}

本轮此前角色发言：
{current_round_context or "你是本轮第一个发言者。"}

请以你的角色身份发言。必须包含：
- 你对当前议案的判断
- 你的可见论证路径：你依据哪些事实、价值和风险作出判断
- 你的政治/治理观点：你更重视自治、秩序、效率、公平、专业责任或心理安全中的哪些
- 你回应了谁的观点
- 你要求新增、删除或修改的具体条款
- 哪些事项不能由本会直接决定
- 下一步可执行动作

长度要求：总长控制在 450-900 中文字；不要使用多级标题；不要写成长报告。
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
3. 各子讨论组的政治/治理观点差异
4. 角色论证路径变化：谁被说服、谁坚持、原因是什么
5. 议案草案修订建议
6. 本组织可直接执行的行动
7. 需要提交外部主体的事项
8. 风险和遗漏
9. 下一循环讨论重点
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
