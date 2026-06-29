# Worklog

Append-only session diary. One entry per working session: what we did + next step.

---

### 2026-06-29
- Locked `spec_version v3.0`. Wrote the doc system: `CLAUDE.md`, `docs/v1/V1_SPEC.md`,
  `V1_RUNBOOK.md`, `V1_PHASE_PLAN.md`, `DECISION_LOG.md`, this worklog.
- Added migration `004` (new v3 label fields, non-destructive). Decided labels write direct to RDS.
- Selected bootstrap 5: `24-21892, 25-02683, 24-04531, 25-16244, 25-26809`.
- Earlier: reviewed `25-16244` (v2 over-called an empty existing-shell as critical) and `24-04531`
  (v1 under-called the TJ Maxx finish schedule as not_flooring — true miss). These drove v3.0.
- **Next:** allowlist Codespace IP → RDS, apply migration 004, then label project #1 (`24-21892`).
