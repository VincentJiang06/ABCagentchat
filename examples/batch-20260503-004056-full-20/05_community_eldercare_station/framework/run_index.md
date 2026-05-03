# Run Index

This file summarizes the categorized run artifact layout.

## Top-Level Sections

- `process/`: raw execution evidence, role discussion rounds, stage reports, transcript, errors, audit, and metrics.
- `compact and planning/`: compact ledgers, compact archive summaries, background contexts, and planning JSON/Markdown.
- `final summary/`: final summary output and reader-facing split documents.
- `framework/`: original scenario snapshot, effective runtime config, and artifact index.

## Key Files

- `framework/input.md`: original scenario snapshot.
- `framework/run_config.json`: effective loop/profile/runtime options.
- `monitor.html` and `status.json`: browser-readable live monitor outputs when monitoring is enabled.
- `process/transcript.jsonl`: request metadata, usage, and previews for every model call.
- `compact and planning/loop_XX/compact.md`: inherited open discussion state ledger.
- `compact and planning/loop_XX/discussion_plan.md`: per-loop perspective and group planning.
- `process/loop_XX/subcycle_*/discussion_round_*.jsonl`: role discussion records.
- `process/loop_XX/stage_report.md`: stage-level thought report.
- `final summary/final_summary.md` and `final summary/00_full_final_summary.md`: full final summary stage output.
- `final summary/01_discussion_result.md`: discussion result landscape and conditional recommendations.
- `final summary/02_process_analysis.md`: objective workflow/process analysis.
- `final summary/03_synthesized_document.md`: reader-facing synthesized document.
- `final summary/04_evidence_and_next_steps.md`: evidence gaps and follow-up testing recommendations.
- `final summary/manifest.json`: final package file manifest.
- `final summary/process_timeline.md`: loop report timeline.
- `final summary/output_tree.md`: complete artifact tree.

## Artifact Tree

# Output Tree

- compact and planning/
  - loop_01/
    - background_context.md
    - compact.md
    - discussion_plan.json
    - discussion_plan.md
    - discussion_plan.raw.json
  - loop_02/
    - background_context.md
    - compact.md
    - discussion_plan.json
    - discussion_plan.md
    - discussion_plan.raw.json
    - discussion_plan.repaired.json
  - loop_03/
    - background_context.md
    - compact.md
    - discussion_plan.json
    - discussion_plan.md
    - discussion_plan.raw.json
- final summary/
  - 00_full_final_summary.md
  - 01_discussion_result.md
  - 02_process_analysis.md
  - 03_synthesized_document.md
  - 04_evidence_and_next_steps.md
  - README.md
  - final_summary.md
  - manifest.json
  - process_timeline.md
- framework/
  - input.md
  - run_config.json
- monitor.html
- process/
  - loop_01/
    - stage_report.md
    - subcycle_01_a/
      - discussion_round_01.jsonl
      - discussion_round_02.jsonl
      - discussion_round_03.jsonl
    - subcycle_02_b/
      - discussion_round_01.jsonl
      - discussion_round_02.jsonl
      - discussion_round_03.jsonl
  - loop_02/
    - stage_report.md
    - subcycle_01_a/
      - discussion_round_01.jsonl
      - discussion_round_02.jsonl
      - discussion_round_03.jsonl
  - loop_03/
    - stage_report.md
    - subcycle_01_a/
      - discussion_round_01.jsonl
      - discussion_round_02.jsonl
      - discussion_round_03.jsonl
    - subcycle_02_b/
      - discussion_round_01.jsonl
      - discussion_round_02.jsonl
      - discussion_round_03.jsonl
    - subcycle_03_c/
      - discussion_round_01.jsonl
      - discussion_round_02.jsonl
      - discussion_round_03.jsonl
  - run.log
  - transcript.jsonl
  - warnings.jsonl
- status.json
