from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .prompts import COORDINATOR_SYSTEM
from .runtime_io import result_summary, write_json, write_text


DEFAULT_DEEP_CONTEXT_CHARS = 900_000
DEFAULT_DEEP_SUMMARY_MAX_TOKENS = 65_536
DEFAULT_PACKAGE_DIR = "deep_summary/final_package"


PACKAGE_SECTIONS = {
    "discussion_result": {
        "title": "对这个问题讨论出来的结果",
        "filename": "01_discussion_result.md",
        "start": "<DISCUSSION_RESULT_MD>",
        "end": "</DISCUSSION_RESULT_MD>",
    },
    "process_analysis": {
        "title": "对整个讨论流程的客观分析",
        "filename": "02_process_analysis.md",
        "start": "<PROCESS_ANALYSIS_MD>",
        "end": "</PROCESS_ANALYSIS_MD>",
    },
    "synthesized_document": {
        "title": "原文的文档合成稿",
        "filename": "03_synthesized_document.md",
        "start": "<SYNTHESIZED_DOCUMENT_MD>",
        "end": "</SYNTHESIZED_DOCUMENT_MD>",
    },
}


@dataclass(frozen=True)
class SummaryArtifact:
    label: str
    path: str
    kind: str
    priority: int
    content: str

    @property
    def chars(self) -> int:
        return len(self.content)


@dataclass(frozen=True)
class PackedArtifact:
    label: str
    path: str
    kind: str
    priority: int
    original_chars: int
    included_chars: int
    mode: str


@dataclass(frozen=True)
class ContextBundle:
    text: str
    manifest: dict[str, Any]


def estimate_tokens_from_chars(chars: int) -> int:
    return max(1, chars // 2)


def _read_if_exists(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _artifact_from_path(run_dir: Path, path: Path, *, label: str, kind: str, priority: int) -> SummaryArtifact | None:
    content = _read_if_exists(path)
    if not content.strip():
        return None
    return SummaryArtifact(
        label=label,
        path=str(path.relative_to(run_dir)),
        kind=kind,
        priority=priority,
        content=content,
    )


def _render_json_artifact(run_dir: Path, path: Path, *, label: str, kind: str, priority: int) -> SummaryArtifact | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return SummaryArtifact(
        label=label,
        path=str(path.relative_to(run_dir)),
        kind=kind,
        priority=priority,
        content=json.dumps(data, ensure_ascii=False, indent=2),
    )


def _render_jsonl_artifact(run_dir: Path, path: Path, *, label: str, kind: str, priority: int) -> SummaryArtifact | None:
    rows = _load_jsonl(path)
    if not rows:
        return None
    return SummaryArtifact(
        label=label,
        path=str(path.relative_to(run_dir)),
        kind=kind,
        priority=priority,
        content=json.dumps(rows, ensure_ascii=False, indent=2),
    )


def _render_round_artifact(run_dir: Path, path: Path, *, label: str, priority: int) -> SummaryArtifact | None:
    rows = _load_jsonl(path)
    if not rows:
        return None
    rendered: list[str] = []
    for row in rows:
        slot = str(row.get("slot") or "?")
        role_name = str(row.get("role_name") or "")
        group_title = str(row.get("group_title") or "")
        content = str(row.get("content") or "").strip()
        rendered.append(f"### {slot} {role_name} · {group_title}\n\n{content}")
    return SummaryArtifact(
        label=label,
        path=str(path.relative_to(run_dir)),
        kind="role_round",
        priority=priority,
        content="\n\n".join(rendered),
    )


def collect_summary_artifacts(run_dir: Path, *, include_background: bool = False) -> list[SummaryArtifact]:
    artifacts: list[SummaryArtifact] = []

    for artifact in [
        _artifact_from_path(run_dir, run_dir / "input.md", label="原始场景", kind="scenario", priority=0),
        _render_json_artifact(run_dir, run_dir / "run_config.json", label="运行配置", kind="metadata", priority=0),
        _render_json_artifact(run_dir, run_dir / "metrics.json", label="运行指标", kind="metadata", priority=0),
        _render_json_artifact(run_dir, run_dir / "status.json", label="监控状态", kind="metadata", priority=0),
        _render_jsonl_artifact(run_dir, run_dir / "errors.jsonl", label="错误记录", kind="metadata", priority=0),
        _artifact_from_path(
            run_dir,
            run_dir / "compact_archive_summary.md",
            label="早期 compact 滚动摘要",
            kind="compact_archive",
            priority=1,
        ),
        _artifact_from_path(run_dir, run_dir / "final_summary.md", label="标准最终总结", kind="baseline_summary", priority=1),
        _artifact_from_path(run_dir, run_dir / "run_index.md", label="运行产物索引", kind="artifact_index", priority=1),
        _artifact_from_path(
            run_dir,
            run_dir / "final" / "process_timeline.md",
            label="最终过程时间线",
            kind="artifact_index",
            priority=1,
        ),
        _artifact_from_path(
            run_dir,
            run_dir / "final" / "output_tree.md",
            label="最终产物树",
            kind="artifact_index",
            priority=1,
        ),
    ]:
        if artifact is not None:
            artifacts.append(artifact)

    run_config = _load_json(run_dir / "run_config.json")
    loops = int((run_config.get("scenario") or {}).get("loops") or 0)
    if loops <= 0:
        loop_dirs = sorted(run_dir.glob("loop_[0-9][0-9]"))
    else:
        loop_dirs = [run_dir / f"loop_{index:02d}" for index in range(1, loops + 1)]

    for loop_dir in loop_dirs:
        if not loop_dir.exists():
            continue
        loop_label = loop_dir.name.replace("_", " ")
        loop_artifacts = [
            _artifact_from_path(run_dir, loop_dir / "compact.md", label=f"{loop_label} compact", kind="compact", priority=1),
            _artifact_from_path(
                run_dir,
                loop_dir / "stage_report.md",
                label=f"{loop_label} 阶段报告",
                kind="stage_report",
                priority=1,
            ),
            _artifact_from_path(
                run_dir,
                loop_dir / "discussion_plan.md",
                label=f"{loop_label} 讨论计划",
                kind="discussion_plan",
                priority=2,
            ),
        ]
        if include_background:
            loop_artifacts.append(
                _artifact_from_path(
                    run_dir,
                    loop_dir / "background_context.md",
                    label=f"{loop_label} 背景上下文",
                    kind="background_context",
                    priority=5,
                )
            )
        artifacts.extend(artifact for artifact in loop_artifacts if artifact is not None)

        for round_path in sorted(loop_dir.glob("subcycle_*_*/discussion_round_*.jsonl")):
            round_name = round_path.stem
            subcycle_name = round_path.parent.name
            is_summary_round = round_name.endswith("_04")
            priority = 2 if is_summary_round else 3
            label = f"{loop_label} {subcycle_name} {round_name}"
            artifact = _render_round_artifact(run_dir, round_path, label=label, priority=priority)
            if artifact is not None:
                artifacts.append(artifact)

    return sorted(artifacts, key=lambda item: (item.priority, item.path))


def _trim_middle(text: str, max_chars: int) -> tuple[str, str]:
    if max_chars <= 0:
        return "", "dropped"
    if len(text) <= max_chars:
        return text, "full"
    if max_chars < 240:
        return text[:max_chars], "head_excerpt"
    omitted = len(text) - max_chars
    marker = f"\n\n[... 中间省略 {omitted} 字符，以适配最终总结上下文预算 ...]\n\n"
    head_chars = max(80, (max_chars - len(marker)) // 2)
    tail_chars = max(80, max_chars - len(marker) - head_chars)
    return text[:head_chars].rstrip() + marker + text[-tail_chars:].lstrip(), "middle_excerpt"


def _render_artifact_block(artifact: SummaryArtifact, content: str, mode: str) -> str:
    return (
        f"## Artifact: {artifact.label}\n\n"
        f"- path: `{artifact.path}`\n"
        f"- kind: `{artifact.kind}`\n"
        f"- priority: `{artifact.priority}`\n"
        f"- mode: `{mode}`\n\n"
        f"{content}\n"
    )


def build_context_bundle(
    run_dir: Path,
    *,
    max_chars: int | None = DEFAULT_DEEP_CONTEXT_CHARS,
    include_background: bool = False,
) -> ContextBundle:
    artifacts = collect_summary_artifacts(run_dir, include_background=include_background)
    original_chars = sum(artifact.chars for artifact in artifacts)
    hard_cap = max_chars if max_chars and max_chars > 0 else None

    header = (
        "# Deep Final Summary Context Bundle\n\n"
        "这个证据包用于五回合结束后的深度最终总结。证据按优先级排序："
        "0=原始场景/配置/指标，1=compact/阶段报告/既有最终总结，"
        "2=讨论计划与角色第4轮自总结，3=原始角色讨论，5=派生背景上下文。\n\n"
        f"- artifact_count: {len(artifacts)}\n"
        f"- original_chars: {original_chars}\n"
        f"- max_chars: {hard_cap or 'unlimited'}\n"
        f"- estimated_original_tokens: {estimate_tokens_from_chars(original_chars)}\n\n"
    )
    parts = [header]
    packed: list[PackedArtifact] = []

    for artifact in artifacts:
        remaining = None if hard_cap is None else hard_cap - sum(len(part) for part in parts)
        if remaining is not None and remaining <= 0:
            packed.append(
                PackedArtifact(
                    label=artifact.label,
                    path=artifact.path,
                    kind=artifact.kind,
                    priority=artifact.priority,
                    original_chars=artifact.chars,
                    included_chars=0,
                    mode="dropped",
                )
            )
            continue
        desired = artifact.content if remaining is None else artifact.content[: max(0, remaining)]
        included, mode = _trim_middle(artifact.content, remaining if remaining is not None else artifact.chars)
        if not included and remaining is not None:
            packed.append(
                PackedArtifact(
                    label=artifact.label,
                    path=artifact.path,
                    kind=artifact.kind,
                    priority=artifact.priority,
                    original_chars=artifact.chars,
                    included_chars=0,
                    mode="dropped",
                )
            )
            continue
        if remaining is not None and len(_render_artifact_block(artifact, included, mode)) > remaining:
            included, mode = _trim_middle(desired, max(0, remaining - 220))
        block = _render_artifact_block(artifact, included, mode)
        if remaining is None or len(block) <= remaining:
            parts.append(block)
            packed.append(
                PackedArtifact(
                    label=artifact.label,
                    path=artifact.path,
                    kind=artifact.kind,
                    priority=artifact.priority,
                    original_chars=artifact.chars,
                    included_chars=len(included),
                    mode=mode,
                )
            )

    text = "\n".join(parts).rstrip() + "\n"
    manifest = {
        "run_dir": str(run_dir),
        "artifact_count": len(artifacts),
        "original_chars": original_chars,
        "included_chars": len(text),
        "max_chars": hard_cap,
        "estimated_included_tokens": estimate_tokens_from_chars(len(text)),
        "include_background": include_background,
        "artifacts": [asdict(item) for item in packed],
    }
    return ContextBundle(text=text, manifest=manifest)


def deep_final_summary_messages(context_bundle: str) -> list[dict[str, str]]:
    system = (
        COORDINATOR_SYSTEM
        + "\n\n你现在是最终总结审计器、开放问题分析员和文档合成编辑。你的任务不是复述阶段报告，也不是强行给出单一结论，"
        "而是基于完整运行证据包重建五回合后的思想景观、临时结论、保留分歧和流程质量。请使用最强推理能力，严格区分证据、推断、共识、条件共识、不可化约分歧和外部待定事项。"
    )
    user = f"""请基于下面的“最长上下文证据包”生成五回合讨论后的 deep_summary 综合目录内容。

工作要求：
- 先以证据包为准，不要只相信既有 final_summary。
- 不展示隐藏思考过程；输出可审计结论和证据定位。
- 明确区分：全体明确同意、部分角色有条件同意、仍反对、需外部主体决定。
- 不要把角色让步写成无条件共识，不要把模拟组织无权决定的事项写成已通过。
- 不要为了“有结果”而压平抽象问题；必须保留概念冲突、价值冲突、少数观点和最强反方。
- 如果证据包被截断，必须在“证据限制”中说明哪些部分可能不完整。
- 你要一次性产出三个独立 Markdown 文档的正文，程序会按标签拆分成三个文件。
- 严格使用下列 XML-like 标签包裹每份文档；标签外不要输出正文。

<DISCUSSION_RESULT_MD>
# 对这个问题讨论出来的结果

必须包含：
1. 执行摘要
2. 讨论结果景观：临时结论、条件共识、不可化约分歧
3. 最终议案版本或建议文本：如果讨论没有形成充分结果，必须标注“仅为条件性草案”
4. 抽象问题地图：核心概念、价值冲突、制度假设和经验差异
5. 条款级/议题级决策矩阵
6. 核心事实、数字和硬约束
7. 本组织可建议/试点的事项、仅能继续讨论的事项、需外部主体决定或审批的事项
8. 风险清单与中止/退出触发条件
9. 证据地图：列出关键结论来自哪些 Artifact/path
10. 证据限制与需要补充的信息
</DISCUSSION_RESULT_MD>

<PROCESS_ANALYSIS_MD>
# 对整个讨论流程的客观分析

必须包含：
1. 流程概览：五回合、每回合 compact/planning/subcycle/stage report/final 的实际作用
2. 子讨论组拆分是否合理，是否真正生成不同视角，而不是四个角色一路走到底
3. 角色互动分析：谁推动概念澄清，谁保持反对，谁提出关键约束，谁被边缘化
4. 论证质量分析：事实使用、价值冲突、程序边界、外部依赖、抽象层次
5. 共识形成路径：哪些让步是真共识，哪些只是阶段性妥协，哪些不该被写成结果
6. 讨论流程的客观问题：重复、遗漏、偏见、过度生成、证据不足、权限混淆风险
7. 对议案讨论引擎的测试价值：上下文保持、角色一致性、并行轮次、第四轮自总结、compact 质量
8. 可量化指标引用：调用数、tokens、reasoning tokens、prompt cache hit/miss、错误数、长度截断、产物完整性；如证据包缺少 metrics，明确说明
9. 改进建议：下一版工作流、prompt、监控和产物结构怎么优化
</PROCESS_ANALYSIS_MD>

<SYNTHESIZED_DOCUMENT_MD>
# 原文的文档合成稿

这不是流程分析，而是一份面向读者/委员会/归档的正式合成稿。必须包含：
1. 标题和摘要
2. 背景与问题定义
3. 讨论基础事实
4. 抽象问题与主要观点
5. 条件性建议方案或议案文本
6. 具体条款/议题矩阵
7. 实施路径或继续讨论路径
8. 监督、评估、退出机制
9. 外部审批/备案事项
10. 风险与保障
11. 附录：讨论过程摘要和证据来源
</SYNTHESIZED_DOCUMENT_MD>

最长上下文证据包：

{context_bundle}
"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def split_deep_summary_package(raw_text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    for key, spec in PACKAGE_SECTIONS.items():
        pattern = re.compile(
            re.escape(str(spec["start"])) + r"\s*(.*?)\s*" + re.escape(str(spec["end"])),
            flags=re.S,
        )
        match = pattern.search(raw_text)
        if match:
            sections[key] = match.group(1).strip()

    if len(sections) == len(PACKAGE_SECTIONS):
        return sections

    heading_fallbacks = {
        "discussion_result": r"(?m)^#\s*对这个问题讨论出来的结果\s*$",
        "process_analysis": r"(?m)^#\s*对整个讨论流程的客观分析\s*$",
        "synthesized_document": r"(?m)^#\s*原文的文档合成稿\s*$",
    }
    found: list[tuple[str, int, int]] = []
    for key, pattern in heading_fallbacks.items():
        match = re.search(pattern, raw_text)
        if match:
            found.append((key, match.start(), match.end()))
    found.sort(key=lambda item: item[1])
    for index, (key, start, _end) in enumerate(found):
        next_start = found[index + 1][1] if index + 1 < len(found) else len(raw_text)
        sections.setdefault(key, raw_text[start:next_start].strip())
    return sections


def _package_index(package_manifest: dict[str, Any]) -> str:
    files = package_manifest["files"]
    lines = [
        "# Deep Summary 综合目录",
        "",
        "这个目录由最长上下文证据包生成，用于把五回合后的讨论产物拆成三类可读文档。",
        "",
        "## 文档",
        "",
    ]
    for item in files:
        lines.append(f"- [{item['title']}]({item['filename']})")
    lines.extend(
        [
            "",
            "## 生成信息",
            "",
            f"- raw_output: `{package_manifest['raw_output']}`",
            f"- complete_sections: `{package_manifest['complete_sections']}`",
            f"- missing_sections: `{', '.join(package_manifest['missing_sections']) or 'none'}`",
        ]
    )
    return "\n".join(lines)


def write_deep_summary_package(
    run_dir: Path,
    raw_text: str,
    *,
    package_dir: str | Path = DEFAULT_PACKAGE_DIR,
    raw_output: str | Path = "deep_final_summary.md",
) -> dict[str, Any]:
    out_dir = run_dir / package_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_path = run_dir / raw_output
    write_text(raw_path, raw_text)
    write_text(out_dir / "00_raw_model_output.md", raw_text)

    sections = split_deep_summary_package(raw_text)
    files: list[dict[str, Any]] = []
    missing: list[str] = []
    for key, spec in PACKAGE_SECTIONS.items():
        content = sections.get(key)
        filename = str(spec["filename"])
        if not content:
            missing.append(key)
            content = (
                f"# {spec['title']}\n\n"
                "本节未能从模型输出中按标签解析出来。请查看 `00_raw_model_output.md`。"
            )
        write_text(out_dir / filename, content)
        files.append(
            {
                "key": key,
                "title": spec["title"],
                "filename": filename,
                "chars": len(content),
                "parsed": key not in missing,
            }
        )

    manifest = {
        "package_dir": str(out_dir),
        "raw_output": str(raw_path.relative_to(run_dir)),
        "complete_sections": not missing,
        "missing_sections": missing,
        "files": files,
    }
    write_text(out_dir / "index.md", _package_index(manifest))
    write_json(out_dir / "manifest.json", manifest)
    return manifest


def write_context_bundle(run_dir: Path, bundle: ContextBundle, *, subdir: str = "deep_summary") -> tuple[Path, Path]:
    out_dir = run_dir / subdir
    bundle_path = out_dir / "context_bundle.md"
    manifest_path = out_dir / "manifest.json"
    write_text(bundle_path, bundle.text)
    write_json(manifest_path, bundle.manifest)
    return bundle_path, manifest_path


def append_deep_summary_transcript(run_dir: Path, request_meta: dict[str, Any], result: Any) -> None:
    path = run_dir / "deep_summary" / "transcript.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "call_type": "deep_final_summary",
        "client_key": "coordinator",
        "request": request_meta,
        "usage": result_summary(result),
        "content_preview": result.content[:500],
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
