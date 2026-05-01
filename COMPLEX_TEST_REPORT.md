# Complex Test Report

Date: 2026-05-01

## Scope

This test covered:

- Syntax validation for the simulator modules.
- Dry-run execution for all 10 scenario files.
- One real DeepSeek V4 Pro run on a complex social proposal scenario.

Real scenario tested:

- `scenarios/04_platform_worker_rights.md`
- Output directory: `runs/real-complex-platform-worker-rights`
- Loops: `1`
- Model: `deepseek-v4-pro`
- Mode: thinking enabled, reasoning effort `max`

## Results

All checks passed.

| Check | Result |
|---|---|
| Python compile | pass |
| All 10 scenarios dry-run | pass |
| Real API run completed | pass |
| Model calls | 16 / 16 succeeded |
| Error log | none |
| Stage report generated | yes |
| Final summary generated | yes |

## Real Run Metrics

| Metric | Value |
|---|---:|
| Prompt tokens | 64,856 |
| Completion tokens | 45,188 |
| Reasoning tokens | 22,087 |
| Total model elapsed seconds | 1,416.5 |
| Estimated API cost | $0.270104 |

The run took a long time because coordinator calls used large thinking budgets. The longest calls were:

- Stage report: 199.3s
- Compact: 159.0s
- Persona generation: 156.0s
- Final summary: 137.8s

## Quality Observations

The discussion produced meaningful conflict and revision rather than fake consensus.

Concrete negotiated outputs included:

- 90-day pilot covering two business districts and at least 600 active riders.
- Continuous order-taking limit set around 4.5 hours for the pilot baseline.
- Forced dispatch stop with peak-period delay rules and a hard cap.
- Waiting time counted at 20% toward work-intensity evaluation.
- Holiday and severe-weather subsidies made visible in the rider app.
- Platform subsidy responsibility not below 50%; merchant share capped at 20% and 0.5 yuan per order.
- Urgent appeals first response within 24 hours and resolution within 72 hours.
- Clear boundary that the industry association cannot replace labor arbitration, administrative determination, or courts.

The final summary correctly separated:

- Industry self-regulation items.
- Platform implementation obligations.
- Merchant cost boundaries.
- Rider safety and appeal protections.
- Issues requiring external authorities.

## Issue Found And Fixed

During the real run, terminal output was buffered until completion, making long runs hard to monitor. The simulator now flushes progress output immediately after each phase and role response.

## Follow-up Recommendations

- Add a faster preset for exploratory runs, such as coordinator `32768` and role `16384`.
- Add a report-only scoring script to verify final summaries against expected hard constraints.
- Consider running a second real test on `01_ebike_charging_governance.md` to cover safety, pricing transparency, and community authority boundaries.

