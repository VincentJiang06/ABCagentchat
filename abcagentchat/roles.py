from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .api import ChatResult
from .conversation import Conversation
from .prompts import ROLE_SYSTEM, role_prompt
from .runtime_io import result_summary, safe_slug
from .scenario import Scenario


RoleCall = Callable[
    [str, str, list[dict[str, str]], int | None, dict[str, Any] | None],
    tuple[str, ChatResult],
]


def run_discussion_group(
    *,
    scenario: Scenario,
    compact: str,
    group: dict[str, Any],
    loop_index: int,
    subcycle_index: int,
    rounds_per_subcycle: int,
    recent_history: str,
    background_context: str,
    loop_dir: Path,
    role_max_tokens: int | None,
    preview_chars: int,
    call_role: RoleCall,
) -> list[str]:
    group_id = str(group["group_id"])
    group_title = str(group["title"])
    group_dir = loop_dir / f"subcycle_{subcycle_index:02d}_{safe_slug(group_id)}"
    group_dir.mkdir(parents=True, exist_ok=True)
    conversation = Conversation(ROLE_SYSTEM)
    discussion_parts: list[str] = []

    for round_index in range(1, rounds_per_subcycle + 1):
        current_round_parts: list[str] = []
        round_path = group_dir / f"discussion_round_{round_index:02d}.jsonl"
        print(f"[loop {loop_index}] subcycle={subcycle_index} discussion_round={round_index}", flush=True)
        for persona in group["roles"]:
            slot = str(persona["slot"])
            role_name = str(persona.get("name") or slot)
            prompt = role_prompt(
                scenario=scenario,
                compact=compact,
                group={
                    "group_id": group_id,
                    "title": group_title,
                    "purpose": group.get("purpose"),
                },
                persona=persona,
                loop_index=loop_index,
                subcycle_index=subcycle_index,
                round_index=round_index,
                current_round_context="\n\n".join(current_round_parts),
                recent_history=recent_history,
                background_context=background_context,
            )
            messages = conversation.messages_for(prompt)
            content, result = call_role(
                slot,
                f"role_{slot}",
                messages,
                role_max_tokens,
                {
                    "loop": loop_index,
                    "subcycle": subcycle_index,
                    "round": round_index,
                    "group_id": group_id,
                    "slot": slot,
                    "assistant_context_messages": conversation.assistant_count(),
                },
            )
            conversation.append_exchange(prompt, content)
            record = {
                "loop": loop_index,
                "subcycle": subcycle_index,
                "group_id": group_id,
                "group_title": group_title,
                "round": round_index,
                "slot": slot,
                "role_name": role_name,
                "represents": persona.get("represents"),
                "political_viewpoint": persona.get("political_viewpoint"),
                "reasoning_focus": persona.get("reasoning_focus"),
                "content": content,
                "usage": result_summary(result),
                "conversation": {
                    "assistant_messages_before_call": max(conversation.assistant_count() - 1, 0),
                    "message_count_sent": len(messages),
                },
            }
            with round_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            line = f"{group_title}/{role_name}({slot}): {content}"
            current_round_parts.append(line)
            discussion_parts.append(
                f"[loop {loop_index} subcycle {subcycle_index} round {round_index} {group_title} {role_name}/{slot}]\n{content}"
            )
            print(
                f"  [{slot}] {role_name} "
                f"{result.elapsed_seconds:.1f}s tokens={result.total_tokens} "
                f"ctx_assistants={record['conversation']['assistant_messages_before_call']} "
                f"preview={content[:preview_chars].replace(chr(10), ' ')}",
                flush=True,
            )
    return discussion_parts
