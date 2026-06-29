# V3 Label Spec — FINAL (for ChatGPT confirmation)

## 0. Goal
- Build a **verified labeled dataset** → train a **fast serverless triage model** (predicts page
  usefulness + role + confidence; project/doc decisions **derived** from page/doc predictions +
  metadata). LLM = offline labeler, not the runtime model.
- Production model **ranks/selects** pages for the flooring packet and **retains raw data** —
  hide/deprioritize, never delete.

## 1. Gates
5 (bootstrap — refine spec/process, *not* training) → 25 (first verified dataset + first model;
split 15/5/5 by project) → 50 (benchmark) → 112+ (scale later). Not optimizing for thousands yet.

## 2. Labeling process (one careful pass — no multi-agent fan-out)
One project at a time. For **every page of a doc we're labeling, read the text AND view the page
image** — this is the gold/training pass, so quality beats cost; the cheap text-only path belongs to
the *production model* later, not to building training data. (Filename/name-triage of *which docs to
open* stays text-only — no point rendering docs we're dropping.)
Claude labels → readable explanation → strict JSON → human corrects → save **both** versions:
- raw Claude label: `label_source = claude`, `reviewed = false`
- corrected final label: `label_source = human_reviewed`, `reviewed = true`

## 3. Label schema

### Project
`decision`: keep | disqualify | unknown_review_needed
fields: decision, primary_reason_code, reason_codes[], reason_text, confidence, needs_review
- **keep codes:** commercial_interior_fit, fitness_retail_restaurant_fit, has_architectural_plan_set,
  has_interior_finish_set, has_finish_floor_plan, has_finish_schedule, has_flooring_specs,
  has_flooring_details, has_enough_flooring_evidence
- **disqualify codes:** no_downloadable_docs, no_usable_plans, paperwork_only, mep_or_structural_only,
  sitework_or_civil_only, signage_or_facade_only, demo_only, no_flooring_evidence,
  residential_low_value_or_out_of_scope
  *(Do NOT blanket-disqualify residential; keep some for variety, but a small residential job can be
  disqualified if not useful for the dataset.)*

### Document
`disposition`: process | raw_only | unknown_review_needed
fields: disposition, document_category, primary_reason_code, reason_codes[], reason_text, confidence,
needs_review
- **document_category (locked, 8):** architectural_plan_set, interior_finish_set,
  project_manual_or_spec, addendum_flooring_relevant, mep_flooring_relevant, mep_structural_civil,
  paperwork_or_approval, unknown
- **process codes:** architectural_plan_set, interior_finish_set, contains_finish_schedule,
  contains_finish_floor_plan, contains_flooring_details, contains_project_manual_specs,
  addendum_changes_flooring, mep_affects_flooring_or_wet_areas
- **raw_only codes:** mep_discipline, fire_or_sprinkler, civil_or_survey, structural_only,
  paperwork_or_approval, receipt_or_contract, photometric, duplicate_or_superseded, no_flooring_evidence

### Page
fields: page_usefulness, page_role, flooring_relevant, sheet_number, sheet_title, primary_reason_code,
reason_codes[], confidence, evidence_text, evidence_keywords, input_tier, needs_review
- **page_usefulness:** critical_flooring | useful_flooring | maybe_flooring | not_flooring |
  unknown_review_needed
- **page_role (locked, 9):** finish_floor_plan, finish_schedule_or_legend, project_manual_or_spec,
  flooring_detail, title_or_project_info, general_notes, architectural_other, not_relevant, unknown
- **input_tier:** text_plus_image (default for every labeled page) | text_only (rare — only if image render fails) | human_review
- **useful/critical codes:** sheet_title_finish_floor_plan, sheet_title_finish_schedule,
  sheet_title_flooring_spec, contains_room_finish_schedule, contains_finish_legend,
  contains_flooring_material_codes, contains_flooring_terms, contains_flooring_detail,
  contains_flooring_spec_section, contains_base_transition_tile_or_wet_area_detail,
  floor_plan_context_for_takeoff
- **not_flooring codes:** mep_page, site_or_civil, structural_page, ceiling_rcp,
  elevations_no_flooring_evidence, non_flooring_detail, non_flooring_notes_or_legend,
  paperwork_or_approval, no_flooring_terms
  *(Use `non_flooring_notes_or_legend`, NOT `notes_or_legend_only` — some legends are flooring-critical.)*
- **uncertain codes (any level):** thin_evidence, scanned_no_text, vectorized_text_suspected,
  name_ambiguous, conflicting_evidence, needs_image_review, needs_human_review
- **flooring_relevant mapping:** critical/useful/maybe → yes|maybe; not_flooring → no;
  unknown_review_needed → unknown

## 4. Trust rule
`process` docs → **extract ALL pages**. Page labels are training/review metadata, **not** a page-skip
filter until recall targets are met: finish floor plan ≥97%, finish schedule/spec ≥98%, ~0 critical
false negatives on held-out projects. False positives OK early; **false negatives on critical pages are
dangerous.**

## 5. Split (25-set)
**Stratified project split**, not random page split: 15 train / 5 val / 5 test, by whole project.
Each split must contain some finish-rich projects (don't put all fitness/finish-rich projects in train).

## 6. Verification
Claude labeler → deterministic contradiction checker → one verifier agent on flagged/uncertain →
human review. (No N-refuter majority vote.) Checker flags: not_flooring page whose text has
FINISH SCHEDULE / FLOOR FINISH / LVT / carpet / tile / base; raw_only doc whose name/text looks
architectural/finish/spec; low-text high-vector; scanned/no-text; unknown role; high confidence + weak
evidence.

## 7. Tables (versioned)
`classification_runs`, `project_labels`, `document_labels`, `page_labels`. Every row carries:
label_source (claude | verifier | human_reviewed | model), spec_version, primary_reason_code,
reason_codes[], confidence, evidence, reviewed, needs_review, created_at. Later: model_versions,
page_predictions. **Only `human_reviewed` rows are ground truth.**

## 8. Review UI (building now — minimal local web app)
A small browser tool to step through each project's pages, see the rendered plan image next to Claude's
v3 labels + reasoning, and agree/correct — both to capture verified labels and to learn the taxonomy.
- **Stack:** one Python file (`review_app.py`, FastAPI + uvicorn), serving one HTML page + a few JSON
  endpoints. No Node, no framework, no build step. Page images rendered on demand from the project PDFs
  via PyMuPDF (already a dependency), cached to disk. Opened via the Codespace-forwarded port.
- **Data:** reads raw v3 labels (`data/labels_v3/lb_<permit>.json`); writes corrections to
  `data/labels_v3/reviewed_<permit>.json` (label_source=human_reviewed, reviewed=true). No DB needed
  during review; sync to RDS later.
- **Screens:** (1) project list (type, #pages, progress, Claude's project decision); (2) review view —
  left: zoomable plan page, right: Claude's usefulness/role/flooring_relevant/reason_codes/confidence +
  evidence + input_tier, with **✓ Agree / ✗ Fix** controls (dropdowns + reason-code checkboxes), ←/→
  nav, jump-to-next-flagged; footer running tally (agreed/fixed/precision-so-far); (3) legend/help so
  the taxonomy is learnable as you click.
- **Sequence:** build it for the bootstrap-5, decide after the 5 whether it's good enough for the 25.

## 9. Bootstrap 5 (selected from existing pool)
- fitness: **24-21892** (26 pp)
- restaurant: **25-02683** (22 pp)
- retail: **24-04531** (TJ Maxx, 11 pp — already reviewed; validates v3 fixes the under-call)
- small/simple: **25-16244** (9 pp — already reviewed; validates v3 stops the over-call)
- disqualify: **25-26809** (flood-elevation cert, no plans)

## 10. Immediate milestone
**5 projects labeled under v3, human-corrected, saved as verified labels.**
Do not run 112. Do not train yet. Do not build V2 extraction. Do not build square footage. No
multi-agent batch labeling. After the 5, review results and make one final spec adjustment before the 25.

## 11. Spec evolution (expected)
The spec is expected to evolve as we label. While labeling the bootstrap-5, Claude logs every case
where a label didn't fit a code, a needed code is missing, or a rule is ambiguous →
`docs/V3-SPEC-CHANGES.md`. After the 5, Claude presents a consolidated set of **proposed changes**
(new/removed codes, clarifications) for human + ChatGPT sign-off, folded into **v3.1** before the
25-set. Every label row carries `spec_version`, so nothing silently shifts.
