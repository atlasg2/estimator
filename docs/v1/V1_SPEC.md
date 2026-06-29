# V1 Label Spec

```
spec_version: v3.0
status: locked for the 5-project bootstrap
canonical: this file is the single source of truth for labeling
```

The label schema for the V1 flooring-triage dataset. Change rules: edit this file in place, bump
`spec_version`, and add a matching `DECISION_LOG.md` entry. Keep the filename stable.

## Scope
The V1 model will eventually predict **`page_usefulness`, `page_role`, `confidence`**. Project and
document decisions are **derived** from page/document predictions + metadata. The LLM is the offline
labeler; the runtime model is not an LLM. The production model may rank/hide/deprioritize pages but
**must not delete raw data**. For any `process` document, full extraction later runs on **all** pages —
page labels are training/review metadata, **not** a page-skip filter.

## Page numbering
Store both: `pdf_page_number` (1-indexed, human) and `page_index` (0-indexed, internal). Output must
always include `pdf_page_number`. Example: `{"pdf_page_number": 1, "page_index": 0}`.

## Input tier
For the bootstrap, **full multimodal review** — review each relevant page with extracted text **and**
the visual page. `input_tier = text_plus_image` for every labeled page. If an image is truly
unavailable: `input_tier = text_only`, `needs_review = true`, `reason_codes` includes
`needs_image_review`. Human review is NOT an input tier — it's `label_source = human_reviewed`,
`reviewed = true`.

## Label source rules
Every row carries `label_source`, `reviewed`, `spec_version`. Allowed `label_source`: `claude |
verifier | human_reviewed | model`. First Claude pass → `claude`, `reviewed=false`, `spec_version=v3.0`.
Corrected final → `human_reviewed`, `reviewed=true`. **Never overwrite Claude labels** — save Claude
and human labels separately. Only `human_reviewed` counts as trusted ground truth for training.

---

## Project labels
`decision`: `keep | disqualify | unknown_review_needed`
Required fields: `project_id, candidate_id, permit_number, decision, primary_reason_code,
reason_codes, reason_text, confidence, needs_review, label_source, reviewed, spec_version, created_at`

**keep reason codes:** `commercial_interior_fit, fitness_retail_restaurant_fit,
has_architectural_plan_set, has_interior_finish_set, has_finish_floor_plan, has_finish_schedule,
has_finish_legend, has_flooring_specs, has_flooring_details, has_enough_flooring_evidence`

**disqualify reason codes:** `no_downloadable_docs, no_usable_plans, paperwork_only,
mep_or_structural_only, sitework_or_civil_only, signage_or_facade_only, demo_only, no_flooring_evidence,
residential_low_value_or_out_of_scope`
*(Do not auto-disqualify all residential; keep some for variety, but a small/low-value residential job
can be disqualified if it doesn't help the dataset.)*

---

## Document labels
`disposition`: `process | raw_only | unknown_review_needed`
`document_category`: `architectural_plan_set, interior_finish_set, project_manual_or_spec,
addendum_flooring_relevant, mep_flooring_relevant, mep_structural_civil, paperwork_or_approval, unknown`
Required fields: `document_id, project_id, filename, doc_id, disposition, document_category,
primary_reason_code, reason_codes, reason_text, confidence, needs_review, label_source, reviewed,
spec_version, created_at`

**process reason codes:** `architectural_plan_set, interior_finish_set, contains_finish_schedule,
contains_finish_legend, contains_finish_floor_plan, contains_flooring_details,
contains_project_manual_specs, addendum_changes_flooring, mep_affects_flooring_or_wet_areas`

**raw_only reason codes:** `mep_discipline, fire_or_sprinkler, civil_or_survey, structural_only,
paperwork_or_approval, receipt_or_contract, photometric, duplicate_or_superseded, no_flooring_evidence`

---

## Page labels
`page_usefulness`: `critical_flooring | useful_flooring | maybe_flooring | not_flooring |
unknown_review_needed`

`page_role`: `finish_floor_plan, finish_schedule, finish_legend, project_manual_or_spec, flooring_detail,
enlarged_flooring_plan, architectural_floor_plan, title_or_project_info, general_notes,
architectural_other, not_relevant, unknown`
- v3.0 intentionally separates **`finish_schedule`** (room→finish tables) from **`finish_legend`**
  (material legends / finish keys explaining codes like LVT-1, CPT-1, CT-1, RB-1, RF-1). If a page has
  both, pick the dominant role and include both reason codes. *(Open hypothesis — see DECISION_LOG: if
  the bootstrap shows these can't be reliably told apart, merge them in v3.1.)*

Required fields: `page_id, project_id, document_id, doc_id, filename, pdf_page_number, page_index,
sheet_number, sheet_title, page_usefulness, page_role, flooring_relevant, primary_reason_code,
reason_codes, reason_text, confidence, evidence_text, evidence_keywords, input_tier, needs_review,
label_source, reviewed, spec_version, created_at`

**useful/critical reason codes:** `sheet_title_finish_floor_plan, sheet_title_finish_schedule,
sheet_title_finish_legend, sheet_title_flooring_spec, contains_room_finish_schedule,
contains_finish_legend, contains_flooring_material_codes, contains_flooring_terms,
contains_flooring_detail, contains_flooring_spec_section,
contains_base_transition_tile_or_wet_area_detail, floor_plan_context_for_takeoff,
enlarged_plan_flooring_relevant`

**not_flooring reason codes:** `mep_page, site_or_civil, structural_page, ceiling_rcp,
elevations_no_flooring_evidence, non_flooring_detail, non_flooring_notes_or_legend,
paperwork_or_approval, no_flooring_terms`
*(Use `non_flooring_notes_or_legend` only when notes/legend are clearly NOT flooring. Never
`notes_or_legend_only` — some legends are flooring-critical.)*

**uncertain reason codes (any level):** `thin_evidence, scanned_no_text, vectorized_text_suspected,
name_ambiguous, conflicting_evidence, needs_image_review, needs_human_review`

`flooring_relevant`: critical/useful/maybe → yes|maybe; not_flooring → no; unknown_review_needed → unknown

---

## Usefulness definitions
- **critical_flooring** — directly needed for takeoff/finish extraction: finish floor plan, floor
  finish plan, room finish schedule, finish schedule, finish legend, flooring spec section, material
  legend with flooring codes.
- **useful_flooring** — supports takeoff but doesn't define quantities: architectural floor plan,
  enlarged flooring plan, flooring/transition/tile/base details, demo plan mentioning flooring removal,
  addendum affecting finishes.
- **maybe_flooring** — possible value, weak/ambiguous evidence: general notes possibly flooring,
  unclear-title arch page, low-text visual plan, scanned page, interior elevations with possible base/tile.
- **not_flooring** — clearly unrelated: electrical, mechanical, fire alarm, sprinkler, civil, survey,
  structural-only, paperwork, receipts, approvals, photometric, ceiling plan with no flooring evidence.
- **unknown_review_needed** — cannot safely decide: conflicting evidence, scanned/no text, unclear
  title, visually-relevant but thin text, possible flooring terms without enough context.

---

## Contradiction checker (deterministic flags → needs_review)
- page `not_flooring` but text/title has FINISH SCHEDULE / ROOM FINISH SCHEDULE / FINISH FLOOR PLAN /
  FLOOR FINISH PLAN / LVT / CPT / TILE / RUBBER / RESILIENT / BASE / FLOORING.
- doc `raw_only` but filename/titles suggest architectural/interior plans, finish schedule/plan,
  project manual, specs, flooring details.
- `confidence` high but `evidence_text` weak/empty.
- text very thin but the visual page looks like a plan/schedule/legend/detail.
- project `disqualify` but any doc/page has finish schedule/floor plan/legend/spec/detail evidence.
Flagged → `needs_review = true`, `reason_codes` includes `conflicting_evidence` or `needs_human_review`.
