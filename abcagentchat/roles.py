from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
from typing import Any, Callable

from .api import ChatResult
from .conversation import Conversation
from .prompts import ROLE_SYSTEM, role_prompt, subcycle_context_prompt
from .runtime_io import result_summary, safe_slug
from .scenario import Scenario


RoleCall = Callable[
    [str, str, list[dict[str, str]], int | None, dict[str, Any] | None],
    tuple[str, ChatResult],
]

SLOT_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}


def _load_round_records(round_path: Path) -> list[dict[str, Any]]:
    if not round_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in round_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _discussion_part(record: dict[str, Any]) -> str:
    return (
        f"[loop {record['loop']} subcycle {record['subcycle']} round {record['round']} "
        f"{record['group_title']} {record['role_name']}/{record['slot']}]\n{record['content']}"
    )


def collect_discussion_parts(loop_dir: Path) -> list[str]:
    parts: list[str] = []
    for round_path in sorted(loop_dir.glob("subcycle_*_*/discussion_round_*.jsonl")):
        for record in _load_round_records(round_path):
            parts.append(_discussion_part(record))
    return parts


def _ordered_roles(group: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(group["roles"], key=lambda persona: SLOT_ORDER.get(str(persona.get("slot")), 99))


def _write_round_records(round_path: Path, records: list[dict[str, Any]]) -> None:
    round_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


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
    resume_existing: bool = False,
    include_summary_round: bool = False,
    parallel_roles: bool = True,
) -> list[str]:
    group_id = str(group["group_id"])
    group_title = str(group["title"])
    group_dir = loop_dir / f"subcycle_{subcycle_index:02d}_{safe_slug(group_id)}"
    group_dir.mkdir(parents=True, exist_ok=True)
    group_meta = {
        "group_id": group_id,
        "title": group_title,
        "purpose": group.get("purpose"),
        "conflict_axis": group.get("conflict_axis"),
    }
    conversation = Conversation(
        ROLE_SYSTEM
        + "\n\n"
        + subcycle_context_prompt(
            scenario=scenario,
            compact=compact,
            group=group_meta,
            recent_history=recent_history,
            background_context=background_context,
        )
    )
    discussion_parts: list[str] = []
    roles = _ordered_roles(group)
    persona_by_slot = {str(persona["slot"]): persona for persona in roles}
    total_rounds = rounds_per_subcycle + (1 if include_summary_round else 0)

    for round_index in range(1, total_rounds + 1):
        is_summary_round = include_summary_round and round_index == total_rounds
        round_path = group_dir / f"discussion_round_{round_index:02d}.jsonl"
        existing_records = _load_round_records(round_path) if resume_existing else []
        existing_by_slot = {str(record["slot"]): record for record in existing_records}

        if existing_records:
            print(
                f"[loop {loop_index}] subcycle={subcycle_index} "
                f"discussion_round={round_index} parallel resume_existing={len(existing_records)}",
                flush=True,
            )
        else:
            kind = "summary" if is_summary_round else "discussion"
            print(
                f"[loop {loop_index}] subcycle={subcycle_index} "
                f"discussion_round={round_index} kind={kind} parallel",
                flush=True,
            )

        pending_calls: dict[str, dict[str, Any]] = {}
        round_snapshot_assistant_count = conversation.assistant_count()
        for persona in roles:
            slot = str(persona["slot"])
            if slot in existing_by_slot:
                continue
            role_name = str(persona.get("name") or slot)
            prompt = role_prompt(
                group=group_meta,
                persona=persona,
                loop_index=loop_index,
                subcycle_index=subcycle_index,
                round_index=round_index,
                is_summary_round=is_summary_round,
            )
            messages = conversation.messages_for(prompt)
            pending_calls[slot] = {
                "persona": persona,
                "role_name": role_name,
                "prompt": prompt,
                "messages": messages,
                "context_meta": {
                    "loop": loop_index,
                    "subcycle": subcycle_index,
                    "round": round_index,
                    "group_id": group_id,
                    "slot": slot,
                    "assistant_context_messages": round_snapshot_assistant_count,
                    "parallel_round": True,
                    "summary_round": is_summary_round,
                },
            }

        completed: dict[str, tuple[str, ChatResult]] = {}
        if pending_calls:
            mode = "parallel" if parallel_roles else "serial"
            print(
                f"[loop {loop_index}] subcycle={subcycle_index} "
                f"discussion_round={round_index} {mode}_start={len(pending_calls)}",
                flush=True,
            )

            def _log_done(slot: str, content: str, result: ChatResult) -> None:
                spec = pending_calls[slot]
                print(
                    f"  [{slot}] {spec['role_name']} "
                    f"{result.elapsed_seconds:.1f}s tokens={result.total_tokens} "
                    f"ctx_assistants={spec['context_meta']['assistant_context_messages']} "
                    f"preview={content[:preview_chars].replace(chr(10), ' ')}",
                    flush=True,
                )

            if parallel_roles:
                with ThreadPoolExecutor(max_workers=len(pending_calls)) as executor:
                    futures = {
                        executor.submit(
                            call_role, slot, f"role_{slot}",
                            spec["messages"], role_max_tokens, spec["context_meta"],
                        ): slot
                        for slot, spec in pending_calls.items()
                    }
                    for future in as_completed(futures):
                        slot = futures[future]
                        content, result = future.result()
                        completed[slot] = (content, result)
                        _log_done(slot, content, result)
            else:
                # Local single-process backend: one model, one canvas at a time.
                # Messages were snapshotted before the round, so serial order does
                # not change what any role sees — the discussion stays fair.
                for slot, spec in pending_calls.items():
                    content, result = call_role(
                        slot, f"role_{slot}",
                        spec["messages"], role_max_tokens, spec["context_meta"],
                    )
                    completed[slot] = (content, result)
                    _log_done(slot, content, result)
            print(
                f"[loop {loop_index}] subcycle={subcycle_index} "
                f"discussion_round={round_index} {mode}_complete={len(completed)}",
                flush=True,
            )

        ordered_records: list[dict[str, Any]] = []
        for persona in roles:
            slot = str(persona["slot"])
            if slot in existing_by_slot:
                record = existing_by_slot[slot]
                prompt = role_prompt(
                    group=group_meta,
                    persona=persona,
                    loop_index=loop_index,
                    subcycle_index=subcycle_index,
                    round_index=round_index,
                    is_summary_round=is_summary_round,
                )
                conversation.append_exchange(prompt, str(record["content"]))
                ordered_records.append(record)
                discussion_parts.append(_discussion_part(record))
                continue

            spec = pending_calls[slot]
            content, result = completed[slot]
            conversation.append_exchange(str(spec["prompt"]), content)
            record = {
                "loop": loop_index,
                "subcycle": subcycle_index,
                "group_id": group_id,
                "group_title": group_title,
                "round": round_index,
                "slot": slot,
                "role_name": spec["role_name"],
                "represents": persona.get("represents"),
                "political_viewpoint": persona.get("political_viewpoint"),
                "reasoning_focus": persona.get("reasoning_focus"),
                "content": content,
                "usage": result_summary(result),
                "conversation": {
                    "assistant_messages_before_call": spec["context_meta"]["assistant_context_messages"],
                    "message_count_sent": len(spec["messages"]),
                    "parallel_round": True,
                    "summary_round": is_summary_round,
                },
            }
            ordered_records.append(record)
            discussion_parts.append(
                f"[loop {loop_index} subcycle {subcycle_index} round {round_index} {group_title} {spec['role_name']}/{slot}]\n{content}"
            )

        _write_round_records(round_path, ordered_records)
    return discussion_parts
