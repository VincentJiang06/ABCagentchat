from __future__ import annotations

import json
import shutil
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .api import ChatResult, DeepSeekClient
from .background import compact_archive_context, recent_context
from .compact import compact_messages
from .config import AppConfig
from .gc import prune_old_runs
from .metrics import write_metrics
from .monitor import NullMonitor, RunMonitor
from .planning import default_discussion_plan, load_discussion_plan, render_discussion_plan
from .prompts import COORDINATOR_SYSTEM, deliberation_plan_prompt, json_repair_prompt
from .reports import final_summary_messages, stage_report_messages
from .roles import run_discussion_group
from .runtime_io import result_summary, safe_slug, write_json, write_text
from .scenario import Scenario


@dataclass
class RunOptions:
    output_dir: Path | None = None
    keep_runs: int = 10
    dry_run: bool = False
    timeout: int = 600
    recent_context_chars: int = 32000
    preview_chars: int = 260
    max_loops: int = 100
    max_subcycles: int = 3
    rounds_per_subcycle: int = 3
    coordinator_max_tokens: int | None = None
    role_max_tokens: int | None = None
    stage_max_tokens: int | None = None
    final_max_tokens: int | None = None
    enable_monitor: bool = False


class DryRunClient:
    def __init__(self, label: str) -> None:
        self.label = label
        self.settings = type(
            "DrySettings",
            (),
            {
                "model": "dry-run",
                "thinking_enabled": label == "coordinator",
                "reasoning_effort": "max" if label == "coordinator" else None,
                "max_tokens": 1024,
                "temperature": 0.0,
            },
        )()

    def request_meta(self, *, max_tokens: int | None = None) -> dict[str, Any]:
        return {
            "model": "dry-run",
            "thinking": {"type": "enabled" if self.label == "coordinator" else "disabled"},
            "reasoning_effort": "max" if self.label == "coordinator" else None,
            "max_tokens": max_tokens or 1024,
            "temperature": 0.0,
        }

    def chat(self, messages: list[dict[str, str]], *, max_tokens: int | None = None, temperature: float | None = None) -> ChatResult:
        content = self._fake_content(messages)
        prompt_tokens = sum(len(message.get("content", "")) // 2 for message in messages)
        completion_tokens = len(content) // 2
        return ChatResult(
            content=content,
            elapsed_seconds=0.01,
            finish_reason="dry_run",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            reasoning_tokens=0,
            total_tokens=prompt_tokens + completion_tokens,
            raw={"dry_run": True, "client": self.label},
        )

    def _fake_content(self, messages: list[dict[str, str]]) -> str:
        last = messages[-1]["content"]
        if "请对整个议案讨论过程做最终总结" in last:
            return "## 最终总结\n\n本次 dry-run 验证了模块化编排、多轮上下文拼接和报告保存逻辑。"
        if "请只输出 JSON" in last and '"groups"' in last:
            return json.dumps(default_discussion_plan(), ensure_ascii=False, indent=2)
        if "现在进行第" in last and "你的人格卡" in last:
            prior_assistants = sum(1 for message in messages if message.get("role") == "assistant")
            return (
                f"我代表本角色发言：这是带有显式多轮上下文的 dry-run 发言。"
                f"本次调用前已有 {prior_assistants} 条 assistant 发言可见；我会回应前序意见，"
                "并要求把程序边界、责任主体、政治观点和可执行动作写入修订条款。"
            )
        if "请生成第" in last and "阶段性报告" in last:
            return "## 阶段性报告\n\n- 共识：需要保留硬约束并形成试点。\n- 分歧：责任和审批边界仍需细化。\n- 下一步：将争议条款改写为可表决文本。"
        if "生成议案讨论 compact" in last:
            return "## Compact\n\n- 当前事实：保留场景硬约束。\n- 论证路径：记录角色如何从事实、价值和风险推导结论。\n- 政治观点：标记自治、秩序、公平、专业责任之间的冲突。"
        return "我代表本角色发言：支持继续推进，但要求把程序边界、政治观点和可执行动作写入修订条款。"


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
        effective_loops = min(scenario.loops, self.options.max_loops)
        shutil.copy2(scenario.path, run_dir / "input.md")
        self._write_run_config(run_dir, scenario, effective_loops)
        monitor = RunMonitor(run_dir, scenario_title=scenario.title, total_loops=effective_loops) if self.options.enable_monitor else NullMonitor()

        print(f"[run] scenario={scenario.title}", flush=True)
        if effective_loops < scenario.loops:
            print(f"[run] requested_loops={scenario.loops} capped_to={effective_loops}", flush=True)
        print(f"[run] loops={effective_loops} output={run_dir}", flush=True)
        if self.options.enable_monitor:
            print(f"[monitor] file={run_dir / 'monitor.html'}", flush=True)
        else:
            print("[monitor] disabled; read Markdown/JSONL artifacts in output directory", flush=True)

        compact_history: list[str] = []
        previous_reports: list[str] = []
        recent_discussion = ""
        timeline_items: list[str] = []
        errors_path = run_dir / "errors.jsonl"
        transcript_path = run_dir / "transcript.jsonl"

        for loop_index in range(1, effective_loops + 1):
            loop_dir = run_dir / f"loop_{loop_index:02d}"
            loop_dir.mkdir(parents=True, exist_ok=True)

            compact = self._run_compact(
                scenario,
                loop_index,
                compact_history,
                previous_reports,
                recent_discussion,
                loop_dir,
                transcript_path,
                errors_path,
                monitor,
            )
            background_context = compact_archive_context(scenario, compact_history)
            write_text(loop_dir / "background_context.md", background_context)
            plan = self._run_planning(scenario, compact, background_context, loop_index, loop_dir, transcript_path, errors_path, monitor)

            loop_discussion_parts: list[str] = []
            for subcycle_index, group in enumerate(plan["groups"], start=1):
                group_title = str(group["title"])
                print(f"[loop {loop_index}] subcycle={subcycle_index} title={group_title}", flush=True)
                monitor.update("running", f"loop {loop_index}: subcycle {subcycle_index} {group_title}", current_loop=loop_index)
                loop_discussion_parts.extend(
                    run_discussion_group(
                        scenario=scenario,
                        compact=compact,
                        group=group,
                        loop_index=loop_index,
                        subcycle_index=subcycle_index,
                        rounds_per_subcycle=self.options.rounds_per_subcycle,
                        recent_history=recent_context(recent_discussion, self.options.recent_context_chars),
                        background_context=background_context,
                        loop_dir=loop_dir,
                        role_max_tokens=self.options.role_max_tokens,
                        preview_chars=self.options.preview_chars,
                        call_role=lambda client_key, call_type, messages, max_tokens, context_meta: self._call(
                            client_key=client_key,
                            call_type=call_type,
                            messages=messages,
                            transcript_path=transcript_path,
                            errors_path=errors_path,
                            max_tokens=max_tokens,
                            monitor=monitor,
                            context_meta=context_meta,
                        ),
                    )
                )

            discussion_text = "\n\n".join(loop_discussion_parts)
            stage_report = self._run_stage_report(
                scenario, loop_index, compact, discussion_text, loop_dir, transcript_path, errors_path, monitor
            )
            compact_history.append(compact)
            previous_reports.append(stage_report)
            recent_discussion = recent_context(discussion_text + "\n\n" + stage_report, self.options.recent_context_chars)
            timeline_items.append(f"loop_{loop_index:02d}: {loop_dir / 'stage_report.md'}")

        final_summary = self._run_final_summary(scenario, previous_reports, timeline_items, run_dir, transcript_path, errors_path, monitor)
        print(f"[final] preview={final_summary[:self.options.preview_chars].replace(chr(10), ' ')}", flush=True)

        metrics = write_metrics(run_dir)
        monitor.update(
            "done",
            "completed",
            call_count=metrics["transcript"]["call_count"],
            total_tokens=metrics["transcript"]["total_tokens"],
            by_type=metrics["transcript"]["by_type"],
        )
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

    def _write_run_config(self, run_dir: Path, scenario: Scenario, effective_loops: int) -> None:
        write_json(
            run_dir / "run_config.json",
            {
                "scenario": {
                    "path": str(scenario.path),
                    "title": scenario.title,
                    "requested_loops": scenario.loops,
                    "loops": effective_loops,
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

    def _run_compact(
        self,
        scenario: Scenario,
        loop_index: int,
        compact_history: list[str],
        previous_reports: list[str],
        recent_discussion: str,
        loop_dir: Path,
        transcript_path: Path,
        errors_path: Path,
        monitor: RunMonitor,
    ) -> str:
        print(f"\n[loop {loop_index}] compact", flush=True)
        monitor.update("running", f"loop {loop_index}: compact", current_loop=loop_index)
        return self._call_and_save(
            client_key="coordinator",
            call_type="compact",
            messages=compact_messages(scenario, loop_index, compact_history, previous_reports, recent_discussion),
            output_path=loop_dir / "compact.md",
            transcript_path=transcript_path,
            errors_path=errors_path,
            max_tokens=self.options.coordinator_max_tokens,
            monitor=monitor,
        )

    def _run_planning(
        self,
        scenario: Scenario,
        compact: str,
        background_context: str,
        loop_index: int,
        loop_dir: Path,
        transcript_path: Path,
        errors_path: Path,
        monitor: RunMonitor,
    ) -> dict[str, Any]:
        print(f"[loop {loop_index}] planning", flush=True)
        monitor.update("running", f"loop {loop_index}: discussion planning", current_loop=loop_index)
        plan_text = self._call_and_save(
            client_key="coordinator",
            call_type="planning",
            messages=[
                {"role": "system", "content": COORDINATOR_SYSTEM},
                {
                    "role": "user",
                    "content": deliberation_plan_prompt(
                        scenario,
                        compact,
                        max_groups=self.options.max_subcycles,
                        background_context=background_context,
                    ),
                },
            ],
            output_path=loop_dir / "discussion_plan.raw.json",
            transcript_path=transcript_path,
            errors_path=errors_path,
            max_tokens=self.options.coordinator_max_tokens,
            monitor=monitor,
        )
        try:
            plan = load_discussion_plan(plan_text, max_groups=self.options.max_subcycles)
        except Exception as exc:
            print(f"[loop {loop_index}] planning_parse_error={exc}", flush=True)
            plan = self._repair_or_fallback_plan(plan_text, loop_index, loop_dir, transcript_path, errors_path, monitor)
        write_json(loop_dir / "discussion_plan.json", plan)
        write_text(loop_dir / "discussion_plan.md", render_discussion_plan(plan))
        return plan

    def _repair_or_fallback_plan(
        self,
        plan_text: str,
        loop_index: int,
        loop_dir: Path,
        transcript_path: Path,
        errors_path: Path,
        monitor: RunMonitor,
    ) -> dict[str, Any]:
        monitor.update("running", f"loop {loop_index}: repair planning JSON", current_loop=loop_index)
        repaired_text = self._call_and_save(
            client_key="coordinator",
            call_type="planning_repair",
            messages=[
                {"role": "system", "content": COORDINATOR_SYSTEM},
                {"role": "user", "content": json_repair_prompt(plan_text)},
            ],
            output_path=loop_dir / "discussion_plan.repaired.json",
            transcript_path=transcript_path,
            errors_path=errors_path,
            max_tokens=self.options.coordinator_max_tokens,
            monitor=monitor,
        )
        try:
            return load_discussion_plan(repaired_text, max_groups=self.options.max_subcycles)
        except Exception as repair_exc:
            warnings_path = errors_path.with_name("warnings.jsonl")
            with warnings_path.open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "call_type": "planning_parse",
                            "client_key": "coordinator",
                            "error": str(repair_exc),
                            "fallback": "default_discussion_plan",
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            return default_discussion_plan()

    def _run_stage_report(
        self,
        scenario: Scenario,
        loop_index: int,
        compact: str,
        discussion_text: str,
        loop_dir: Path,
        transcript_path: Path,
        errors_path: Path,
        monitor: RunMonitor,
    ) -> str:
        print(f"[loop {loop_index}] stage_report", flush=True)
        monitor.update("running", f"loop {loop_index}: stage report", current_loop=loop_index)
        stage_report = self._call_and_save(
            client_key="coordinator",
            call_type="stage_report",
            messages=stage_report_messages(scenario, loop_index, compact, discussion_text),
            max_tokens=self.options.stage_max_tokens or 32768,
            output_path=loop_dir / "stage_report.md",
            transcript_path=transcript_path,
            errors_path=errors_path,
            monitor=monitor,
        )
        print(f"[loop {loop_index}] report_preview={stage_report[:self.options.preview_chars].replace(chr(10), ' ')}", flush=True)
        return stage_report

    def _run_final_summary(
        self,
        scenario: Scenario,
        previous_reports: list[str],
        timeline_items: list[str],
        run_dir: Path,
        transcript_path: Path,
        errors_path: Path,
        monitor: RunMonitor,
    ) -> str:
        print("\n[final] summary", flush=True)
        monitor.update("running", "final summary")
        return self._call_and_save(
            client_key="coordinator",
            call_type="final_summary",
            messages=final_summary_messages(scenario, previous_reports, "\n".join(timeline_items)),
            output_path=run_dir / "final_summary.md",
            transcript_path=transcript_path,
            errors_path=errors_path,
            max_tokens=self.options.final_max_tokens,
            monitor=monitor,
        )

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
        monitor: RunMonitor | None = None,
    ) -> str:
        content, _result = self._call(
            client_key=client_key,
            call_type=call_type,
            messages=messages,
            transcript_path=transcript_path,
            errors_path=errors_path,
            max_tokens=max_tokens,
            monitor=monitor,
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
        monitor: RunMonitor | None = None,
        context_meta: dict[str, Any] | None = None,
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
            if monitor is not None:
                monitor.record_error(f"error: {call_type}")
            print(f"[error] call_type={call_type} client={client_key} error={exc}", flush=True)
            raise

        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        request_meta = client.request_meta(max_tokens=max_tokens) if hasattr(client, "request_meta") else {}
        with transcript_path.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "call_type": call_type,
                        "client_key": client_key,
                        "request": request_meta,
                        "messages": {
                            "count": len(messages),
                            "assistant_count": sum(1 for message in messages if message.get("role") == "assistant"),
                            "user_count": sum(1 for message in messages if message.get("role") == "user"),
                        },
                        "context": context_meta or {},
                        "usage": result_summary(result),
                        "content_preview": result.content[:500],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        if monitor is not None:
            monitor.record_call(call_type, result.total_tokens)
        return result.content, result
