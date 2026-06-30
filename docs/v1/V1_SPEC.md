# V1 Label Spec — Model 1: Page Purpose Classifier

```
spec_version: v4.0
status: locked for the 5-project bootstrap (re-tag under v4.0)
canonical: this file is the single source of truth for labeling
```

Change rules: edit this file in place, bump `spec_version`, add a matching `DECISION_LOG.md` entry,
keep the filename stable. Old v3.0 labels are kept as weak historical (see §Storage); only
`human_reviewed` v4.0 labels are trusted ground truth.

> ## SCOPE GUARDRAIL
> Section 8 (observations) is allowed only if it stays observation **capture**, not extraction.
> During the bootstrap, record facts **visible on the page**. Do **not** compute flooring square
> footage, sum rooms, decide flooring subsets, trace polygons, verify scale, or build Model 2/3/4.
> **Model 1 stays Model 1.**

## 0. The one-line change (v3.0 → v4.0)
**Old target:** "Is this page flooring-relevant / should Elite bid this project?"
**New target:** "What downstream job(s) can this page help with, and how important is it for each?"

Model 1 **classifies and ranks pages by purpose.** Any company-specific bid decision is a
swappable rules layer applied **after** the model (`bid_filter_result`), never a learned target —
we have no ground truth for it. ("V1" = Model 1 in the roadmap; "v4.0" = this spec's revision.)

## 1. Model roadmap
1. **Model 1 — Page Purpose Classifier** (this spec). Cheap/serverless at runtime, **not an LLM**.
2. **Model 2 — Finish Material Extractor** (rules + table parse + LLM + human review first).
3. **Model 3 — Room / Finish Assignment Assistant.**
4. **Model 4 — Quantity Takeoff / Geometry Assistant** (SF, LF base, transitions, counts).

Build in order 1 → 2 → 3/4. **Observe for all four now; build only Model 1 this phase.**

## 2. Label hierarchy
```
project / permit bundle   ← ingestion unit; profile + sf_readiness DERIVED; no learned bid decision
  └─ document / PDF        ← first-class: provenance, disposition, dedup, supersede
       └─ page             ← PRIMARY labeling/training unit
            └─ (later: block / table / room / polygon for Models 2 & 4)
```

## 3. Page object

### 3.1 Field tiers
**Required on every page (incl. negatives):** `page_role`, `useful_for`, `evidence_text`,
`needs_review`, `label_source`, `reviewed`, `spec_version`.
Plus identity: `project_id, document_id, doc_id, filename, pdf_page_number, page_index,
sheet_number, sheet_title, created_at`.

**Required when `useful_for` is non-empty:** `tag_importance` (the **source of truth** for ranking).

**Required when the tag is present:** `context_signals` (if `project_context`);
`measurement_readiness` (if `quantity_takeoff`).

**Optional enrichment (fill ONLY when obvious — `yes/no/unclear`):** `observations`,
`tag_confidence`, `evidence_keywords`.

**Derived by code/postprocessor, never hand-labeled:** `overall_importance`; `primary_uses`;
`display_primary_use`; `observations.scanned_or_low_text`; `observations.vectorized_text_suspected`;
`observations.sf.sf_method`; `observations.sf.sf_confidence`; `project_profile`; `sf_readiness`.
*(Claude may output the facts these are computed from, but must not subjectively "decide" a
derived field — if one appears, it must be mechanically computable from the observed facts.)*

**Key-presence convention:** always emit the required-every-page keys; conditional keys are
emitted present-but-empty when N/A (`context_signals: []`, `tag_importance: {}`).

### 3.2 `useful_for` tag set (locked)
| tag | feeds | meaning |
|-----|-------|---------|
| `finish_material`  | Model 2 | finishes/materials, codes, products, specs, base, transitions, install reqs |
| `room_layout`      | Model 3 | rooms/spaces — names, numbers, walls, layout |
| `quantity_takeoff` | Model 4 | usable for measuring SF/LF/counts; **does NOT require finish callouts** |
| `project_context`  | triage/scope | scope, index, total area, drawing org, revisions, relevant notes |

`useful_for: []` = page not selected for the flooring packet. **Still stored, never deleted.**

### 3.3 Enums
- `importance` (`tag_importance` values + derived `overall_importance`): `primary | supporting | incidental`
- `tag_confidence` (claude/verifier labels; ordinal, not decimal): `high | medium | low`
- `measurement_readiness`: `likely_measurable | maybe_measurable | unlikely | unknown`
- `context_signals`: `scope_of_work | drawing_index | area_summary | revision_or_addendum | vendor_or_finish_reference | project_metadata | general_notes_relevant`
- `schedule_type`: `room_finish_schedule | finish_legend | door_schedule | equipment_schedule | other | null`
- `sf_method` (DERIVED): `not_applicable | stated | room_schedule_sum | dimension_math | scale_measure | manual_needed | unknown`
- `page_role` (descriptive — what the page IS): `title_or_project_info | finish_schedule | finish_legend | finish_floor_plan | architectural_floor_plan | demo_plan | enlarged_flooring_plan | flooring_detail | spec_section | architectural_other | ceiling_rcp | mep | structural | civil_site | paperwork | not_relevant` *(extend only when repeated real examples prove a role is needed)*

### 3.4 `primary_uses` (derived) + `display_primary_use` (derived, UI only)
`tag_importance` is the **source of truth**. A page may be `primary` for several jobs at once —
combined finish-floor-plan/schedule sheets routinely are (finish_material **and** room_layout
**and** quantity_takeoff). Do **not** force a single "main job."

- **`primary_uses`** = every tag in `useful_for` whose `tag_importance == "primary"` (may be 0, 1,
  or many). This is what you rank/select on.
- **`display_primary_use`** = one tag for legacy/UI display only — the first of `primary_uses` by
  the tie-break order below (or, if none are primary, the highest tie-break tag in `useful_for`).
  It is **never** ground truth and must not override `tag_importance`.

Display tie-break order: `quantity_takeoff > finish_material > room_layout > project_context`.

Rank/select per downstream packet straight from the truth — e.g. finish packet = pages where
`tag_importance.finish_material == "primary"`; takeoff packet =
`tag_importance.quantity_takeoff == "primary"`; room packet = `room_layout == "primary"`.

### 3.5 Confidence semantics
`tag_confidence` is mainly for `claude`/`verifier` labels (flags pages needing review). On final
`human_reviewed` labels the load-bearing fields are `useful_for`, `tag_importance`, `needs_review`,
`evidence_text`. Ordinal only — the deployed model emits numeric probabilities later.

### 3.6 Examples

Floor plan (SF-readiness facts captured, **no SF computed**):
```json
{
  "page_role": "architectural_floor_plan",
  "useful_for": ["room_layout", "quantity_takeoff"],
  "tag_importance": { "room_layout": "primary", "quantity_takeoff": "primary" },
  "primary_uses": ["quantity_takeoff", "room_layout"], "display_primary_use": "quantity_takeoff",
  "overall_importance": "primary",
  "measurement_readiness": "likely_measurable",
  "context_signals": [],
  "observations": {
    "room_labels_present": "yes", "room_numbers_present": "yes",
    "finish_callouts_present": "no", "table_or_schedule_present": "no", "schedule_type": null,
    "drawing_index_present": "no", "area_summary_present": "no",
    "flooring_scope_mentioned": "no", "vendor_or_product_names_present": "no",
    "sf": {
      "written_scale_present": "yes", "scale_value": "1/8\"=1'-0\"", "scale_bar_present": "no",
      "dimension_strings_present": "yes", "room_schedule_with_areas": "no", "stated_area": null,
      "match_lines_present": "no", "multi_area_or_split_plan": "no",
      "vector_geometry": "present_clean", "flooring_subset_note": null,
      "sf_method": "scale_measure", "sf_confidence": "medium"
    }
  },
  "evidence_text": "A102 Second Floor Plan; rooms, dimensions, and 1/8\" scale visible.",
  "needs_review": false, "label_source": "claude", "reviewed": false, "spec_version": "v4.0"
}
```

Finish schedule:
```json
{
  "page_role": "finish_schedule",
  "useful_for": ["finish_material", "room_layout"],
  "tag_importance": { "finish_material": "primary", "room_layout": "supporting" },
  "primary_uses": ["finish_material"], "display_primary_use": "finish_material",
  "overall_importance": "primary", "context_signals": [],
  "observations": {
    "table_or_schedule_present": "yes", "schedule_type": "room_finish_schedule",
    "finish_callouts_present": "yes", "room_numbers_present": "yes", "room_labels_present": "yes"
  },
  "evidence_text": "Room finish schedule maps room numbers to floor/base/wall/ceiling finishes.",
  "needs_review": false, "label_source": "claude", "reviewed": false, "spec_version": "v4.0"
}
```

Title sheet (the v3 failure case — `stated_area` recorded if printed, **never summed**):
```json
{
  "page_role": "title_or_project_info",
  "useful_for": ["project_context", "finish_material"],
  "tag_importance": { "project_context": "primary", "finish_material": "supporting" },
  "primary_uses": ["project_context"], "display_primary_use": "project_context",
  "overall_importance": "primary",
  "context_signals": ["scope_of_work", "drawing_index", "area_summary", "vendor_or_finish_reference"],
  "observations": {
    "drawing_index_present": "yes", "area_summary_present": "yes",
    "flooring_scope_mentioned": "yes", "vendor_or_product_names_present": "yes",
    "sf": {
      "stated_area": { "total_sf": 22577, "remodel_sf": 1366, "where": "T1 code analysis block" },
      "flooring_subset_note": "Stated total is the store; flooring is a subset. Do not compute during Model 1.",
      "sf_method": "stated", "sf_confidence": "high"
    }
  },
  "evidence_text": "Title sheet: scope = new flooring in sales/processing; area summary 22,577 SF total / 1,366 SF remodel; vendor list Parterre + Armstrong VCT; drawing index present.",
  "needs_review": false, "label_source": "claude", "reviewed": false, "spec_version": "v4.0"
}
```

Dropped page (negative — stored, minimal evidence):
```json
{
  "page_role": "mep", "useful_for": [], "primary_uses": [], "display_primary_use": null,
  "tag_importance": {}, "overall_importance": "incidental", "context_signals": [],
  "evidence_text": "Mechanical duct plan; no finish, room, context, or quantity value.",
  "needs_review": false, "label_source": "claude", "reviewed": false, "spec_version": "v4.0"
}
```

## 4. Document object (first-class)
Per document: `doc_id, project_id, filename, document_category, disposition, primary_reason_code,
reason_codes, reason_text, confidence, needs_review, label_source, reviewed, spec_version, created_at`.
- `document_category`: `architectural_plan_set | spec_or_project_manual | agency_review_or_report | permit_or_application | contract_or_other | unknown`
- `disposition`: `process | raw_only | duplicate_or_superseded | unknown_review_needed`

Disposition supports provenance/dedup/workflow; it never deletes raw data. Pages are labeled only
for `process` documents; `duplicate_or_superseded`/`raw_only` docs are stored but not page-labeled.

## 5. Project object (no learned decision)
Required: `permit_number, category, project_profile (derived), sf_readiness (derived),
bid_filter_result (optional/app-layer), reviewer_note, needs_review, label_source, reviewed,
spec_version, created_at`.
```json
{
  "permit_number": "24-04531-RNVN", "category": "retail",
  "project_profile": {
    "project_type": "retail",
    "has_finish_material_pages": true, "has_room_layout_pages": true,
    "has_quantity_takeoff_pages": true, "has_project_context_pages": true,
    "finish_schedule_location": "main_arch_set", "spec_location": "main_arch_set",
    "representation_mix": { "digital_text_vector": 4, "vectorized_text": 0, "scanned": 0 }
  },
  "sf_readiness": { "status": "provisional_from_page_observations", "best_method": "stated", "needs_human_ruler": false },
  "bid_filter_result": { "ruleset": "elite_commercial_v1", "decision": "passes_filter", "reason": "Commercial retail with arch plans + finish schedule." },
  "reviewer_note": "", "needs_review": false, "label_source": "claude", "reviewed": false, "spec_version": "v4.0"
}
```
- `category` = descriptive only, **never a gate.**
- `project_profile` + `sf_readiness` = **derived** from page/doc labels. `sf_readiness.status` is
  always `provisional_from_page_observations` — it is **not** a takeoff result.
- `bid_filter_result` = optional app-layer/demo ruleset; not learned, not ground truth.
- The v3 `decision` (keep/disqualify) is **removed as a training target**; human judgment, if any,
  → free-text `reviewer_note`.

## 6. Labeling rules
1. **Every page in a selected project gets a row** — including obvious negatives (`useful_for: []`).
2. **Evidence depth scales with value** — useful pages get specific `evidence_text`; obvious
   negatives get a one-line reason.
3. **Redundancy is allowed** — a title sheet with a vendor list gets the `finish_material` *tag*
   AND `project_context` + `context_signals: [vendor_or_finish_reference]`.
4. **Observations are capture, not extraction.** *Allowed:* record a directly stated area, a
   printed scale value, whether dimensions/rooms/finish callouts/schedules are visible, the
   schedule type, match lines, split/multi-area. *Forbidden during bootstrap:* sum rooms, compute
   flooring SF, decide the flooring subset, trace polygons, verify scale, measure from image/vectors.
5. **Capture only as a byproduct** — if a fact needs opening extra pages or measuring, defer it.
6. **Only `human_reviewed` v4.0 labels are ground truth.**

## 7. Dataset / selection policy
Select for **coverage** across: the four `useful_for` tags; representation types
(digital-text/vector, vectorized-text, scanned/low-text); bundle quality; difficulty; and size.
Simple residential / small commercial earn their place on `room_layout` + `quantity_takeoff` value
alone. **Page-level negatives are intrinsic** (every set is mostly MEP/structural/paperwork) — do
**not** source whole "reject projects" for training. Keep **~5–10% hard-negative *projects* in the
benchmark only** (paperwork-only, sign, facade-only, bad bundles) to test the system, not the model.

## 8. Observation capture (future-proofing) — capture ONLY, never compute (see guardrail)
### 8.1 Durable no-regret capture
Capture/retain: raw PDF; per-page text layer; per-page **vector** layer; rendered image/thumbnail;
coordinate transform; provenance (permit → doc_id → pdf_page_number → S3 key); dedup/superseded
marks; label version history. Vectors are stored in PDF coordinates (resolution-independent), so
future measurement reuses the same source — no re-render needed. *(Runtime note: store text + a
thumbnail for every page; high-res/crops on demand only. Runtime perf is deferred.)*

### 8.2 SF difficulty ladder (conceptual; `sf_method` is DERIVED, not labeled)
`not_applicable` (MEP/spec/legend/RCP/paperwork) · `stated` (numeric area printed — record value
only) · `room_schedule_sum` (per-room areas — **future, not executed in bootstrap**) ·
`dimension_math` / `scale_measure` / `manual_needed` (all Model 4) · `unknown` (flag).

### 8.3 `observations` object (optional, `yes/no/unclear`, fill-when-obvious)
**General:** `room_labels_present, room_numbers_present, finish_callouts_present,
table_or_schedule_present, schedule_type, drawing_index_present, area_summary_present,
flooring_scope_mentioned, vendor_or_product_names_present`.
**`observations.sf` (facts only):** `written_scale_present, scale_value` (literal printed value or
null), `scale_bar_present, dimension_strings_present, room_schedule_with_areas, stated_area`
(printed number + where, or null — **never a computed subtotal**), `match_lines_present,
multi_area_or_split_plan, vector_geometry` (present_clean | present_dense | absent — derived),
`flooring_subset_note` (notes a subset *exists*, never the math); **derived:** `sf_method`,
`sf_confidence`.
**Derived from ingestion (not labeled):** `scanned_or_low_text`, `vectorized_text_suspected`.

### 8.4 Project rollups (DERIVED post-labeling, not part of hand labeling)
`sf_readiness` (provisional) + content census (how many have finish schedules; where specs live;
scanned/vectorized counts; usable-scale count; stated-area count). Analytics/routing only — must
not slow per-page labeling.

### 8.5 The architecture bet
**LLM** reads/understands/routes + points to evidence. **Code** does deterministic math/geometry
(vectors × scale). **Human** verifies the residual. The LLM never eyeballs pixel distances or
produces final measured quantities. No SF calculator / polygon tracing is part of Model 1.

### 8.6 Bounded "now" win
Capture obvious SF-readiness observations; a directly **stated** area may be recorded if visibly
printed. **Do not compute takeoff totals during the bootstrap.**

## 9. Storage & migration
- **Lean JSONB.** v4 label = one JSONB document (new v4 store, migration **005**). Validate
  shape/enums in **code** (JSON schema/validator), not rigid per-field DB columns.
- **Coexist, never overwrite.** v3 tables/labels remain untouched as weak historical; v4.0 labels
  are written alongside. `spec_version` distinguishes schema; `label_source`
  (`claude | verifier | human_reviewed | model`) distinguishes source. Only `human_reviewed` v4.0
  is trusted ground truth.

## 10. Contradiction checker (deterministic flags → needs_review)
- page `useful_for: []` but text/title has FINISH SCHEDULE / ROOM FINISH SCHEDULE / FINISH FLOOR
  PLAN / LVT / CPT / TILE / RUBBER / RESILIENT / BASE / FLOORING.
- `quantity_takeoff` ∈ `useful_for` but `measurement_readiness` missing/`unknown` with a clearly
  scaled plan.
- `schedule_type` = `door_schedule`/`equipment_schedule` but `useful_for` includes `finish_material`.
- doc `raw_only`/`duplicate_or_superseded` but filename/titles suggest arch/interior plans, finish
  schedule/plan, project manual, specs, flooring details.
- `tag_confidence` high but `evidence_text` weak/empty.
- text very thin but the visual page looks like a plan/schedule/legend/detail.
Flagged → `needs_review = true`; note in `reason`/`reviewer_note`.
