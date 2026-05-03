from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from abcagentchat.api import DeepSeekClient, ModelSettings, normalize_reasoning_effort
from abcagentchat.batch_control import request_stop, read_json as read_batch_json, status_path, stop_from_status, write_json as write_batch_json
from abcagentchat.conversation import Conversation
from abcagentchat.gc import prune_old_runs, trim_text
from abcagentchat.metrics import audit_run_dir
from abcagentchat.scenario import load_scenario, parse_frontmatter
from abcagentchat.simulator import RunOptions, Simulator, parse_json_object, safe_slug


class ScenarioParsingTests(unittest.TestCase):
    def test_frontmatter_parses_nested_source_refs(self) -> None:
        text = """---
title: 测试议案
loops: 2
domain: community
source_refs:
  - title: Source A
    url: https://example.com/a
primary_tests:
  - fact_retention
---

# Body
"""
        meta, body = parse_frontmatter(text)
        self.assertEqual(meta["title"], "测试议案")
        self.assertEqual(meta["loops"], 2)
        self.assertEqual(meta["source_refs"][0]["title"], "Source A")
        self.assertEqual(meta["source_refs"][0]["url"], "https://example.com/a")
        self.assertEqual(meta["primary_tests"], ["fact_retention"])
        self.assertIn("# Body", body)

    def test_load_scenario_loop_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scenario.md"
            path.write_text("---\ntitle: A\nloops: 2\n---\nbody", encoding="utf-8")
            scenario = load_scenario(path, loops_override=5)
            self.assertEqual(scenario.title, "A")
            self.assertEqual(scenario.loops, 5)

    def test_repository_scenario_dataset_has_twenty_cases(self) -> None:
        scenario_dir = Path(__file__).resolve().parents[1] / "scenarios"
        paths = sorted(scenario_dir.glob("*.md"))
        self.assertEqual(len(paths), 20)
        scenarios = [load_scenario(path) for path in paths]
        self.assertTrue(all(scenario.loops == 3 for scenario in scenarios))
        self.assertEqual(len({scenario.title for scenario in scenarios}), 20)


class UtilityTests(unittest.TestCase):
    def test_parse_json_object_accepts_fenced_json(self) -> None:
        parsed = parse_json_object('```json\n{"roles": []}\n```')
        self.assertEqual(parsed, {"roles": []})

    def test_safe_slug_and_trim_text(self) -> None:
        self.assertEqual(safe_slug("  A / B?  "), "A-B")
        self.assertEqual(trim_text("abcdef", 3), "def")

    def test_reasoning_effort_aliases(self) -> None:
        self.assertEqual(normalize_reasoning_effort("long"), "high")
        self.assertEqual(normalize_reasoning_effort("extra long"), "max")

    def test_deepseek_payload_thinking_modes(self) -> None:
        coordinator = DeepSeekClient(
            "key",
            ModelSettings(
                model="deepseek-v4-pro",
                base_url="https://api.deepseek.com",
                max_tokens=8192,
                thinking_enabled=True,
                reasoning_effort="max",
            ),
        )
        role = DeepSeekClient(
            "key",
            ModelSettings(
                model="deepseek-v4-pro",
                base_url="https://api.deepseek.com",
                max_tokens=6144,
                thinking_enabled=False,
                reasoning_effort=None,
                temperature=0.8,
            ),
        )
        coordinator_payload = coordinator.build_payload([{"role": "user", "content": "x"}])
        coordinator_override_payload = coordinator.build_payload(
            [{"role": "user", "content": "x"}],
            reasoning_effort="high",
        )
        role_payload = role.build_payload([{"role": "user", "content": "x"}])
        self.assertEqual(role_payload["model"], "deepseek-v4-pro")
        self.assertEqual(coordinator_payload["thinking"], {"type": "enabled"})
        self.assertEqual(coordinator_payload["reasoning_effort"], "max")
        self.assertEqual(coordinator_override_payload["reasoning_effort"], "high")
        self.assertEqual(role_payload["thinking"], {"type": "disabled"})
        self.assertNotIn("reasoning_effort", role_payload)
        self.assertEqual(role_payload["max_tokens"], 6144)
        self.assertEqual(role_payload["temperature"], 0.8)
        role_meta = role.request_meta(max_tokens=6144, temperature=0.8)
        self.assertEqual(role_meta["thinking"], {"type": "disabled"})
        self.assertNotIn("reasoning_effort", role_meta)

    def test_conversation_appends_assistant_outputs_for_later_rounds(self) -> None:
        conversation = Conversation("system")
        first = conversation.messages_for("user-1")
        conversation.append_exchange("user-1", "assistant-1")
        second = conversation.messages_for("user-2")
        conversation.append_exchange("user-2", "assistant-2")
        third = conversation.messages_for("user-3")
        self.assertEqual([message["role"] for message in first], ["system", "user"])
        self.assertIn({"role": "assistant", "content": "assistant-1"}, second)
        self.assertIn({"role": "assistant", "content": "assistant-1"}, third)
        self.assertIn({"role": "assistant", "content": "assistant-2"}, third)

    def test_prune_old_runs_keeps_newest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "old"
            new = root / "new"
            old.mkdir()
            new.mkdir()
            os.utime(old, (1, 1))
            os.utime(new, (2, 2))
            removed = prune_old_runs(root, keep_runs=1)
            self.assertEqual(len(removed), 1)
            self.assertEqual(removed[0].name, "old")
            self.assertEqual(len([path for path in root.iterdir() if path.is_dir()]), 1)


class DryRunIntegrationTests(unittest.TestCase):
    def test_dry_run_writes_expected_artifacts_and_metrics_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenario_dir = root / "scenarios"
            scenario_dir.mkdir()
            scenario_path = scenario_dir / "scenario.md"
            scenario_path.write_text(
                """---
title: 分块测试议案
loops: 1
domain: test
source_refs: []
primary_tests:
  - fact_retention
---

# 情景设定
测试。
""",
                encoding="utf-8",
            )
            scenario = load_scenario(scenario_path)
            out = root / "runs" / "block"
            simulator = Simulator(root=root, config=None, options=RunOptions(output_dir=out, dry_run=True))
            with redirect_stdout(StringIO()):
                simulator.run(scenario)

            metrics = json.loads((out / "process" / "metrics.json").read_text(encoding="utf-8"))
            self.assertTrue(metrics["passed"], metrics)
            self.assertEqual(metrics["transcript"]["call_count"], 16)
            for final_file in [
                "framework/input.md",
                "framework/run_config.json",
                "framework/run_index.md",
                "final summary/README.md",
                "final summary/manifest.json",
                "final summary/00_full_final_summary.md",
                "final summary/01_discussion_result.md",
                "final summary/02_process_analysis.md",
                "final summary/03_synthesized_document.md",
                "final summary/04_evidence_and_next_steps.md",
                "final summary/final_summary.md",
                "final summary/process_timeline.md",
                "final summary/output_tree.md",
            ]:
                self.assertTrue((out / final_file).exists(), final_file)
            rows = [
                json.loads(line)
                for line in (out / "process" / "transcript.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            first_by_type = {}
            for row in rows:
                first_by_type.setdefault(row["call_type"], row["request"])
            self.assertEqual(first_by_type["compact"]["temperature"], 0.0)
            self.assertEqual(first_by_type["planning"]["temperature"], 0.2)
            self.assertEqual(first_by_type["role_A"]["temperature"], 0.8)
            self.assertEqual(first_by_type["role_A"]["max_tokens"], 6144)
            self.assertEqual(first_by_type["role_A"]["thinking"], {"type": "disabled"})
            self.assertNotIn("reasoning_effort", first_by_type["role_A"])
            self.assertEqual(first_by_type["stage_report"]["temperature"], 0.0)
            self.assertEqual(first_by_type["stage_report"]["max_tokens"], 65536)
            self.assertEqual(first_by_type["final_summary"]["temperature"], 0.5)
            self.assertEqual(first_by_type["final_summary"]["max_tokens"], 65536)
            for round_index in range(1, 4):
                round_path = out / "process" / "loop_01" / "subcycle_01_a" / f"discussion_round_{round_index:02d}.jsonl"
                self.assertEqual(len(round_path.read_text(encoding="utf-8").splitlines()), 4)
            self.assertFalse((out / "process" / "loop_01" / "subcycle_01_a" / "discussion_round_04.jsonl").exists())

    def test_dry_run_two_loops_expected_call_formula(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenario_path = root / "scenario.md"
            scenario_path.write_text("---\ntitle: 两轮议案\nloops: 2\n---\n# 情景设定\n测试。", encoding="utf-8")
            scenario = load_scenario(scenario_path)
            out = root / "runs" / "two-loops"
            simulator = Simulator(root=root, config=None, options=RunOptions(output_dir=out, dry_run=True, max_loops=6))
            with redirect_stdout(StringIO()):
                simulator.run(scenario)

            metrics = json.loads((out / "process" / "metrics.json").read_text(encoding="utf-8"))
            self.assertTrue(metrics["passed"], metrics)
            self.assertEqual(metrics["expected_calls"], 31)
            self.assertEqual(metrics["transcript"]["call_count"], 31)
            loop2_background = (out / "compact and planning" / "loop_02" / "background_context.md").read_text(encoding="utf-8")
            self.assertIn("第 1 个循环 compact", loop2_background)
            self.assertIn("# 原始议题全文", loop2_background)

    def test_dry_run_rolls_older_compacts_into_max_effort_summary_and_gradient_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenario_path = root / "scenario.md"
            scenario_path.write_text("---\ntitle: 六轮议案\nloops: 6\n---\n# 情景设定\n测试。", encoding="utf-8")
            scenario = load_scenario(scenario_path)
            out = root / "runs" / "six-loops"
            simulator = Simulator(root=root, config=None, options=RunOptions(output_dir=out, dry_run=True, max_loops=6))
            with redirect_stdout(StringIO()):
                simulator.run(scenario)

            metrics = json.loads((out / "process" / "metrics.json").read_text(encoding="utf-8"))
            self.assertTrue(metrics["passed"], metrics)
            self.assertEqual(metrics["expected_calls"], 92)
            self.assertEqual(metrics["transcript"]["by_type"]["compact_archive_summary"], 1)

            loop6_background = (out / "compact and planning" / "loop_06" / "background_context.md").read_text(encoding="utf-8")
            self.assertIn("第 1-1 个循环 compact 滚动开放讨论账本摘要", loop6_background)
            self.assertIn("更早 Compact 滚动开放讨论账本", loop6_background)
            self.assertIn("第 1 个循环 compact（梯度摘录", loop6_background)
            self.assertIn("## 第 2 个循环 compact（全文）\n# Compact 开放讨论状态账本", loop6_background)
            self.assertIn("## 第 5 个循环 compact（全文）\n# Compact 开放讨论状态账本", loop6_background)
            self.assertTrue((out / "compact and planning" / "compact_archive_summary.md").exists())

            rows = [
                json.loads(line)
                for line in (out / "process" / "transcript.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            archive_rows = [row for row in rows if row["call_type"] == "compact_archive_summary"]
            self.assertEqual(archive_rows[0]["request"]["thinking"], {"type": "enabled"})
            self.assertEqual(archive_rows[0]["request"]["reasoning_effort"], "max")

    def test_parallel_batch_dry_run_records_process_groups(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenarios = root / "scenarios"
            scenarios.mkdir()
            for index in range(1, 5):
                (scenarios / f"{index:02d}_case.md").write_text(
                    f"---\ntitle: 并发样例 {index}\nloops: 1\n---\n# 情景设定\n测试 {index}。",
                    encoding="utf-8",
                )
            out = root / "batch"
            cmd = [
                sys.executable,
                str(repo / "run_all_scenarios.py"),
                "--scenarios-dir",
                str(scenarios),
                "--out",
                str(out),
                "--batch-id",
                "test-batch",
                "--dry-run",
                "--parallel",
                "3",
                "--loops",
                "1",
                "--poll-seconds",
                "0.01",
            ]
            result = subprocess.run(cmd, cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout)
            status = json.loads((out / "batch_status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["status"], "done")
            self.assertEqual(status["parallelism"], 3)
            self.assertEqual(status["running_cases"], [])
            self.assertEqual(len(status["cases"]), 4)
            self.assertTrue(all(case["status"] == "done" for case in status["cases"]))
            self.assertTrue(all(case.get("pid") and case.get("pgid") for case in status["cases"]))
            first_run = Path(status["cases"][0]["run_dir"])
            self.assertTrue((first_run / "process" / "run.log").exists())
            self.assertTrue((first_run / "process" / "metrics.json").exists())
            self.assertFalse((first_run / "process" / "loop_01" / "subcycle_01_a" / "discussion_round_04.jsonl").exists())

    def test_stop_helper_marks_running_and_pending_cases_stopped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch_root = Path(tmp)
            write_batch_json(
                status_path(batch_root),
                {
                    "status": "running",
                    "cases": [
                        {"slug": "active", "status": "running", "pgid": -1},
                        {"slug": "queued", "status": "pending"},
                        {"slug": "done", "status": "done"},
                    ],
                },
            )
            request_stop(batch_root, reason="unit test", stop_monitor=True)
            result = stop_from_status(batch_root, timeout=0.01)
            self.assertEqual(result["status"], "stopped")
            status = read_batch_json(status_path(batch_root))
            by_slug = {case["slug"]: case["status"] for case in status["cases"]}
            self.assertEqual(by_slug["active"], "stopped")
            self.assertEqual(by_slug["queued"], "stopped")
            self.assertEqual(by_slug["done"], "done")

    def test_loop_cap_defaults_to_3(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenario_path = root / "scenario.md"
            scenario_path.write_text("---\ntitle: 三轮上限\nloops: 150\n---\n# 情景设定\n测试。", encoding="utf-8")
            scenario = load_scenario(scenario_path)
            out = root / "runs" / "cap"
            simulator = Simulator(root=root, config=None, options=RunOptions(output_dir=out, dry_run=True))
            with redirect_stdout(StringIO()):
                simulator.run(scenario)
            run_config = json.loads((out / "framework" / "run_config.json").read_text(encoding="utf-8"))
            self.assertEqual(run_config["scenario"]["requested_loops"], 150)
            self.assertEqual(run_config["scenario"]["loops"], 3)

    def test_audit_detects_missing_round_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "process" / "loop_01").mkdir(parents=True)
            (run / "compact and planning" / "loop_01").mkdir(parents=True)
            (run / "framework").mkdir()
            (run / "final summary").mkdir()
            (run / "framework" / "input.md").write_text("input", encoding="utf-8")
            (run / "framework" / "run_index.md").write_text("index", encoding="utf-8")
            (run / "framework" / "run_config.json").write_text(
                json.dumps({"scenario": {"loops": 1}, "options": {"rounds_per_subcycle": 3, "role_summary_round": True}}),
                encoding="utf-8",
            )
            for name in [
                "background_context.md",
                "compact.md",
                "discussion_plan.raw.json",
                "discussion_plan.json",
                "discussion_plan.md",
            ]:
                (run / "compact and planning" / "loop_01" / name).write_text("x", encoding="utf-8")
            (run / "process" / "loop_01" / "stage_report.md").write_text("x", encoding="utf-8")
            for name in [
                "README.md",
                "manifest.json",
                "00_full_final_summary.md",
                "01_discussion_result.md",
                "02_process_analysis.md",
                "03_synthesized_document.md",
                "04_evidence_and_next_steps.md",
                "final_summary.md",
                "process_timeline.md",
                "output_tree.md",
            ]:
                (run / "final summary" / name).write_text("{}" if name.endswith(".json") else "x", encoding="utf-8")
            (run / "compact and planning" / "loop_01" / "discussion_plan.json").write_text(
                json.dumps({"groups": [{"group_id": "a"}]}),
                encoding="utf-8",
            )
            subcycle = run / "process" / "loop_01" / "subcycle_01_a"
            subcycle.mkdir()
            (subcycle / "discussion_round_01.jsonl").write_text(
                "\n".join("{}" for _ in range(3)) + "\n",
                encoding="utf-8",
            )
            for round_index in [2, 3, 4]:
                (subcycle / f"discussion_round_{round_index:02d}.jsonl").write_text(
                    "\n".join("{}" for _ in range(4)) + "\n",
                    encoding="utf-8",
                )
            (run / "process" / "transcript.jsonl").write_text("\n".join(json.dumps({"usage": {}, "content_preview": "x"}) for _ in range(20)) + "\n", encoding="utf-8")

            metrics = audit_run_dir(run)
            self.assertFalse(metrics["passed"])
            self.assertIn("process/loop_01/subcycle_01_a/discussion_round_01.jsonl", metrics["failed_rounds"])

    def test_audit_treats_length_and_preview_issues_as_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "process" / "loop_01").mkdir(parents=True)
            (run / "compact and planning" / "loop_01").mkdir(parents=True)
            (run / "framework").mkdir()
            (run / "final summary").mkdir()
            (run / "framework" / "input.md").write_text("input", encoding="utf-8")
            (run / "framework" / "run_index.md").write_text("index", encoding="utf-8")
            (run / "framework" / "run_config.json").write_text(
                json.dumps({"scenario": {"loops": 1}, "options": {"rounds_per_subcycle": 3, "role_summary_round": False}}),
                encoding="utf-8",
            )
            for name in [
                "background_context.md",
                "compact.md",
                "discussion_plan.raw.json",
                "discussion_plan.json",
                "discussion_plan.md",
            ]:
                (run / "compact and planning" / "loop_01" / name).write_text("x", encoding="utf-8")
            (run / "compact and planning" / "loop_01" / "discussion_plan.json").write_text(
                json.dumps({"groups": []}),
                encoding="utf-8",
            )
            (run / "process" / "loop_01" / "stage_report.md").write_text("x", encoding="utf-8")
            for name in [
                "README.md",
                "manifest.json",
                "00_full_final_summary.md",
                "01_discussion_result.md",
                "02_process_analysis.md",
                "03_synthesized_document.md",
                "04_evidence_and_next_steps.md",
                "final_summary.md",
                "process_timeline.md",
                "output_tree.md",
            ]:
                (run / "final summary" / name).write_text("{}" if name.endswith(".json") else "x", encoding="utf-8")
            rows = [
                {"call_type": "compact", "client_key": "coordinator", "usage": {}, "content_preview": "x"},
                {"call_type": "planning", "client_key": "coordinator", "usage": {}, "content_preview": "x"},
                {"call_type": "stage_report", "client_key": "coordinator", "usage": {"finish_reason": "length"}, "content_preview": ""},
                {"call_type": "final_summary", "client_key": "coordinator", "usage": {}, "content_preview": "x"},
            ]
            (run / "process" / "transcript.jsonl").write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )

            metrics = audit_run_dir(run)
            self.assertTrue(metrics["passed"], metrics)
            self.assertFalse(metrics["strict_passed"])
            self.assertEqual(metrics["warning_count"], 2)
            self.assertEqual(metrics["warnings"], ["has_no_length_stops", "has_no_empty_previews"])


if __name__ == "__main__":
    unittest.main()
