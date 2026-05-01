from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .api import ChatResult, DeepSeekClient
from .config import AppConfig
from .gc import prune_old_runs, trim_text
from .metrics import write_metrics
from .prompts import (
    COORDINATOR_SYSTEM,
    ROLE_SYSTEM,
    compact_prompt,
    final_summary_prompt,
    persona_prompt,
    role_prompt,
    stage_report_prompt,
)
from .scenario import Scenario


@dataclass
class RunOptions:
    output_dir: Path | None = None
    keep_runs: int = 10
    dry_run: bool = False
    timeout: int = 600
    recent_context_chars: int = 24000
    preview_chars: int = 260
    coordinator_max_tokens: int | None = None
    role_max_tokens: int | None = None
    stage_max_tokens: int | None = None
    final_max_tokens: int | None = None


class DryRunClient:
    def __init__(self, label: str) -> None:
        self.label = label

    def chat(self, messages: list[dict[str, str]], *, max_tokens: int | None = None, temperature: float | None = None) -> ChatResult:
        content = self._fake_content(messages)
        return ChatResult(
            content=content,
            elapsed_seconds=0.01,
            finish_reason="dry_run",
            prompt_tokens=sum(len(message.get("content", "")) // 2 for message in messages),
            completion_tokens=len(content) // 2,
            reasoning_tokens=0,
            total_tokens=sum(len(message.get("content", "")) // 2 for message in messages) + len(content) // 2,
            raw={"dry_run": True, "client": self.label},
        )

    def _fake_content(self, messages: list[dict[str, str]]) -> str:
        last = messages[-1]["content"]
        if "请对整个议案讨论过程做最终总结" in last:
            return "## 最终总结\n\n本次 dry-run 验证了文件生成、循环流程、角色隔离和报告保存逻辑。"
        if "请只输出 JSON" in last:
            return json.dumps(
                {
                    "roles": [
                        {
                            "slot": slot,
                            "name": f"测试角色{slot}",
                            "represents": group,
                            "position": "在测试中提出清晰但不同的立场",
                            "goals": ["验证多角色讨论", "推动议案修订"],
                            "red_lines": ["不得越权", "不得忽视硬约束"],
                            "must_raise": ["程序边界", "预算或安全约束"],
                            "speaking_style": "具体、克制、带有修订建议",
                            "authority_boundary": "不能替代主管部门或法定程序作决定",
                        }
                        for slot, group in zip("ABCD", ["居民/使用者", "运营/执行方", "监管/程序方", "弱势或公共利益方"])
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
        if "现在进行第" in last and "你的人格卡" in last:
            return "我代表本角色发言：支持继续推进，但要求把预算、程序边界、责任主体和弱势群体保护写入修订条款。需要把可由本组织决定的试点事项，与必须提交主管部门或法定程序的事项分开处理。"
        if "请生成第" in last and "阶段性报告" in last:
            return "## 阶段性报告\n\n- 共识：需要保留硬约束并形成试点。\n- 分歧：费用、责任和审批边界仍需细化。\n- 下一步：将争议条款改写为可表决文本。"
        if "生成议案讨论 compact" in last:
            return "## Compact\n\n- 当前事实：保留场景硬约束。\n- 程序红线：不得越权替代审批。\n- 本轮重点：预算、责任、弱势群体、执行路径。"
        return "我代表本角色发言：支持继续推进，但要求把预算、程序边界、责任主体和弱势群体保护写入修订条款。"


def safe_slug(value: str) -> str:
    value = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", value.strip())
    value = value.strip("-._")
    return value[:80] or "scenario"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def result_summary(result: ChatResult) -> dict[str, Any]:
    return {
        "elapsed_seconds": round(result.elapsed_seconds, 3),
        "finish_reason": result.finish_reason,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "reasoning_tokens": result.reasoning_tokens,
        "visible_answer_tokens_estimate": result.visible_answer_tokens_estimate,
        "total_tokens": result.total_tokens,
    }


class Simulator:
    def __init__(self, root: Path, config: AppConfig | None, options: RunOptions) -> None:
        self.root = root
        self.config = config
        self.options = options
        self.clients = self._build_clients()

    def _build_clients(self) -> dict[str, Any]:
        if self.options.dry_run:
            return {slot: DryRunClient(slot) for slot in ["coordinator", "A", "B", "C", "D"]}
        if self.config is None:
            raise RuntimeError("Config is required unless dry_run is enabled.")
        clients: dict[str, Any] = {
            "coordinator": DeepSeekClient(self.config.coordinator_key, self.config.coordinator_settings)
        }
        for slot, key in self.config.role_keys.items():
            clients[slot] = DeepSeekClient(key, self.config.role_settings)
        return clients

    def make_run_dir(self, scenario: Scenario) -> Path:
        if self.options.output_dir:
            run_dir = self.options.output_dir
        else:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            run_dir = self.root / "runs" / f"{stamp}-{safe_slug(scenario.title)}"
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def run(self, scenario: Scenario) -> Path:
        run_dir = self.make_run_dir(scenario)
        shutil.copy2(scenario.path, run_dir / "input.md")
        write_json(
            run_dir / "run_config.json",
            {
                "scenario": {
                    "path": str(scenario.path),
                    "title": scenario.title,
                    "loops": scenario.loops,
                    "domain": scenario.domain,
                    "source_refs": scenario.source_refs,
                    "primary_tests": scenario.primary_tests,
                },
                "options": {
                    **asdict(self.options),
                    "output_dir": str(self.options.output_dir) if self.options.output_dir else None,
                },
                "dry_run": self.options.dry_run,
            },
        )

        print(f"[run] scenario={scenario.title}", flush=True)
        print(f"[run] loops={scenario.loops} output={run_dir}", flush=True)

        previous_reports: list[str] = []
        recent_discussion = ""
        timeline_items: list[str] = []
        errors_path = run_dir / "errors.jsonl"
        transcript_path = run_dir / "transcript.jsonl"

        for loop_index in range(1, scenario.loops + 1):
            loop_dir = run_dir / f"loop_{loop_index:02d}"
            loop_dir.mkdir(parents=True, exist_ok=True)
            print(f"\n[loop {loop_index}] compact", flush=True)
            compact = self._call_and_save(
                client_key="coordinator",
                call_type="compact",
                messages=[
                    {"role": "system", "content": COORDINATOR_SYSTEM},
                    {
                        "role": "user",
                        "content": compact_prompt(scenario, loop_index, previous_reports, recent_discussion),
                    },
                ],
                output_path=loop_dir / "compact.md",
                transcript_path=transcript_path,
                errors_path=errors_path,
                max_tokens=self.options.coordinator_max_tokens,
            )

            print(f"[loop {loop_index}] personas", flush=True)
            persona_text = self._call_and_save(
                client_key="coordinator",
                call_type="personas",
                messages=[
                    {"role": "system", "content": COORDINATOR_SYSTEM},
                    {"role": "user", "content": persona_prompt(scenario, compact)},
                ],
                output_path=loop_dir / "personas.raw.json",
                transcript_path=transcript_path,
                errors_path=errors_path,
                max_tokens=self.options.coordinator_max_tokens,
            )
            personas = self._load_personas(persona_text)
            write_json(loop_dir / "personas.json", {"roles": personas})
            write_text(loop_dir / "personas.md", self._render_personas(personas))

            loop_discussion_parts: list[str] = []
            for round_index in range(1, 4):
                current_round_parts: list[str] = []
                round_path = loop_dir / f"discussion_round_{round_index:02d}.jsonl"
                print(f"[loop {loop_index}] discussion_round={round_index}", flush=True)
                for persona in personas:
                    slot = str(persona["slot"])
                    role_name = str(persona.get("name") or slot)
                    prompt = role_prompt(
                        scenario=scenario,
                        compact=compact,
                        persona=persona,
                        loop_index=loop_index,
                        round_index=round_index,
                        current_round_context="\n\n".join(current_round_parts),
                        recent_history=trim_text(recent_discussion, self.options.recent_context_chars),
                    )
                    content, result = self._call(
                        client_key=slot,
                        call_type=f"role_{slot}",
                        messages=[
                            {"role": "system", "content": ROLE_SYSTEM},
                            {"role": "user", "content": prompt},
                        ],
                        transcript_path=transcript_path,
                        errors_path=errors_path,
                        max_tokens=self.options.role_max_tokens,
                    )
                    record = {
                        "loop": loop_index,
                        "round": round_index,
                        "slot": slot,
                        "role_name": role_name,
                        "represents": persona.get("represents"),
                        "content": content,
                        "usage": result_summary(result),
                    }
                    with round_path.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                    line = f"{role_name}({slot}): {content}"
                    current_round_parts.append(line)
                    loop_discussion_parts.append(f"[loop {loop_index} round {round_index} {role_name}/{slot}]\n{content}")
                    print(
                        f"  [{slot}] {role_name} "
                        f"{result.elapsed_seconds:.1f}s tokens={result.total_tokens} "
                        f"preview={content[:self.options.preview_chars].replace(chr(10), ' ')}",
                        flush=True,
                    )

            discussion_text = "\n\n".join(loop_discussion_parts)
            print(f"[loop {loop_index}] stage_report", flush=True)
            stage_report = self._call_and_save(
                client_key="coordinator",
                call_type="stage_report",
                messages=[
                    {"role": "system", "content": COORDINATOR_SYSTEM},
                    {"role": "user", "content": stage_report_prompt(scenario, loop_index, compact, discussion_text)},
                ],
                max_tokens=self.options.stage_max_tokens or 32768,
                output_path=loop_dir / "stage_report.md",
                transcript_path=transcript_path,
                errors_path=errors_path,
            )
            previous_reports.append(stage_report)
            recent_discussion = trim_text(discussion_text + "\n\n" + stage_report, self.options.recent_context_chars)
            timeline_items.append(f"loop_{loop_index:02d}: {loop_dir / 'stage_report.md'}")
            print(
                f"[loop {loop_index}] report_preview={stage_report[:self.options.preview_chars].replace(chr(10), ' ')}",
                flush=True,
            )

        print("\n[final] summary", flush=True)
        final_summary = self._call_and_save(
            client_key="coordinator",
            call_type="final_summary",
            messages=[
                {"role": "system", "content": COORDINATOR_SYSTEM},
                {
                    "role": "user",
                    "content": final_summary_prompt(scenario, previous_reports, "\n".join(timeline_items)),
                },
            ],
            output_path=run_dir / "final_summary.md",
            transcript_path=transcript_path,
            errors_path=errors_path,
            max_tokens=self.options.final_max_tokens,
        )
        print(f"[final] preview={final_summary[:self.options.preview_chars].replace(chr(10), ' ')}", flush=True)

        metrics = write_metrics(run_dir)
        print(
            f"[metrics] passed={metrics['passed']} calls={metrics['transcript']['call_count']} "
            f"tokens={metrics['transcript']['total_tokens']}",
            flush=True,
        )

        removed = prune_old_runs(self.root / "runs", self.options.keep_runs)
        if removed:
            print(f"[gc] removed_old_runs={len(removed)}", flush=True)
        print(f"[done] output={run_dir}", flush=True)
        return run_dir

    def _load_personas(self, text: str) -> list[dict[str, Any]]:
        data = parse_json_object(text)
        roles = data.get("roles")
        if not isinstance(roles, list) or len(roles) != 4:
            raise RuntimeError("Persona generation must return exactly four roles.")
        by_slot = {str(role.get("slot")): role for role in roles if isinstance(role, dict)}
        missing = [slot for slot in "ABCD" if slot not in by_slot]
        if missing:
            raise RuntimeError(f"Persona generation missing slots: {', '.join(missing)}")
        return [by_slot[slot] for slot in "ABCD"]

    def _render_personas(self, personas: list[dict[str, Any]]) -> str:
        parts = ["# Personas"]
        for persona in personas:
            parts.append(
                f"\n## {persona.get('slot')} - {persona.get('name')}\n"
                f"- Represents: {persona.get('represents')}\n"
                f"- Position: {persona.get('position')}\n"
                f"- Authority boundary: {persona.get('authority_boundary')}\n"
            )
        return "\n".join(parts)

    def _call_and_save(
        self,
        *,
        client_key: str,
        call_type: str,
        messages: list[dict[str, str]],
        output_path: Path,
        transcript_path: Path,
        errors_path: Path,
        max_tokens: int | None = None,
    ) -> str:
        content, _result = self._call(
            client_key=client_key,
            call_type=call_type,
            messages=messages,
            transcript_path=transcript_path,
            errors_path=errors_path,
            max_tokens=max_tokens,
        )
        write_text(output_path, content)
        return content

    def _call(
        self,
        *,
        client_key: str,
        call_type: str,
        messages: list[dict[str, str]],
        transcript_path: Path,
        errors_path: Path,
        max_tokens: int | None = None,
    ) -> tuple[str, ChatResult]:
        client = self.clients[client_key]
        started = time.time()
        try:
            result = client.chat(messages, max_tokens=max_tokens)
        except Exception as exc:
            errors_path.parent.mkdir(parents=True, exist_ok=True)
            with errors_path.open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "call_type": call_type,
                            "client_key": client_key,
                            "started_at_unix": started,
                            "error": str(exc),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            print(f"[error] call_type={call_type} client={client_key} error={exc}", flush=True)
            raise

        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        with transcript_path.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "call_type": call_type,
                        "client_key": client_key,
                        "usage": result_summary(result),
                        "content_preview": result.content[:500],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        return result.content, result
