from __future__ import annotations

from typing import Any

from .runtime_io import parse_json_object


SLOTS = ("A", "B", "C", "D")


def default_discussion_plan() -> dict[str, Any]:
    return {
        "planning_note": "fallback plan: 保留四个不同视角用于恢复运行；真实 planning 应根据 compact 轮换视角，而不是让同一批角色机械走到底。",
        "groups": [
            {
                "group_id": "a",
                "title": "综合视角碰撞组",
                "purpose": "在同一桌面上处理事实、程序、价值分歧和抽象争点。",
                "conflict_axis": "自主/秩序、照护/控制、公平/效率",
                "roles": [
                    {
                        "slot": slot,
                        "name": f"测试角色{slot}",
                        "represents": group,
                        "perspective_archetype": archetype,
                        "political_viewpoint": viewpoint,
                        "reasoning_focus": "把抽象争点、论证路径、权力边界和保留分歧一起说明。",
                        "position": "在测试中提出清晰但不同的开放立场",
                        "goals": ["验证多角色讨论", "暴露核心概念冲突"],
                        "red_lines": ["不得越权", "不得忽视硬约束"],
                        "must_raise": ["程序边界", "概念定义或安全约束"],
                        "must_challenge": ["把复杂议题过早写成结果"],
                        "will_steelman": "先替最强反方说清楚理由，再回应。",
                        "rotation_rationale": "fallback 用于恢复运行；正式规划应由模型解释本轮是否保留该视角。",
                        "speaking_style": "具体、克制、带有强分歧意识",
                        "authority_boundary": "不能替代主管部门或法定程序作决定",
                    }
                    for slot, group, archetype, viewpoint in zip(
                        SLOTS,
                        ["使用者/学生", "教师/专业执行方", "管理/程序方", "心理或公共利益方"],
                        ["自由主义反强制者", "教育责任辩护者", "秩序型治理者", "弱势经验保护者"],
                        ["自治优先", "教育责任优先", "可执行治理优先", "弱势保护优先"],
                    )
                ],
            }
        ],
    }


def load_discussion_plan(text: str, *, max_groups: int) -> dict[str, Any]:
    data = parse_json_object(text)
    groups = data.get("groups")
    if not isinstance(groups, list) or not groups:
        raise RuntimeError("Discussion planning must return at least one group.")
    normalized_groups: list[dict[str, Any]] = []
    for group_index, group in enumerate(groups[:max_groups], start=1):
        if not isinstance(group, dict):
            raise RuntimeError("Each discussion group must be an object.")
        roles = group.get("roles")
        if not isinstance(roles, list) or len(roles) != 4:
            raise RuntimeError("Each discussion group must return exactly four roles.")
        by_slot = {str(role.get("slot")): role for role in roles if isinstance(role, dict)}
        missing = [slot for slot in SLOTS if slot not in by_slot]
        if missing:
            raise RuntimeError(f"Discussion group missing slots: {', '.join(missing)}")
        normalized_groups.append(
            {
                "group_id": str(group.get("group_id") or chr(96 + group_index)),
                "title": str(group.get("title") or f"子讨论组 {group_index}"),
                "purpose": str(group.get("purpose") or "处理本轮议案分歧。"),
                "conflict_axis": str(group.get("conflict_axis") or ""),
                "roles": [by_slot[slot] for slot in SLOTS],
            }
        )
    return {
        "planning_note": str(data.get("planning_note") or ""),
        "groups": normalized_groups,
    }


def render_discussion_plan(plan: dict[str, Any]) -> str:
    parts = ["# Discussion Plan"]
    note = plan.get("planning_note")
    if note:
        parts.append(f"\n{note}\n")
    for group in plan.get("groups", []):
        parts.append(f"\n## {group.get('group_id')} - {group.get('title')}\n")
        parts.append(f"Purpose: {group.get('purpose')}\n")
        if group.get("conflict_axis"):
            parts.append(f"Conflict axis: {group.get('conflict_axis')}\n")
        for role in group.get("roles", []):
            parts.append(
                f"\n### {role.get('slot')} - {role.get('name')}\n"
                f"- Represents: {role.get('represents')}\n"
                f"- Perspective archetype: {role.get('perspective_archetype')}\n"
                f"- Position: {role.get('position')}\n"
                f"- Political viewpoint: {role.get('political_viewpoint')}\n"
                f"- Reasoning focus: {role.get('reasoning_focus')}\n"
                f"- Must challenge: {role.get('must_challenge')}\n"
                f"- Will steelman: {role.get('will_steelman')}\n"
                f"- Rotation rationale: {role.get('rotation_rationale')}\n"
                f"- Authority boundary: {role.get('authority_boundary')}\n"
            )
    return "\n".join(parts)
