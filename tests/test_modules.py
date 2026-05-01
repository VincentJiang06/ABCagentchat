from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from abcagentchat.api import ChatResult, DeepSeekClient, ModelSettings
from abcagentchat.background import compact_archive_context, compact_excerpt, previous_reports_context, recent_context, split_compact_history
from abcagentchat.compact import compact_messages
from abcagentchat.conversation import Conversation
from abcagentchat.deep_summary import (
    build_context_bundle,
    collect_summary_artifacts,
    deep_final_summary_messages,
    split_deep_summary_package,
    write_deep_summary_package,
)
from abcagentchat.monitor import NullMonitor, RunMonitor
from abcagentchat.planning import default_discussion_plan, load_discussion_plan, render_discussion_plan
from abcagentchat.reports import final_summary_messages, stage_report_messages
from abcagentchat.roles import collect_discussion_parts, run_discussion_group
from abcagentchat.runtime_io import parse_json_object, result_summary, safe_slug, write_json, write_text
from abcagentchat.scenario import Scenario


def make_scenario() -> Scenario:
    return Scenario(
        path=Path("scenario.md"),
        title="测试议案",
        loops=2,
        domain="unit_test",
        source_refs=[{"title": "来源", "url": "https://example.com"}],
        primary_tests=["fact_retention", "boundary"],
        body="# 原始议题\n需要讨论是否试点。",
    )


def fake_result(content: str = "ok", total_tokens: int = 10) -> ChatResult:
    return ChatResult(
        content=content,
        elapsed_seconds=0.01,
        finish_reason="stop",
        prompt_tokens=3,
        completion_tokens=4,
        reasoning_tokens=0,
        total_tokens=total_tokens,
        raw={},
    )


class ApiModuleTests(unittest.TestCase):
    def test_payload_records_max_and_high_thinking(self) -> None:
        coordinator = DeepSeekClient(
            "key",
            ModelSettings("deepseek-v4-pro", "https://api.deepseek.com", 8192, thinking_enabled=True, reasoning_effort="max"),
        )
        role = DeepSeekClient(
            "key",
            ModelSettings(
                "deepseek-v4-pro",
                "https://api.deepseek.com",
                6144,
                thinking_enabled=False,
                reasoning_effort=None,
                temperature=0.8,
            ),
        )
        self.assertEqual(coordinator.build_payload([{"role": "user", "content": "x"}])["reasoning_effort"], "max")
        self.assertEqual(
            coordinator.build_payload([{"role": "user", "content": "x"}], reasoning_effort="high")["reasoning_effort"],
            "high",
        )
        role_payload = role.build_payload([{"role": "user", "content": "x"}])
        self.assertEqual(role_payload["thinking"], {"type": "disabled"})
        self.assertNotIn("reasoning_effort", role_payload)
        self.assertEqual(role_payload["max_tokens"], 6144)
        self.assertEqual(role_payload["temperature"], 0.8)
        coordinator_meta = coordinator.request_meta(max_tokens=1234, temperature=0.0, reasoning_effort="max")
        self.assertEqual(coordinator_meta["max_tokens"], 1234)
        self.assertEqual(coordinator_meta["temperature"], 0.0)
        self.assertEqual(coordinator_meta["reasoning_effort"], "max")
        role_meta = role.request_meta(max_tokens=6144, temperature=0.8)
        self.assertEqual(role_meta["thinking"], {"type": "disabled"})
        self.assertNotIn("reasoning_effort", role_meta)


class BackgroundModuleTests(unittest.TestCase):
    def test_compact_archive_includes_original_issue_and_history(self) -> None:
        context = compact_archive_context(make_scenario(), ["compact-1", "compact-2"])
        self.assertIn("# 原始议题全文", context)
        self.assertIn("需要讨论是否试点", context)
        self.assertIn("第 1 个循环 compact", context)
        self.assertIn("compact-2", context)

    def test_compact_archive_uses_summary_for_older_history(self) -> None:
        context = compact_archive_context(
            make_scenario(),
            ["compact-1", "compact-2", "compact-3", "compact-4", "compact-5"],
            earlier_summary="早期高质量摘要",
        )
        self.assertIn("第 1-1 个循环 compact 滚动开放讨论账本摘要", context)
        self.assertIn("早期高质量摘要", context)
        self.assertIn("第 1 个循环 compact（梯度摘录", context)
        self.assertIn("## 第 2 个循环 compact（全文）\ncompact-2", context)
        self.assertIn("## 第 5 个循环 compact（全文）\ncompact-5", context)

    def test_split_compact_history_keeps_latest_four_full_by_default(self) -> None:
        older, recent = split_compact_history(["c1", "c2", "c3", "c4", "c5"], recent_count=3)
        self.assertEqual(older, ["c1", "c2"])
        self.assertEqual(recent, ["c3", "c4", "c5"])
        older_default, recent_default = split_compact_history(["c1", "c2", "c3", "c4", "c5"])
        self.assertEqual(older_default, ["c1"])
        self.assertEqual(recent_default, ["c2", "c3", "c4", "c5"])

    def test_compact_excerpt_keeps_head_and_tail(self) -> None:
        excerpt = compact_excerpt("a" * 500 + "TAIL", 120)
        self.assertTrue(excerpt.startswith("a"))
        self.assertIn("梯度省略", excerpt)
        self.assertTrue(excerpt.endswith("TAIL"))

    def test_recent_and_previous_reports_context(self) -> None:
        self.assertEqual(recent_context("abcdef", 3), "def")
        self.assertIn("r2", previous_reports_context(["r1", "r2"], keep=1))
        self.assertNotIn("r1", previous_reports_context(["r1", "r2"], keep=1))


class CompactPromptModuleTests(unittest.TestCase):
    def test_compact_messages_inject_history_archive(self) -> None:
        messages = compact_messages(make_scenario(), 2, ["compact-1"], "", ["report-1"], "recent-role-talk")
        self.assertEqual(messages[0]["role"], "system")
        user = messages[1]["content"]
        self.assertIn("原始议题与历史 compact 档案", user)
        self.assertIn("compact-1", user)
        self.assertIn("recent-role-talk", user)
        self.assertIn("开放讨论状态账本", user)
        self.assertIn("抽象问题与概念争点", user)
        self.assertIn("观点生态账本", user)
        self.assertIn("继承", user)
        self.assertIn("外部待定", user)


class PlanningModuleTests(unittest.TestCase):
    def test_plan_loader_limits_groups_and_orders_slots(self) -> None:
        raw = {
            "planning_note": "note",
            "groups": [
                {
                    "group_id": "a",
                    "title": "一组",
                    "purpose": "测试",
                    "roles": [{"slot": slot, "name": slot} for slot in "DCBA"],
                },
                {
                    "group_id": "b",
                    "title": "二组",
                    "purpose": "测试",
                    "roles": [{"slot": slot, "name": slot} for slot in "ABCD"],
                },
            ],
        }
        plan = load_discussion_plan(json.dumps(raw, ensure_ascii=False), max_groups=1)
        self.assertEqual(len(plan["groups"]), 1)
        self.assertEqual([role["slot"] for role in plan["groups"][0]["roles"]], list("ABCD"))
        self.assertIn("Political viewpoint", render_discussion_plan(default_discussion_plan()))

    def test_plan_loader_rejects_missing_slots(self) -> None:
        raw = {"groups": [{"roles": [{"slot": "A"}, {"slot": "B"}, {"slot": "C"}]}]}
        with self.assertRaises(RuntimeError):
            load_discussion_plan(json.dumps(raw), max_groups=1)


class ConversationModuleTests(unittest.TestCase):
    def test_messages_for_uses_stateless_api_pattern(self) -> None:
        conversation = Conversation("system")
        conversation.append_exchange("u1", "a1")
        messages = conversation.messages_for("u2")
        self.assertEqual(messages, [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
        ])


class RolesModuleTests(unittest.TestCase):
    def test_role_group_writes_rounds_and_accumulates_assistant_context(self) -> None:
        calls: list[dict[str, object]] = []

        def call_role(client_key: str, call_type: str, messages: list[dict[str, str]], max_tokens: int | None, context_meta: dict[str, object] | None):
            calls.append({
                "client_key": client_key,
                "call_type": call_type,
                "assistant_count": sum(1 for message in messages if message["role"] == "assistant"),
                "system": messages[0]["content"],
                "user_text": "\n".join(message["content"] for message in messages if message["role"] == "user"),
                "context_meta": context_meta,
                "max_tokens": max_tokens,
            })
            return f"{client_key} response {len(calls)}", fake_result(total_tokens=10 + len(calls))

        with tempfile.TemporaryDirectory() as tmp:
            group = default_discussion_plan()["groups"][0]
            with redirect_stdout(StringIO()):
                parts = run_discussion_group(
                    scenario=make_scenario(),
                    compact="compact",
                    group=group,
                    loop_index=1,
                    subcycle_index=1,
                    rounds_per_subcycle=3,
                    recent_history="recent",
                    background_context="原始议题 + compact 历史",
                    loop_dir=Path(tmp),
                    role_max_tokens=2048,
                    preview_chars=20,
                    call_role=call_role,
                )
            self.assertEqual(len(calls), 16)
            by_round: dict[int, list[int]] = {}
            for call in calls:
                context_meta = call["context_meta"] or {}
                by_round.setdefault(int(context_meta["round"]), []).append(int(call["assistant_count"]))
                self.assertTrue(context_meta["parallel_round"])
            self.assertEqual(sorted(by_round[1]), [0, 0, 0, 0])
            self.assertEqual(sorted(by_round[2]), [4, 4, 4, 4])
            self.assertEqual(sorted(by_round[3]), [8, 8, 8, 8])
            self.assertEqual(sorted(by_round[4]), [12, 12, 12, 12])
            self.assertIn("原始议题 + compact 历史", str(calls[0]["system"]))
            self.assertIn("当前 compact", str(calls[0]["system"]))
            self.assertIn("recent", str(calls[0]["system"]))
            self.assertIn("conflict_axis", str(calls[0]["system"]))
            for call in calls:
                self.assertNotIn("原始议题 + compact 历史", str(call["user_text"]))
                self.assertNotIn("本轮此前角色发言", str(call["user_text"]))
                self.assertNotIn("最近历史摘要", str(call["user_text"]))
            self.assertEqual(len(parts), 16)
            summary_prompts = [
                call for call in calls if (call["context_meta"] or {}).get("summary_round")
            ]
            self.assertEqual(len(summary_prompts), 4)
            self.assertIn("第 4 轮总结", str(summary_prompts[0]["user_text"]))
            for round_index in range(1, 5):
                round_path = Path(tmp) / "subcycle_01_a" / f"discussion_round_{round_index:02d}.jsonl"
                rows = [json.loads(line) for line in round_path.read_text(encoding="utf-8").splitlines()]
                self.assertEqual(len(rows), 4)
                self.assertIn("conversation", rows[0])
                self.assertEqual([row["slot"] for row in rows], ["A", "B", "C", "D"])
            summary_rows = [
                json.loads(line)
                for line in (Path(tmp) / "subcycle_01_a" / "discussion_round_04.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertTrue(all(row["conversation"]["summary_round"] for row in summary_rows))

    def test_role_group_resume_reuses_existing_round_records(self) -> None:
        calls: list[str] = []

        def call_role(client_key: str, call_type: str, messages: list[dict[str, str]], max_tokens: int | None, context_meta: dict[str, object] | None):
            calls.append(client_key)
            return f"{client_key} resumed", fake_result(total_tokens=5)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            group = default_discussion_plan()["groups"][0]
            subcycle = root / "subcycle_01_a"
            subcycle.mkdir()
            existing = [
                {
                    "loop": 1,
                    "subcycle": 1,
                    "group_id": "a",
                    "group_title": group["title"],
                    "round": 1,
                    "slot": "A",
                    "role_name": "测试角色A",
                    "content": "existing A",
                },
                {
                    "loop": 1,
                    "subcycle": 1,
                    "group_id": "a",
                    "group_title": group["title"],
                    "round": 1,
                    "slot": "B",
                    "role_name": "测试角色B",
                    "content": "existing B",
                },
            ]
            (subcycle / "discussion_round_01.jsonl").write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in existing) + "\n",
                encoding="utf-8",
            )

            with redirect_stdout(StringIO()):
                parts = run_discussion_group(
                    scenario=make_scenario(),
                    compact="compact",
                    group=group,
                    loop_index=1,
                    subcycle_index=1,
                    rounds_per_subcycle=1,
                    recent_history="recent",
                    background_context="background",
                    loop_dir=root,
                    role_max_tokens=2048,
                    preview_chars=20,
                    call_role=call_role,
                    resume_existing=True,
                    include_summary_round=False,
                )
            self.assertEqual(calls, ["C", "D"])
            rows = [
                json.loads(line)
                for line in (subcycle / "discussion_round_01.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual([row["slot"] for row in rows], ["A", "B", "C", "D"])
            self.assertEqual(len(collect_discussion_parts(root)), 4)


class ReportsModuleTests(unittest.TestCase):
    def test_report_messages_are_coordinator_messages(self) -> None:
        stage = stage_report_messages(make_scenario(), 1, "compact", "discussion")
        final = final_summary_messages(make_scenario(), ["report"], "timeline")
        self.assertEqual(stage[0]["role"], "system")
        self.assertIn("阶段性思想报告", stage[1]["content"])
        self.assertIn("最终总结", final[1]["content"])


class DeepSummaryModuleTests(unittest.TestCase):
    def test_collects_run_artifacts_and_role_summary_rounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "input.md").write_text("原始议题", encoding="utf-8")
            (run / "run_config.json").write_text(
                json.dumps({"scenario": {"loops": 1}}, ensure_ascii=False),
                encoding="utf-8",
            )
            loop = run / "loop_01"
            subcycle = loop / "subcycle_01_a"
            subcycle.mkdir(parents=True)
            (loop / "compact.md").write_text("compact", encoding="utf-8")
            (loop / "stage_report.md").write_text("stage", encoding="utf-8")
            (loop / "discussion_plan.md").write_text("plan", encoding="utf-8")
            rows = [
                {"slot": "A", "role_name": "学生", "group_title": "组", "content": "A总结"},
                {"slot": "B", "role_name": "教师", "group_title": "组", "content": "B总结"},
            ]
            (subcycle / "discussion_round_04.jsonl").write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
                encoding="utf-8",
            )

            artifacts = collect_summary_artifacts(run)
            paths = [artifact.path for artifact in artifacts]
            self.assertIn("loop_01/subcycle_01_a/discussion_round_04.jsonl", paths)
            rendered = next(
                artifact.content
                for artifact in artifacts
                if artifact.path == "loop_01/subcycle_01_a/discussion_round_04.jsonl"
            )
            self.assertIn("A总结", rendered)
            self.assertIn("B总结", rendered)

    def test_context_bundle_records_budget_and_messages_request_deep_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "input.md").write_text("原始议题" * 200, encoding="utf-8")
            (run / "run_config.json").write_text(
                json.dumps({"scenario": {"loops": 0}}, ensure_ascii=False),
                encoding="utf-8",
            )

            bundle = build_context_bundle(run, max_chars=500)
            self.assertLessEqual(bundle.manifest["included_chars"], 520)
            self.assertEqual(bundle.manifest["artifact_count"], 2)
            self.assertIn("Deep Final Summary Context Bundle", bundle.text)

            messages = deep_final_summary_messages(bundle.text)
            self.assertEqual(messages[0]["role"], "system")
            self.assertIn("最长上下文证据包", messages[1]["content"])
            self.assertIn("最终议案版本", messages[1]["content"])
            self.assertIn("<DISCUSSION_RESULT_MD>", messages[1]["content"])

    def test_writes_split_deep_summary_package(self) -> None:
        raw = """<DISCUSSION_RESULT_MD>
# 对这个问题讨论出来的结果

结果正文
</DISCUSSION_RESULT_MD>
<PROCESS_ANALYSIS_MD>
# 对整个讨论流程的客观分析

流程正文
</PROCESS_ANALYSIS_MD>
<SYNTHESIZED_DOCUMENT_MD>
# 原文的文档合成稿

合成正文
</SYNTHESIZED_DOCUMENT_MD>
"""
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            sections = split_deep_summary_package(raw)
            self.assertEqual(set(sections), {"discussion_result", "process_analysis", "synthesized_document"})
            manifest = write_deep_summary_package(run, raw)
            package = run / "deep_summary" / "final_package"
            self.assertTrue((package / "index.md").exists())
            self.assertTrue((package / "01_discussion_result.md").exists())
            self.assertTrue((package / "02_process_analysis.md").exists())
            self.assertTrue((package / "03_synthesized_document.md").exists())
            self.assertTrue(manifest["complete_sections"])
            self.assertIn("结果正文", (package / "01_discussion_result.md").read_text(encoding="utf-8"))


class RuntimeIOModuleTests(unittest.TestCase):
    def test_runtime_helpers_write_and_parse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_text(root / "a" / "x.md", "hello")
            write_json(root / "b" / "x.json", {"k": "v"})
            self.assertEqual((root / "a" / "x.md").read_text(encoding="utf-8"), "hello\n")
            self.assertEqual(json.loads((root / "b" / "x.json").read_text(encoding="utf-8")), {"k": "v"})
        self.assertEqual(parse_json_object('```json\n{"x": 1}\n```'), {"x": 1})
        self.assertEqual(safe_slug(" a/b? "), "a-b")
        self.assertEqual(result_summary(fake_result(total_tokens=15))["total_tokens"], 15)


class MonitorModuleTests(unittest.TestCase):
    def test_null_monitor_writes_nothing_and_run_monitor_writes_status(self) -> None:
        NullMonitor().update("running", "noop")
        with tempfile.TemporaryDirectory() as tmp:
            monitor = RunMonitor(Path(tmp), scenario_title="测试", total_loops=2)
            monitor.record_call(
                "compact",
                {
                    "prompt_tokens": 7,
                    "completion_tokens": 5,
                    "reasoning_tokens": 2,
                    "visible_answer_tokens_estimate": 3,
                    "total_tokens": 12,
                },
            )
            status = json.loads((Path(tmp) / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["call_count"], 1)
            self.assertEqual(status["by_type"]["compact"], 1)
            self.assertEqual(status["prompt_tokens"], 7)
            self.assertEqual(status["completion_tokens"], 5)
            self.assertEqual(status["reasoning_tokens"], 2)
            self.assertEqual(status["visible_answer_tokens_estimate"], 3)
            self.assertTrue((Path(tmp) / "monitor.html").exists())
            html = (Path(tmp) / "monitor.html").read_text(encoding="utf-8")
            self.assertIn("估算费用", html)
            self.assertIn("Token 用量拆分", html)
            self.assertIn("data-theme", html)
            self.assertIn("themeToggle", html)
            self.assertIn("status.json HTTP", html)
            self.assertIn("测试流程总览", html)
            self.assertIn("DEFAULT_BATCH_CASES", html)
            self.assertIn("20_online_social_relationships", html)


if __name__ == "__main__":
    unittest.main()
