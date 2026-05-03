from __future__ import annotations

from pathlib import Path


PROCESS_DIR = "process"
COMPACT_PLANNING_DIR = "compact and planning"
FINAL_SUMMARY_DIR = "final summary"
FRAMEWORK_DIR = "framework"


def process_root(run_dir: Path) -> Path:
    return run_dir / PROCESS_DIR


def compact_planning_root(run_dir: Path) -> Path:
    return run_dir / COMPACT_PLANNING_DIR


def final_summary_root(run_dir: Path) -> Path:
    return run_dir / FINAL_SUMMARY_DIR


def framework_root(run_dir: Path) -> Path:
    return run_dir / FRAMEWORK_DIR


def process_loop_dir(run_dir: Path, loop_index: int) -> Path:
    return process_root(run_dir) / f"loop_{loop_index:02d}"


def compact_planning_loop_dir(run_dir: Path, loop_index: int) -> Path:
    return compact_planning_root(run_dir) / f"loop_{loop_index:02d}"
