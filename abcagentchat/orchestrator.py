from __future__ import annotations

import json
import re
import shutil
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .api import ChatResult, DeepSeekClient
from .background import DEFAULT_FULL_RECENT_COMPACTS, compact_archive_context, recent_context, split_compact_history
from .compact import compact_messages
from .config import COORDINATOR_MAX_TOKENS, ROLE_MAX_TOKENS, AppConfig
from .gc import prune_old_runs
from .layout import (
    compact_planning_loop_dir,
    compact_planning_root,
    final_summary_root,
    framework_root,
    process_loop_dir,
    process_root,
)
from .metrics import write_metrics
from .monitor import NullMonitor, RunMonitor
from .planning import default_discussion_plan, load_discussion_plan, render_discussion_plan
from .prompts import COORDINATOR_SYSTEM, compact_archive_summary_prompt, deliberation_plan_prompt, json_repair_prompt
from .reports import final_summary_messages, stage_report_messages
from .roles import run_discussion_group
from .runtime_io import result_summary, safe_slug, write_json, write_text
from .scenario import Scenario


TEMP_COMPACT = 0.0
TEMP_PLANNING = 0.2
TEMP_PLANNING_REPAIR = 0.0
TEMP_STAGE_REPORT = 0.0
TEMP_FINAL_SUMMARY = 0.5
DEFAULT_STAGE_MAX_TOKENS = COORDINATOR_MAX_TOKENS
DEFAULT_FINAL_MAX_TOKENS = COORDINATOR_MAX_TOKENS
DEFAULT_PLANNING_MAX_TOKENS = 8192
DEFAULT_PLANNING_CONTEXT_CHARS = 16000
FINAL_SECTION_SPECS = [
    ("discussion_result", "对这个问题讨论出来的结果", "01_discussion_result.md"),
    ("process_analysis", "对整个讨论流程的客观分析", "02_process_analysis.md"),
    ("synthesized_document", "原文的文档合成稿", "03_synthesized_document.md"),
    ("evidence_and_next_steps", "证据缺口与后续测试建议", "04_evidence_and_next_steps.md"),
]


@dataclass
class RunOptions:
    output_dir: Path | None = None
    keep_runs: int = 10
    dry_run: bool = False
    timeout: int = 600
    recent_context_chars: int = 32000
    planning_context_chars: int = DEFAULT_PLANNING_CONTEXT_CHARS
    preview_chars: int = 260
    max_loops: int = 3
    max_subcycles: int = 3
    rounds_per_subcycle: int = 3
    role_summary_round: bool = False
    coordinator_max_tokens: int | None = None
    planning_max_tokens: int | None = DEFAULT_PLANNING_MAX_TOKENS
    role_max_tokens: int | None = None
    stage_max_tokens: int | None = None
    final_max_tokens: int | None = None
    enable_monitor: bool = False


class DryRunClient:
    def __init__(self, label: str) -> None:
        self.label = label
        is_coordinator = label == "coordinator"
        default_reasoning = "max" if is_coordinator else None
        default_temperature = 0.2 if label == "coordinator" else 0.8
        default_max_tokens = COORDINATOR_MAX_TOKENS if label == "coordinator" else ROLE_MAX_TOKENS
        self.settings = type(
            "DrySettings",
            (),
            {
                "model": "dry-run",
                "thinking_enabled": is_coordinator,
                "reasoning_effort": default_reasoning,
                "max_tokens": default_max_tokens,
                "temperature": default_temperature,
            },
        )()

    def request_meta(
        self,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        effort = reasoning_effort if reasoning_effort is not None else self.settings.reasoning_effort
        payload = {
            "model": "dry-run",
            "thinking": {"type": "enabled" if self.settings.thinking_enabled else "disabled"},
            "max_tokens": max_tokens or self.settings.max_tokens,
            "temperature": self.settings.temperature if temperature is None else temperature,
        }
        if self.settings.thinking_enabled and effort:
            payload["reasoning_effort"] = effort
        return payload

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        reasoning_effort: str | None = None,
    ) -> ChatResult:
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
        if "请对整个议案讨论过程做最终总结" in last or "请对整个开放式议题讨论过程做最终总结" in last:
            return (
                "# 对这个问题讨论出来的结果\n\n"
                "本次 dry-run 验证了模块化编排、多轮上下文拼接、开放分歧记录和报告保存逻辑。\n\n"
                "# 对整个讨论流程的客观分析\n\n"
                "流程分析显示 compact、planning、并行角色轮和阶段报告均被保存，可供审计。\n\n"
                "# 原文的文档合成稿\n\n"
                "这是一份面向读者的合成稿占位，真实运行会在这里形成更长的议案文本。\n\n"
                "# 证据缺口与后续测试建议\n\n"
                "dry-run 不包含真实模型论证内容，因此只能验证结构，不能验证观点质量。"
            )
        if "请更新“更早 compact”的高质量滚动状态账本摘要" in last or "请更新“更早 compact”的高质量滚动开放讨论账本摘要" in last:
            covered_match = re.search(r"覆盖第 1-(\d+) 个循环", last)
            covered_until = covered_match.group(1) if covered_match else "1"
            return (
                f"# 更早 Compact 滚动开放讨论账本（覆盖第 1-{covered_until} 循环）\n\n"
                "## A. 长期稳定事实、数字、概念边界与硬约束\n\n"
                "- 继承：早期循环已形成稳定事实、概念争点和程序红线。\n\n"
                "## C. 概念争点生命周期账本\n\n"
                "| 争点/议题 | 当前状态 | 支持/反对/条件 | 关键演化历史 | 外部依赖 | 后续风险 |\n"
                "|---|---|---|---|---|---|\n"
                "| 自主/规训 | 继承 | 需继续讨论 | 已被纳入开放争点 | 外部审批待定 | 不能误写成共识 |\n\n"
                "## D. 视角立场与政治/治理观点演化\n\n"
                "- 继承：角色论证路径和自治、秩序、公平、专业责任之间的冲突应持续可见。"
            )
        if "请只输出 JSON" in last and '"groups"' in last:
            return json.dumps(default_discussion_plan(), ensure_ascii=False, indent=2)
        if "现在进行第" in last and "你的人格卡" in last:
            prior_assistants = sum(1 for message in messages if message.get("role") == "assistant")
            if "这是本子讨论组的第 4 轮总结" in last:
                return (
                    f"我代表本角色进行第 4 轮总结：本次调用前已有 {prior_assistants} 条 assistant 发言可见。"
                    "我的最终立场是有条件推进；仍有疑惑包括执行边界、外部审批和弱势群体保护；"
                    "下一轮 compact 应记录这些未决问题。"
                )
            return (
                f"我代表本角色发言：这是带有显式多轮上下文的 dry-run 发言。"
                f"本次调用前已有 {prior_assistants} 条 assistant 发言可见；我会回应前序意见，"
                "并要求把抽象争点、程序边界、政治观点和保留分歧写入后续 compact。"
            )
        if "请生成第" in last and ("阶段性报告" in last or "阶段性思想报告" in last):
            return "## 阶段性思想报告\n\n- 抽象争点：自主与规训仍在冲突。\n- 分歧：责任和审批边界仍需细化。\n- 下一步：保留强反对意见并引入新视角。"
        if "生成议案讨论 compact" in last or "议案状态账本 compact" in last or "开放讨论状态账本 compact" in last:
            return (
                "# Compact 开放讨论状态账本（第 1 循环）\n\n"
                "## 0. 本轮思想变化摘要\n\n"
                "- 新增：保留场景硬约束、概念争点和强分歧。\n\n"
                "## 1. 稳定事实、概念边界与硬约束\n\n"
                "| 事项 | 状态 | 内容 | 依据来源 | 对后续讨论的影响 |\n"
                "|---|---|---|---|---|\n"
                "| 场景边界 | 继承 | 原始议题和权限边界必须持续可见 | 原始场景 | 后续讨论不能越权 |\n\n"
                "## 4. 观点生态账本\n\n"
                "| 视角/角色 | 当前立场 | 可见论证路径 | 政治/治理观点 | 最强反方是谁 | 相比上一轮变化 |\n"
                "|---|---|---|---|---|---|\n"
                "| A/B/C/D | 分歧保留 | 从概念、事实、价值和风险推导结论 | 自治、秩序、公平、专业责任冲突 | 彼此构成反方 | 新增 |\n\n"
                "## 8. 防遗忘清单\n\n"
                "- 继承/新增/修订/废弃/外部待定状态必须持续可见。"
            )
        return "我代表本角色发言：保留开放讨论，要求把抽象争点、程序边界、政治观点和保留分歧写入后续 compact。"


class Simulator:
    def __init__(self, root: Path, config: AppConfig | None, options: RunOptions) -> None:
        self.root = root
        self.config = config
        self.options = options
        self.clients = self._build_clients()
        self._io_lock = threading.Lock()

    def _build_clients(self) -> dict[str, Any]:
        if self.options.dry_run:
            return {slot: DryRunClient(slot) for slot in ["coordinator", "A", "B", "C", "D"]}
        if self.config is None:
            raise RuntimeError("Config is required unless dry_run is enabled.")
        if self.config.backend == "local":
            from .local_diffusion import LocalDiffusionClient
            assert self.config.coordinator_local and self.config.role_local
            clients: dict[str, Any] = {
                "coordinator": LocalDiffusionClient(self.config.coordinator_local)
            }
            # One shared local model process, so all roles use the same role config;
            # roles.py runs them serially (snapshot-fair, identical to the old pool).
            for slot in self.config.role_keys:
                clients[slot] = LocalDiffusionClient(self.config.role_local)
            return clients
        clients = {
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
        for section_dir in (
            process_root(run_dir),
            compact_planning_root(run_dir),
            final_summary_root(run_dir),
            framework_root(run_dir),
        ):
            section_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(scenario.path, framework_root(run_dir) / "input.md")
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
        compact_archive_summary = ""
        compact_archive_summary_count = 0
        previous_reports: list[str] = []
        recent_discussion = ""
        timeline_items: list[str] = []
        errors_path = process_root(run_dir) / "errors.jsonl"
        transcript_path = process_root(run_dir) / "transcript.jsonl"

        for loop_index in range(1, effective_loops + 1):
            loop_process_dir = process_loop_dir(run_dir, loop_index)
            loop_compact_dir = compact_planning_loop_dir(run_dir, loop_index)
            loop_process_dir.mkdir(parents=True, exist_ok=True)
            loop_compact_dir.mkdir(parents=True, exist_ok=True)
            compact_archive_summary, compact_archive_summary_count = self._refresh_compact_archive_summary(
                scenario=scenario,
                compact_history=compact_history,
                current_summary=compact_archive_summary,
                summarized_count=compact_archive_summary_count,
                loop_dir=loop_compact_dir,
                transcript_path=transcript_path,
                errors_path=errors_path,
                monitor=monitor,
            )

            compact = self._run_compact(
                scenario,
                loop_index,
                compact_history,
                compact_archive_summary,
                previous_reports,
                recent_discussion,
                loop_compact_dir,
                transcript_path,
                errors_path,
                monitor,
            )
            background_context = compact_archive_context(
                scenario,
                compact_history,
                earlier_summary=compact_archive_summary,
            )
            write_text(loop_compact_dir / "background_context.md", background_context)
            plan = self._run_planning(scenario, compact, background_context, loop_index, loop_compact_dir, transcript_path, errors_path, monitor)

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
                        loop_dir=loop_process_dir,
                        role_max_tokens=self.options.role_max_tokens,
                        preview_chars=self.options.preview_chars,
                        include_summary_round=self.options.role_summary_round,
                        parallel_roles=(self.config is None or self.config.backend != "local"),
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
                scenario, loop_index, compact, discussion_text, loop_process_dir, transcript_path, errors_path, monitor
            )
            compact_history.append(compact)
            previous_reports.append(stage_report)
            recent_discussion = recent_context(discussion_text + "\n\n" + stage_report, self.options.recent_context_chars)
            timeline_items.append(f"loop_{loop_index:02d}: process/loop_{loop_index:02d}/stage_report.md")

        final_summary = self._run_final_summary(scenario, previous_reports, timeline_items, run_dir, transcript_path, errors_path, monitor)
        self._write_final_artifacts(run_dir, final_summary, timeline_items)
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
            framework_root(run_dir) / "run_config.json",
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
        compact_archive_summary: str,
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
            messages=compact_messages(
                scenario,
                loop_index,
                compact_history,
                compact_archive_summary,
                previous_reports,
                recent_discussion,
            ),
            output_path=loop_dir / "compact.md",
            transcript_path=transcript_path,
            errors_path=errors_path,
            max_tokens=self.options.coordinator_max_tokens,
            monitor=monitor,
            reasoning_effort="max",
            temperature=TEMP_COMPACT,
        )

    def _refresh_compact_archive_summary(
        self,
        *,
        scenario: Scenario,
        compact_history: list[str],
        current_summary: str,
        summarized_count: int,
        loop_dir: Path,
        transcript_path: Path,
        errors_path: Path,
        monitor: RunMonitor,
    ) -> tuple[str, int]:
        older, _recent = split_compact_history(compact_history, recent_count=DEFAULT_FULL_RECENT_COMPACTS)
        target_count = len(older)
        if target_count <= summarized_count:
            return current_summary, summarized_count
        newly_archived = [
            (index, compact_history[index - 1])
            for index in range(summarized_count + 1, target_count + 1)
        ]
        print(f"[archive] summarize_compacts=1-{target_count}", flush=True)
        monitor.update("running", f"archive compact summary 1-{target_count}")
        summary = self._call_and_save(
            client_key="coordinator",
            call_type="compact_archive_summary",
            messages=[
                {"role": "system", "content": COORDINATOR_SYSTEM},
                {
                    "role": "user",
                    "content": compact_archive_summary_prompt(
                        scenario,
                        current_summary,
                        newly_archived,
                        target_count,
                    ),
                },
            ],
            output_path=loop_dir / "compact_archive_summary.md",
            transcript_path=transcript_path,
            errors_path=errors_path,
            max_tokens=self.options.coordinator_max_tokens,
            monitor=monitor,
            reasoning_effort="max",
            temperature=TEMP_COMPACT,
        )
        write_text(loop_dir.parent / "compact_archive_summary.md", summary)
        return summary, target_count

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
                        self._trim_planning_text(compact, "compact"),
                        max_groups=self.options.max_subcycles,
                        background_context=self._trim_planning_text(background_context, "background"),
                    ),
                },
            ],
            output_path=loop_dir / "discussion_plan.raw.json",
            transcript_path=transcript_path,
            errors_path=errors_path,
            max_tokens=self.options.planning_max_tokens or DEFAULT_PLANNING_MAX_TOKENS,
            monitor=monitor,
            reasoning_effort="max",
            temperature=TEMP_PLANNING,
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
            max_tokens=self.options.planning_max_tokens or DEFAULT_PLANNING_MAX_TOKENS,
            monitor=monitor,
            reasoning_effort="max",
            temperature=TEMP_PLANNING_REPAIR,
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

    def _trim_planning_text(self, text: str, label: str) -> str:
        max_chars = max(0, int(self.options.planning_context_chars or 0))
        if not max_chars or len(text) <= max_chars:
            return text
        marker = (
            f"\n\n[... {label} 中段省略 {len(text) - max_chars} 字符；"
            "planning 只保留开头约束与结尾最近状态，完整 compact 仍保存在文件中 ...]\n\n"
        )
        head_chars = max(2000, int(max_chars * 0.42))
        tail_chars = max(2000, max_chars - head_chars - len(marker))
        if head_chars + tail_chars + len(marker) >= len(text):
            return text
        return text[:head_chars].rstrip() + marker + text[-tail_chars:].lstrip()

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
            max_tokens=self.options.stage_max_tokens or DEFAULT_STAGE_MAX_TOKENS,
            output_path=loop_dir / "stage_report.md",
            transcript_path=transcript_path,
            errors_path=errors_path,
            monitor=monitor,
            reasoning_effort="max",
            temperature=TEMP_STAGE_REPORT,
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
            output_path=final_summary_root(run_dir) / "final_summary.md",
            transcript_path=transcript_path,
            errors_path=errors_path,
            max_tokens=self.options.final_max_tokens or DEFAULT_FINAL_MAX_TOKENS,
            monitor=monitor,
            reasoning_effort="max",
            temperature=TEMP_FINAL_SUMMARY,
        )

    def _write_final_artifacts(self, run_dir: Path, final_summary: str, timeline_items: list[str]) -> None:
        final_dir = final_summary_root(run_dir)
        final_dir.mkdir(parents=True, exist_ok=True)
        write_text(final_dir / "final_summary.md", final_summary)
        write_text(final_dir / "00_full_final_summary.md", final_summary)

        split_sections = self._split_final_summary_sections(final_summary)
        files: list[dict[str, Any]] = []
        for key, title, filename in FINAL_SECTION_SPECS:
            content = split_sections.get(key)
            parsed = bool(content)
            if not content:
                content = f"# {title}\n\n本节未能从模型输出中按标准一级标题解析出来。请查看 `00_full_final_summary.md`。"
            write_text(final_dir / filename, content)
            files.append(
                {
                    "key": key,
                    "title": title,
                    "filename": filename,
                    "chars": len(content),
                    "parsed": parsed,
                }
            )

        timeline = ["# Process Timeline", ""]
        if timeline_items:
            timeline.extend(f"- {item}" for item in timeline_items)
        else:
            timeline.append("- No loop stage reports were produced.")
        write_text(final_dir / "process_timeline.md", "\n".join(timeline))
        write_text(
            final_dir / "README.md",
            "\n".join(
                [
                    "# Final Package",
                    "",
                    "标准最终阶段会同时保留完整模型输出和拆分后的阅读文件。",
                    "",
                    "## Recommended Reading Order",
                    "",
                    "- `01_discussion_result.md`: 议题结果、条件共识、不可化约分歧和权限边界。",
                    "- `02_process_analysis.md`: 对规划、compact、角色碰撞、阶段报告和上下文保持的客观分析。",
                    "- `03_synthesized_document.md`: 面向读者/委员会/归档的正式合成稿。",
                    "- `04_evidence_and_next_steps.md`: 证据缺口、后续测试和运行风险。",
                    "- `00_full_final_summary.md`: 未拆分的完整模型输出，供审计和排错。",
                    "",
                ]
            ),
        )
        write_json(final_dir / "manifest.json", {"files": files})

        output_tree = self._render_output_tree(run_dir)
        write_text(final_dir / "output_tree.md", output_tree)
        write_text(
            framework_root(run_dir) / "run_index.md",
            "\n".join(
                [
                    "# Run Index",
                    "",
                    "This file summarizes the categorized run artifact layout.",
                    "",
                    "## Top-Level Sections",
                    "",
                    "- `process/`: raw execution evidence, role discussion rounds, stage reports, transcript, errors, audit, and metrics.",
                    "- `compact and planning/`: compact ledgers, compact archive summaries, background contexts, and planning JSON/Markdown.",
                    "- `final summary/`: final summary output and reader-facing split documents.",
                    "- `framework/`: original scenario snapshot, effective runtime config, and artifact index.",
                    "",
                    "## Key Files",
                    "",
                    "- `framework/input.md`: original scenario snapshot.",
                    "- `framework/run_config.json`: effective loop/profile/runtime options.",
                    "- `monitor.html` and `status.json`: browser-readable live monitor outputs when monitoring is enabled.",
                    "- `process/transcript.jsonl`: request metadata, usage, and previews for every model call.",
                    "- `compact and planning/loop_XX/compact.md`: inherited open discussion state ledger.",
                    "- `compact and planning/loop_XX/discussion_plan.md`: per-loop perspective and group planning.",
                    "- `process/loop_XX/subcycle_*/discussion_round_*.jsonl`: role discussion records.",
                    "- `process/loop_XX/stage_report.md`: stage-level thought report.",
                    "- `final summary/final_summary.md` and `final summary/00_full_final_summary.md`: full final summary stage output.",
                    "- `final summary/01_discussion_result.md`: discussion result landscape and conditional recommendations.",
                    "- `final summary/02_process_analysis.md`: objective workflow/process analysis.",
                    "- `final summary/03_synthesized_document.md`: reader-facing synthesized document.",
                    "- `final summary/04_evidence_and_next_steps.md`: evidence gaps and follow-up testing recommendations.",
                    "- `final summary/manifest.json`: final package file manifest.",
                    "- `final summary/process_timeline.md`: loop report timeline.",
                    "- `final summary/output_tree.md`: complete artifact tree.",
                    "",
                    "## Artifact Tree",
                    "",
                    output_tree,
                ]
            ),
        )

    def _split_final_summary_sections(self, final_summary: str) -> dict[str, str]:
        headings = {f"# {title}": key for key, title, _filename in FINAL_SECTION_SPECS}
        sections: dict[str, list[str]] = {}
        current_key: str | None = None
        for line in final_summary.splitlines():
            stripped = line.strip()
            if stripped in headings:
                current_key = headings[stripped]
                sections[current_key] = [line]
                continue
            if current_key:
                sections[current_key].append(line)
        return {
            key: "\n".join(lines).strip()
            for key, lines in sections.items()
            if "\n".join(lines).strip()
        }

    def _render_output_tree(self, run_dir: Path) -> str:
        lines = ["# Output Tree", ""]
        for path in sorted(run_dir.rglob("*")):
            rel = path.relative_to(run_dir)
            if any(part.startswith(".") for part in rel.parts):
                continue
            indent = "  " * (len(rel.parts) - 1)
            suffix = "/" if path.is_dir() else ""
            lines.append(f"{indent}- {rel.name}{suffix}")
        return "\n".join(lines)

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
        reasoning_effort: str | None = None,
        temperature: float | None = None,
    ) -> str:
        content, _result = self._call(
            client_key=client_key,
            call_type=call_type,
            messages=messages,
            transcript_path=transcript_path,
            errors_path=errors_path,
            max_tokens=max_tokens,
            monitor=monitor,
            reasoning_effort=reasoning_effort,
            temperature=temperature,
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
        reasoning_effort: str | None = None,
        temperature: float | None = None,
    ) -> tuple[str, ChatResult]:
        client = self.clients[client_key]
        started = time.time()
        try:
            result = client.chat(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                reasoning_effort=reasoning_effort,
            )
        except Exception as exc:
            with self._io_lock:
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

        request_meta = (
            client.request_meta(max_tokens=max_tokens, temperature=temperature, reasoning_effort=reasoning_effort)
            if hasattr(client, "request_meta")
            else {}
        )
        with self._io_lock:
            transcript_path.parent.mkdir(parents=True, exist_ok=True)
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
                monitor.record_call(call_type, result_summary(result))
        return result.content, result
