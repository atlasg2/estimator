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
- Allowlisted Codespace IP → RDS; **migration 004 applied**. Built review UI (`tools/review_app.py`).
- Added North Star + training cadence + benchmark gates to the docs.
- Decided: 25 = re-label already-discovered projects under v3 (prioritize the 20 already extracted),
  no new discovery; dataset includes **rejects** (≈⅓), heavy extraction on keeps / light on rejects.
- Added rule: Claude proposes adjustments / new insights when it sees a better way.
- Labeled bootstrap **#1 church `24-21892`** (keep, 26pp; A101 finish floor plan critical).
- Labeled **#2 restaurant `25-02683`** (keep-LOW/needs_review, 14pp). Archetype: NO finish
  schedule; only flooring evidence is A6.0 bathroom tile layout (hex/subway/cove). Marked the
  14pp HDLC-approved set primary; the 8pp set is a duplicate subset (`duplicate_or_superseded`).
- Labeled **#3 TJ Maxx `24-04531`** (keep, 4pp). Canonical good retail: RC2 carries the room
  material & finish schedule + finish legend (VCT/LVT/ceramic/cove base) — **the exact page
  prompt-v1 wrongly called not_flooring; v3 marks it critical.** RCC-stamped set primary; plain
  permit set is its unstamped duplicate.
- All 3 live in the review UI (`tools/review_app.py`, http://localhost:8000).
- **Next:** user reviews first 3 in the UI → feedback → then label #4 (`25-16244`) & #5
  (`25-26809` disqualify). Labels currently in `data/v1_labels/` JSON; DB write still pending.

### 2026-06-30
- All 5 bootstrap projects had been Claude-labeled under v3 (`data/v1_labels/`); rebuilt the review
  UI (`tools/review_app.py`, uncommitted) — overview + thumbnail grid + zoom + dropdowns.
- **Major pivot v3.0 → v4.0:** Model 1 reframed from Elite keep/disqualify triage to a **Page
  Purpose Classifier** (`useful_for` = finish_material / room_layout / quantity_takeoff /
  project_context; per-tag `tag_importance`; derived `overall_importance`/profiles; ordinal
  confidence; every page gets a row; byproduct `observations` incl. `observations.sf` for
  square-footage *readiness* facts under a strict no-compute guardrail). Converged with GPT over
  several rounds — trail in `docs/proposals/` (rescope → reply-to-gpt → page-purpose-v4.0 →
  project-selection-and-prep).
- **Applied to canonical:** rewrote `V1_SPEC.md` (v4.0), updated `V1_RUNBOOK.md`, `V1_PHASE_PLAN.md`,
  `CLAUDE.md` STATUS + North Star; appended `DECISION_LOG.md` entry; added migration
  `005_v4_jsonb_labels.sql` (non-destructive JSONB v4 store; v3 untouched).
- **Next:** apply migration 005 to RDS (needs DB access), then **re-tag the 5 under v4.0** (every
  page; label `25-26809` fully) → human review → decide before scaling to 25. No UI rebuild, no SF
  computation yet.
- **v4.0 tweak:** dropped single `primary_use` → derived `primary_uses` (all primary tags) +
  `display_primary_use` (UI tie-break); `tag_importance` is the source of truth. Dissolves the
  RC2-vs-A101 combined-sheet inconsistency. Spec/runbook/decision-log updated; both labels + UI updated.
- **Re-tagged ALL 5 under v4.0** (`data/v1_labels_v4/`, v3 untouched): 24-04531 (4pp),
  24-21892 (26pp), 25-02683 (14pp), 25-16244 (9pp), 25-26809 (8pp). **61 pages, 22 keeps, 39 drops,
  6 needs_review.** Did a true multimodal pass (read the key sheets).
- **Built mobile review view** (`/m`, auto-redirect for phones) + made port 8000 public for phone
  access. UI still cramped for dense sheets — flagged for a proper mobile redo (parked).
- **Findings:** SF spread = 1 scale_measure / 3 room_schedule_sum / 1 not_applicable (great Model-4
  coverage). 24-21892 finish schedule HAS an area column (room_schedule_sum); TJ Maxx does not
  (scale_measure). **finish_material is SPARSE (6 pages; 2 of 5 projects have NO finish schedule at
  all)** — big implication for Model 2. 25-26809 has NO plans (only a FEMA elevation cert) → a
  "no-usable-plans" empty-packet hard-negative; bid_filter correctly fails it. Negatives intrinsic
  (64% of pages dropped) — confirms no need to source reject projects.
- **Next:** human-review the 5 (gate) → mobile UI redo → apply migration 005 + write to RDS →
  scale toward 25 (seek more finish-schedule-present + scanned/vectorized projects).
