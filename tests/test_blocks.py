from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

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


class UtilityTests(unittest.TestCase):
    def test_parse_json_object_accepts_fenced_json(self) -> None:
        parsed = parse_json_object('```json\n{"roles": []}\n```')
        self.assertEqual(parsed, {"roles": []})

    def test_safe_slug_and_trim_text(self) -> None:
        self.assertEqual(safe_slug("  A / B?  "), "A-B")
        self.assertEqual(trim_text("abcdef", 3), "def")

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

            metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
            self.assertTrue(metrics["passed"], metrics)
            self.assertEqual(metrics["transcript"]["call_count"], 16)
            for round_index in range(1, 4):
                round_path = out / "loop_01" / f"discussion_round_{round_index:02d}.jsonl"
                self.assertEqual(len(round_path.read_text(encoding="utf-8").splitlines()), 4)

    def test_dry_run_two_loops_expected_call_formula(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenario_path = root / "scenario.md"
            scenario_path.write_text("---\ntitle: 两轮议案\nloops: 2\n---\n# 情景设定\n测试。", encoding="utf-8")
            scenario = load_scenario(scenario_path)
            out = root / "runs" / "two-loops"
            simulator = Simulator(root=root, config=None, options=RunOptions(output_dir=out, dry_run=True))
            with redirect_stdout(StringIO()):
                simulator.run(scenario)

            metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
            self.assertTrue(metrics["passed"], metrics)
            self.assertEqual(metrics["expected_calls"], 31)
            self.assertEqual(metrics["transcript"]["call_count"], 31)

    def test_audit_detects_missing_round_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "loop_01").mkdir()
            (run / "input.md").write_text("input", encoding="utf-8")
            (run / "final_summary.md").write_text("final", encoding="utf-8")
            (run / "run_config.json").write_text(json.dumps({"scenario": {"loops": 1}}), encoding="utf-8")
            for name in [
                "compact.md",
                "personas.raw.json",
                "personas.json",
                "personas.md",
                "stage_report.md",
            ]:
                (run / "loop_01" / name).write_text("x", encoding="utf-8")
            for round_index in range(1, 4):
                rows = 4 if round_index != 2 else 3
                (run / "loop_01" / f"discussion_round_{round_index:02d}.jsonl").write_text(
                    "\n".join("{}" for _ in range(rows)) + "\n",
                    encoding="utf-8",
                )
            (run / "transcript.jsonl").write_text("\n".join(json.dumps({"usage": {}, "content_preview": "x"}) for _ in range(16)) + "\n", encoding="utf-8")

            metrics = audit_run_dir(run)
            self.assertFalse(metrics["passed"])
            self.assertIn("loop_01/discussion_round_02.jsonl", metrics["failed_rounds"])


if __name__ == "__main__":
    unittest.main()
