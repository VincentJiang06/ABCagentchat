from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from abcagentchat.api import ChatResult, DeepSeekClient, ModelSettings
from abcagentchat.background import compact_archive_context, previous_reports_context, recent_context
from abcagentchat.compact import compact_messages
from abcagentchat.conversation import Conversation
from abcagentchat.monitor import NullMonitor, RunMonitor
from abcagentchat.planning import default_discussion_plan, load_discussion_plan, render_discussion_plan
from abcagentchat.reports import final_summary_messages, stage_report_messages
from abcagentchat.roles import run_discussion_group
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
    def test_payload_records_enabled_and_disabled_thinking(self) -> None:
        coordinator = DeepSeekClient(
            "key",
            ModelSettings("deepseek-v4-pro", "https://api.deepseek.com", 8192, thinking_enabled=True, reasoning_effort="max"),
        )
        role = DeepSeekClient(
            "key",
            ModelSettings("deepseek-v4-pro", "https://api.deepseek.com", 4096, thinking_enabled=False, reasoning_effort=None),
        )
        self.assertEqual(coordinator.build_payload([{"role": "user", "content": "x"}])["reasoning_effort"], "max")
        role_payload = role.build_payload([{"role": "user", "content": "x"}])
        self.assertEqual(role_payload["thinking"], {"type": "disabled"})
        self.assertNotIn("reasoning_effort", role_payload)


class BackgroundModuleTests(unittest.TestCase):
    def test_compact_archive_includes_original_issue_and_history(self) -> None:
        context = compact_archive_context(make_scenario(), ["compact-1", "compact-2"])
        self.assertIn("# 原始议题全文", context)
        self.assertIn("需要讨论是否试点", context)
        self.assertIn("第 1 个循环 compact", context)
        self.assertIn("compact-2", context)

    def test_recent_and_previous_reports_context(self) -> None:
        self.assertEqual(recent_context("abcdef", 3), "def")
        self.assertIn("r2", previous_reports_context(["r1", "r2"], keep=1))
        self.assertNotIn("r1", previous_reports_context(["r1", "r2"], keep=1))


class CompactPromptModuleTests(unittest.TestCase):
    def test_compact_messages_inject_history_archive(self) -> None:
        messages = compact_messages(make_scenario(), 2, ["compact-1"], ["report-1"], "recent-role-talk")
        self.assertEqual(messages[0]["role"], "system")
        user = messages[1]["content"]
        self.assertIn("原始议题与历史 compact 档案", user)
        self.assertIn("compact-1", user)
        self.assertIn("recent-role-talk", user)


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
            self.assertEqual(len(calls), 12)
            self.assertEqual([call["assistant_count"] for call in calls], list(range(12)))
            self.assertEqual(len(parts), 12)
            for round_index in range(1, 4):
                round_path = Path(tmp) / "subcycle_01_a" / f"discussion_round_{round_index:02d}.jsonl"
                rows = [json.loads(line) for line in round_path.read_text(encoding="utf-8").splitlines()]
                self.assertEqual(len(rows), 4)
                self.assertIn("conversation", rows[0])


class ReportsModuleTests(unittest.TestCase):
    def test_report_messages_are_coordinator_messages(self) -> None:
        stage = stage_report_messages(make_scenario(), 1, "compact", "discussion")
        final = final_summary_messages(make_scenario(), ["report"], "timeline")
        self.assertEqual(stage[0]["role"], "system")
        self.assertIn("阶段性报告", stage[1]["content"])
        self.assertIn("最终总结", final[1]["content"])


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
            monitor.record_call("compact", 12)
            status = json.loads((Path(tmp) / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["call_count"], 1)
            self.assertEqual(status["by_type"]["compact"], 1)
            self.assertTrue((Path(tmp) / "monitor.html").exists())


if __name__ == "__main__":
    unittest.main()
