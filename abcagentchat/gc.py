from __future__ import annotations

import shutil
from pathlib import Path


def prune_old_runs(runs_dir: Path, keep_runs: int) -> list[Path]:
    if keep_runs <= 0 or not runs_dir.exists():
        return []
    candidates = [path for path in runs_dir.iterdir() if path.is_dir()]
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    removed: list[Path] = []
    for path in candidates[keep_runs:]:
        # Only remove directories below the explicit runs root.
        if path.parent.resolve() != runs_dir.resolve():
            continue
        shutil.rmtree(path)
        removed.append(path)
    return removed


def trim_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]

