# V1 Spec — Status & Open Items to Finalize

## Where we are
- Goal: a **verified labeled dataset** → train a **fast serverless triage model** (predicts page
  usefulness + page role + confidence; project/doc decisions **derived** from page/doc predictions
  + metadata). The LLM is the *offline labeler*, not the runtime model.
- **48 projects labeled historically** — 25 under prompt **v1**, 23 under prompt **v2**. These are now
  **OLD / WEAK labels**: kept in the DB, **not** used as trusted training ground truth.
- **Human review started.** Confirmed: **v1 under-calls** (a TJ Maxx **finish schedule** was labeled
  `not_flooring` — a true miss), **v2 over-calls** critical (the safe direction).
- **Decision:** freeze a clean final spec (call it **v3**) and relabel fresh under it.

## Locked decisions
- **Gates:** 5 (bootstrap — refine spec/process, *not* for training) → 25 (first verified dataset +
  first model) → 50 (benchmark) → 112+ (scale later). Not optimizing for thousands yet.
- **Labeling process:** ONE careful **project-by-project** pass — **no multi-agent batch fan-out**.
  Text-first; open the page image only when text is thin/ambiguous/scanned. Then human review, then
  next project.
- **25-set split BY PROJECT:** 15 train / 5 val / 5 test. Split by whole project (no page-level
  leakage), **stratified** so each split contains finish-schedule-rich projects.
- **Production behavior:** model **ranks/selects** pages for the flooring packet and **retains raw
  data** — it may hide/deprioritize, never deletes.
- **Trust rule:** for `process` docs, **extract ALL pages**. Page labels are training/review metadata,
  **not** a page-skip filter — only after recall targets are met (finish floor plan ≥97%, finish
  schedule/spec ≥98%, ~0 critical false negatives on held-out projects).
- **Reason layer:** deterministic rules + stored evidence snippets — **not** an LLM at runtime, not the
  model writing prose. Model outputs prediction + confidence (+ maybe top features).
- **Verification (v1):** Claude labeler → deterministic contradiction checker → one verifier agent on
  flagged cases → human review. (No N-refuter majority vote yet.)
- **Tables:** versioned — `classification_runs`, `project_labels`, `document_labels`, `page_labels`.
  Every row carries `label_source` (claude/verifier/human/model), `spec_version`, `confidence`,
  `evidence`, `needs_review`, `created_at`. **Only human-verified labels = ground truth.**

## Label schema (proposed — near final)
**Project:** decision `keep | disqualify | unknown_review_needed`; fields: decision, reason_code,
reason_text, confidence, needs_review.

**Document:** disposition `process | raw_only | unknown_review_needed`; fields: disposition,
document_category, reason_code, reason_text, confidence, needs_review.
- document_category: `architectural_plan_set, interior_finish_set, project_manual_or_spec,
  addendum_flooring_relevant, mep_flooring_relevant, paperwork_or_approval, mep_structural_civil, unknown`

**Page:** page_usefulness `critical_flooring | useful_flooring | maybe_flooring | not_flooring |
unknown_review_needed`; page_role (limited v1 set) `finish_floor_plan, finish_schedule_or_legend,
project_manual_or_spec, flooring_detail, title_or_project_info, general_notes, architectural_other,
not_relevant, unknown`; plus flooring_relevant, sheet_number, sheet_title, confidence, evidence_text,
evidence_keywords, input_tier `text_only | text_plus_image | human_review`, needs_review.

## OPEN — needed to finalize the spec (please confirm/lock)
1. **`reason_code` vocabulary** — the main undefined piece. DRAFT below — approve/edit:
   - *project disqualify:* `no_plans, mep_or_structural_only, sitework_or_civil_only,
     signage_or_facade_only, demo_only, residential_out_of_scope, paperwork_only`
   - *project keep:* `has_plan_set, has_finish_schedule, commercial_interior_fit`
   - *doc raw_only:* `mep_discipline, fire_or_sprinkler, civil_or_survey, structural_only,
     paperwork_or_approval, receipt_or_contract, photometric, duplicate_or_superseded`
   - *page not_flooring:* `elevations_only, ceiling_rcp, mep_page, site_or_civil, non_floor_detail,
     notes_or_legend_only, no_flooring_terms`
   - *uncertain (any level):* `thin_evidence, scanned_no_text, vectorized_text_suspected, name_ambiguous`
2. Confirm the **document_category** (8) and **page_role** (9) sets are final, or adjust.
3. Confirm **stratified** 15/5/5 split (by finish-richness) vs pure random.
4. **Review UI** for the bootstrap: minimal **local web app** (page image + Claude's call + agree/fix →
   writes verified labels) vs. keep reviewing conversationally? (process choice)
5. **Bootstrap-5 selection:** pick from our existing discovered pool to hit archetypes
   (fitness / restaurant / retail-or-office / small-simple / one genuine `disqualify`), stratified —
   OK, or discover a fresh 5?

## Immediate next milestone
**5 projects carefully labeled + human-corrected under one frozen spec (v3).**
