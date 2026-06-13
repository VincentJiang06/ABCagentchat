#!/usr/bin/env python3
"""Incrementally publish completed DiffusionGemma scenarios to GitHub.

Run repeatedly (e.g. from a 10-minute monitor loop). For every batch scenario
that has finished (status done / completed_with_warnings) and is not yet in
examples/, copy the curated readable package (framework + final summary +
flattened stage reports + metrics; NOT raw transcripts), commit, and push.
Idempotent — already-published scenarios are skipped.

  python3 sync_examples.py            # incremental: publish any newly-finished scenarios
  python3 sync_examples.py --finalize # overwrite old example batch + write README/table
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BATCH_ID = "batch-local-dg-all20"
BATCH_ROOT = ROOT / "runs" / "local-diffusiongemma-all20"
EXAMPLES = ROOT / "examples" / BATCH_ID
SCENARIOS = ROOT / "scenarios"
OLD_BATCH = ROOT / "examples" / "batch-20260503-004056-full-20"
READY = {"done", "completed_with_warnings"}
COAUTHOR = "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"


def sh(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True)


def git_push(message: str) -> bool:
    cm = sh(["git", "commit", "-m", message])
    if cm.returncode != 0:
        if "nothing to commit" in (cm.stdout + cm.stderr):
            return True
        print(f"  commit failed: {(cm.stdout + cm.stderr)[-300:]}")
        return False
    ps = sh(["git", "push"])
    if ps.returncode != 0:
        print(f"  push failed: {ps.stderr[-300:]}")
        return False
    return True


def package(run_dir: Path, slug: str, dest: Path) -> bool:
    """Copy the curated readable package for one scenario into dest."""
    final_src = run_dir / "final summary"
    if not (final_src / "final_summary.md").exists():
        return False  # scenario not actually complete
    if dest.exists():
        shutil.rmtree(dest)
    # framework + the source scenario
    if (run_dir / "framework").exists():
        shutil.copytree(run_dir / "framework", dest / "framework")
    (dest / "framework").mkdir(parents=True, exist_ok=True)
    if (SCENARIOS / f"{slug}.md").exists():
        shutil.copy2(SCENARIOS / f"{slug}.md", dest / "framework" / "scenario.md")
    # final summary -> final_summary
    shutil.copytree(final_src, dest / "final_summary")
    # process: flatten per-loop stage reports + keep metrics/audit (skip raw transcripts)
    pdest = dest / "process"
    pdest.mkdir(parents=True, exist_ok=True)
    proc = run_dir / "process"
    for loop_dir in sorted(proc.glob("loop_*")):
        sr = loop_dir / "stage_report.md"
        if sr.exists():
            shutil.copy2(sr, pdest / f"{loop_dir.name}_stage_report.md")
    for name in ("metrics.json", "audit.log"):
        if (proc / name).exists():
            shutil.copy2(proc / name, pdest / name)
    if (run_dir / "status.json").exists():
        shutil.copy2(run_dir / "status.json", dest / "status.json")
    return True


def load_cases() -> tuple[list[dict], str]:
    status_file = BATCH_ROOT / "batch_status.json"
    if not status_file.exists():
        return [], "missing"
    data = json.loads(status_file.read_text(encoding="utf-8"))
    cases = sorted(data.get("cases", []), key=lambda c: c.get("index", 999))
    return cases, data.get("status", "?")


def incremental() -> int:
    cases, batch_status = load_cases()
    if not cases:
        print("SUMMARY: no batch_status.json yet")
        return 0
    pushed = []
    for c in cases:
        slug, status = c.get("slug"), c.get("status")
        dest = EXAMPLES / slug
        if status in READY and not (dest / "final_summary" / "final_summary.md").exists():
            run_dir = Path(c["run_dir"])
            if package(run_dir, slug, dest):
                sh(["git", "add", "-f", str(dest.relative_to(ROOT))])
                title = c.get("title", slug)
                msg = f"议题 {int(c.get('index', 0)):02d} {title}：DiffusionGemma 本地讨论结果\n\n{COAUTHOR}"
                if git_push(msg):
                    pushed.append(slug)
                    print(f"PUSHED {slug}")
    done = sum(1 for c in cases if c.get("status") in READY)
    failed = [c.get("slug") for c in cases if c.get("status") in {"failed", "error"}]
    print(f"SUMMARY done={done}/{len(cases)} pushed_this_run={len(pushed)} "
          f"failed={failed} batch_status={batch_status} running={[c.get('slug') for c in cases if c.get('status') in {'running','starting'}]}")
    return 0


def finalize() -> int:
    cases, _ = load_cases()
    published = [c for c in cases if (EXAMPLES / c.get("slug") / "final_summary" / "final_summary.md").exists()]
    # remove the old DeepSeek example batch (overwrite)
    if OLD_BATCH.exists():
        shutil.rmtree(OLD_BATCH)
    # batch_summary.json
    total_calls = total_tokens = 0
    for c in published:
        m = Path(c["run_dir"]) / "process" / "metrics.json"
        if m.exists():
            t = (json.loads(m.read_text(encoding="utf-8")).get("transcript") or {})
            total_calls += int(t.get("call_count") or 0)
            total_tokens += int(t.get("total_tokens") or 0)
    summary = {
        "batch": BATCH_ID,
        "model": "diffusiongemma-26B-A4B-it-Q4_K_M (local, llama-diffusion-cli)",
        "backend": "local-diffusiongemma (serial roles, single-thread, dynamic ubatch)",
        "settings": "3 loops × 2 subcycles × 4 rounds",
        "completed": len(published),
        "total_cases": len(cases),
        "total_calls": total_calls,
        "total_tokens_estimate": total_tokens,
    }
    (EXAMPLES).mkdir(parents=True, exist_ok=True)
    (EXAMPLES / "batch_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # README table
    rows = []
    for c in sorted(published, key=lambda c: c.get("index", 999)):
        slug = c.get("slug")
        rows.append(f"| {int(c.get('index',0)):02d} | {c.get('title', slug)} | "
                    f"[final_summary]({BATCH_ID}/{slug}/final_summary/final_summary.md) | "
                    f"[完整包]({BATCH_ID}/{slug}/final_summary/00_full_final_summary.md) |")
    readme = EXAMPLES / "README.md"
    readme.write_text(
        "# DiffusionGemma 本地批次：" + BATCH_ID + "\n\n"
        "本批次由 **本地 DiffusionGemma 26B-A4B（Q4_K_M）** 通过 `llama-diffusion-cli` 串行生成"
        "（单进程、角色逐个发言、动态 ubatch 低内存模式）。设置：3 loops × 2 subcycles × 4 rounds。\n\n"
        f"完成 {len(published)}/{len(cases)} 个议题。每个议题先读 `<slug>/final_summary/final_summary.md`。\n\n"
        "| # | 议题 | Final summary | 完整包 |\n|---:|---|---|---|\n" + "\n".join(rows) + "\n",
        encoding="utf-8")
    sh(["git", "add", "-A", "examples"])
    msg = f"DiffusionGemma 本地批次完成（{len(published)}/{len(cases)}）：覆盖旧 examples + 汇总\n\n{COAUTHOR}"
    ok = git_push(msg)
    print(f"FINALIZE published={len(published)}/{len(cases)} pushed={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(finalize() if "--finalize" in sys.argv[1:] else incremental())
