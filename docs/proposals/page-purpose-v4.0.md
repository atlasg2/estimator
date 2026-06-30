# Model 1 Spec v4.0 — Page Purpose Classifier (converged)

**Status:** CONVERGED draft (human + GPT, two rounds each way). Ready to apply to `V1_SPEC.md`
on your go. **Not yet applied.**
**Date:** 2026-06-30
**Supersedes (as the target):** v3.0 "is this flooring-relevant / worth bidding for Elite?"
**Reads with:** `page-purpose-rescope.md`, `page-purpose-rescope-reply-to-gpt.md`,
`project-selection-and-prep.md`.

> **SCOPE GUARDRAIL (the rule that governs this whole spec):**
> **Section 8 is allowed only if it stays observation *capture*, not extraction.**
> During the 5-project bootstrap we record facts that are *visible on the page*. We do **not**
> compute flooring square footage, sum rooms, decide flooring subsets, trace polygons, or verify
> scale. Model 1 stays Model 1.

---

## 0. The one-line change

**Old target:** *"Is this page flooring-relevant / should Elite bid this project?"*
**New target:** *"What downstream job(s) can this page help with, and how important is it for each?"*

Model 1 classifies and **ranks** pages by purpose. Any company-specific bid decision is a
swappable rules layer applied **after** the model — never a learned target.

> Naming: "V1" = Model 1 in the roadmap; "v4.0" = the revision of *its* spec. Orthogonal.

---

## 1. Model roadmap

1. **Model 1 — Page Purpose Classifier** (this spec). Cheap/serverless at runtime, not an LLM.
2. **Model 2 — Finish Material Extractor.** Rules + table parse + LLM + human review first.
3. **Model 3 — Room / Finish Assignment Assistant.**
4. **Model 4 — Quantity Takeoff / Geometry Assistant** (SF, LF base, transitions, counts).

Build 1 → 2 → 3/4. **Observe for all four now; build none but Model 1.**

---

## 2. Label hierarchy

```
project / permit bundle   ← ingestion unit; profile + sf_readiness are DERIVED, no learned decision
  └─ document / PDF        ← first-class: provenance, disposition, dedup, supersede
       └─ page             ← PRIMARY labeling/training unit
            └─ (later: block/table/room/polygon for Models 2 & 4)
```

---

## 3. Page object (the core)

### 3.1 Field tiers

**Required on every page (incl. negatives):**
`page_role`, `useful_for`, `evidence_text`, `needs_review`, `label_source`, `reviewed`,
`spec_version`.

**Required when `useful_for` is non-empty:** `primary_use`, `tag_importance`.

**Required when the relevant tag is present:**
`context_signals` (if `project_context`); `measurement_readiness` (if `quantity_takeoff`).

**Optional enrichment (fill ONLY when obvious — `yes/no/unclear`):**
`observations` (§8), `tag_confidence`, `evidence_keywords`.

**Derived (never hand-labeled):**
`overall_importance` (= max of `tag_importance`; empty `useful_for` ⇒ `incidental`);
`observations.scanned_or_low_text`, `observations.vectorized_text_suspected` (from ingestion);
`observations.sf.sf_method`, `observations.sf.sf_confidence` (from the observation facts).

> Key-presence convention: always emit the required-every-page keys; conditional keys are emitted
> present-but-empty when N/A (`context_signals: []`, `tag_importance: {}`).

### 3.2 `useful_for` tag set (locked)

| tag | feeds | meaning |
|-----|-------|---------|
| `finish_material`  | Model 2 | finishes/materials, codes, products, specs, base, transitions, install reqs |
| `room_layout`      | Model 3 | shows rooms/spaces (names, numbers, walls) |
| `quantity_takeoff` | Model 4 | usable for measuring (SF/LF/counts). **Does NOT require finish callouts** |
| `project_context`  | triage/scope | scope, index, total area, drawing org, revisions, relevant notes |

`useful_for: []` = not selected for the packet (still stored, not deleted).

### 3.3 Enums

- `importance`: `primary | supporting | incidental`
- `tag_confidence`: `high | medium | low`
- `measurement_readiness`: `likely_measurable | maybe_measurable | unlikely | unknown`
- `context_signals`: `scope_of_work | drawing_index | area_summary | revision_or_addendum | vendor_or_finish_reference | project_metadata | general_notes_relevant`
- `schedule_type`: `room_finish_schedule | finish_legend | door_schedule | equipment_schedule | other | null`
- `sf_method` (DERIVED): `not_applicable | stated | room_schedule_sum | dimension_math | scale_measure | manual_needed | unknown`
- `page_role`: `title_or_project_info | finish_schedule | finish_legend | finish_floor_plan | architectural_floor_plan | enlarged_flooring_plan | flooring_detail | spec_section | architectural_other | ceiling_rcp | mep | structural | civil_site | paperwork | not_relevant` (extend as needed)

### 3.4 `primary_use` — deterministic rule

```
1. measurable/scaled finish floor plan, floor plan, demo plan, or enlarged plan → quantity_takeoff
2. else finish schedule / legend / material legend / spec section / vendor list / flooring detail → finish_material
3. else page mainly shows rooms but is not a strong measuring surface → room_layout
4. else cover / title / index / scope / general project info → project_context
5. else → null
```
Tie-break (most downstream harm if missed): `quantity_takeoff > finish_material > room_layout > project_context`.
`primary_use` is **routing/tie-break only** — it does not suppress other tags.

### 3.5 Confidence semantics

`tag_confidence` is mainly for **claude/verifier** labels (flags where review is needed). On
final **`human_reviewed`** labels, `needs_review` + `evidence_text` matter more. Ordinal only.

### 3.6 Examples

Floor plan (SF-readiness facts captured, **no SF computed**):
```json
{
  "page_role": "architectural_floor_plan",
  "useful_for": ["room_layout", "quantity_takeoff"],
  "primary_use": "quantity_takeoff",
  "tag_importance": { "room_layout": "primary", "quantity_takeoff": "primary" },
  "overall_importance": "primary",
  "measurement_readiness": "likely_measurable",
  "context_signals": [],
  "observations": {
    "room_labels_present": "yes",
    "room_numbers_present": "yes",
    "finish_callouts_present": "no",
    "table_or_schedule_present": "no",
    "schedule_type": null,
    "drawing_index_present": "no",
    "area_summary_present": "no",
    "flooring_scope_mentioned": "no",
    "vendor_or_product_names_present": "no",
    "sf": {
      "written_scale_present": "yes",
      "scale_value": "1/8\"=1'-0\"",
      "scale_bar_present": "no",
      "dimension_strings_present": "yes",
      "room_schedule_with_areas": "no",
      "stated_area": null,
      "match_lines_present": "no",
      "multi_area_or_split_plan": "no",
      "vector_geometry": "present_clean",
      "flooring_subset_note": null,
      "sf_method": "scale_measure",
      "sf_confidence": "medium"
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
  "primary_use": "finish_material",
  "tag_importance": { "finish_material": "primary", "room_layout": "supporting" },
  "overall_importance": "primary",
  "context_signals": [],
  "observations": {
    "table_or_schedule_present": "yes",
    "schedule_type": "room_finish_schedule",
    "finish_callouts_present": "yes",
    "room_numbers_present": "yes",
    "room_labels_present": "yes"
  },
  "evidence_text": "Room finish schedule maps room numbers to floor/base/wall/ceiling finishes.",
  "needs_review": false, "label_source": "claude", "reviewed": false, "spec_version": "v4.0"
}
```

Title sheet (the case v3 got wrong — `stated_area` recorded, NOT summed):
```json
{
  "page_role": "title_or_project_info",
  "useful_for": ["project_context", "finish_material"],
  "primary_use": "project_context",
  "tag_importance": { "project_context": "primary", "finish_material": "supporting" },
  "overall_importance": "primary",
  "context_signals": ["scope_of_work", "drawing_index", "area_summary", "vendor_or_finish_reference"],
  "observations": {
    "drawing_index_present": "yes",
    "area_summary_present": "yes",
    "flooring_scope_mentioned": "yes",
    "vendor_or_product_names_present": "yes",
    "sf": {
      "stated_area": { "total_sf": 22577, "remodel_sf": 1366, "where": "T1 code analysis block" },
      "flooring_subset_note": "Stated total is the store; flooring is a subset (sales+processing per RC2). NOT computed.",
      "sf_method": "stated",
      "sf_confidence": "high"
    }
  },
  "evidence_text": "Title sheet: scope = NEW FLOORING in sales+processing; area 22,577 SF / 1,366 SF remodel; vendor list Parterre + Armstrong VCT; drawing index.",
  "needs_review": false, "label_source": "claude", "reviewed": false, "spec_version": "v4.0"
}
```

Dropped page (negative — stored, minimal evidence):
```json
{
  "page_role": "mep", "useful_for": [], "primary_use": null,
  "tag_importance": {}, "overall_importance": "incidental", "context_signals": [],
  "evidence_text": "Mechanical duct plan; no finish, room, context, or quantity value.",
  "needs_review": false, "label_source": "claude", "reviewed": false, "spec_version": "v4.0"
}
```

---

## 4. Document object (first-class)

Per document: `doc_id`, `filename`, `document_category` (architectural_plan_set | spec /
project_manual | agency_review_or_report | permit_or_application | contract_or_other),
`disposition` (`process | raw_only | duplicate_or_superseded`), `primary_reason_code`,
`reason_text`, `needs_review`, `label_source`, `reviewed`, `spec_version`.

---

## 5. Project object (no learned decision)

```json
{
  "permit_number": "24-04531-RNVN",
  "category": "retail",
  "project_profile": {
    "project_type": "retail",
    "has_finish_material_pages": true, "has_room_layout_pages": true,
    "has_quantity_takeoff_pages": true, "has_project_context_pages": true,
    "finish_schedule_location": "main_arch_set", "spec_location": "main_arch_set",
    "representation_mix": { "digital_text_vector": 4, "vectorized_text": 0, "scanned": 0 }
  },
  "sf_readiness": {
    "status": "provisional_from_page_observations",
    "best_method": "stated",
    "needs_human_ruler": false
  },
  "bid_filter_result": {
    "ruleset": "elite_commercial_v1", "decision": "passes_filter",
    "reason": "Commercial retail with architectural plans + finish schedule."
  },
  "reviewer_note": "", "needs_review": false,
  "label_source": "claude", "reviewed": false, "spec_version": "v4.0"
}
```
- `category` = descriptive tag, **never a gate.**
- `project_profile` + `sf_readiness` = **derived** from page observations; never hand-labeled.
  `sf_readiness.status` is always `provisional_from_page_observations` — it is **not** a
  takeoff result.
- `bid_filter_result` = optional, app-layer, swappable; not learned, not ground truth.
- v3 `decision` (keep/disqualify) is **removed as a target**; human judgment → `reviewer_note`.

---

## 6. Labeling rules

1. **Every page gets a row** — including obvious negatives (`useful_for: []`).
2. **Evidence depth scales with value.** Keeps get specific `evidence_text`; obvious drops get one line.
3. **Redundancy is allowed** (title sheet → `finish_material` tag AND `project_context` +
   `context_signals: [vendor_or_finish_reference]`).
4. **Observations are capture, not extraction** (the guardrail). Allowed: record a directly
   *stated* area, a printed scale, visible dimensions, schedule type, room/finish presence — all
   as `yes/no/unclear` or a literal printed value. **Forbidden during bootstrap:** sum rooms,
   decide the flooring subset, compute totals, trace polygons, verify scale/dimensions.
5. **Capture only as a byproduct.** If a fact needs opening extra pages or measuring, defer it.
6. **Only `human_reviewed` v4.0 labels are ground truth.**

---

## 7. Dataset / selection policy

- **Select for coverage** across the four tags AND representation types (digital / vectorized-text
  / scanned), bundle conditions, difficulty, and size. (Full rubric in
  `project-selection-and-prep.md`.) Simple residential / small commercial earn their place on
  `quantity_takeoff` value alone.
- **Page-level negatives are intrinsic** — do not source whole "reject projects" for training.
- **Keep ~5–10% hard-negative *projects* in the benchmark only** (paperwork-only, sign, facade).

---

## 8. Observation capture (future-proofing) — capture ONLY, never compute

**Why:** Models 2–4 will be redesigned; we capture **durable facts** now and re-derive later
instead of re-opening PDFs. Capture is byproduct-only and **never crosses into extraction**
(the guardrail at the top).

### 8.1 Durable no-regret set (capture now, robust to how 2–4 evolve)
1. **Full ingestion per page** — text + **vectors** + image + coordinate transform. Vectors are
   resolution-independent geometry → no future re-render for measurement. *(Runtime note: store
   text + a thumbnail for every page; high-res/crops on demand only. Runtime perf is deferred.)*
2. **Provenance** — permit → doc_id → pdf_page_number → S3 key on every row.
3. **Observations, not interpretations** — facts visible on the page; never a pipeline decision.
4. **Dedup / superseded** marking at the document level.
5. **Immutability + version coexistence** — re-derive across schema changes; never re-collect.

### 8.2 SF difficulty ladder (conceptual context — `sf_method` is DERIVED, not labeled)
| `sf_method` | condition | who/when |
|-------------|-----------|----------|
| `not_applicable` | MEP, spec, legend, RCP, paperwork — no SF meaning | — |
| `stated` | a numeric area is printed | record it now; reading only |
| `room_schedule_sum` | room schedule has per-room areas | **future/possible** — not executed in bootstrap unless trivially obvious |
| `dimension_math` | dimension strings on the plan | Model 4 |
| `scale_measure` | scaled plan, no stated area/dims ("needs a ruler") | Model 4: code measures vectors × scale; human confirms scale |
| `manual_needed` | no scale/dims, scanned | Model 4: human calibrates |
| `unknown` | image/text unclear | flag |

### 8.3 The `observations` object (optional, `yes/no/unclear`, fill-when-obvious)
General (Models 2 & 3 + context): `room_labels_present`, `room_numbers_present`,
`finish_callouts_present`, `table_or_schedule_present`, `schedule_type`, `drawing_index_present`,
`area_summary_present`, `flooring_scope_mentioned`, `vendor_or_product_names_present`.

`observations.sf` (Model 4 readiness — **facts only**): `written_scale_present`, `scale_value`
(literal printed value or null), `scale_bar_present`, `dimension_strings_present`,
`room_schedule_with_areas`, `stated_area` (printed number + where, or null — **never a computed
subtotal**), `match_lines_present`, `multi_area_or_split_plan`, `vector_geometry`
(present_clean | present_dense | absent — derived), `flooring_subset_note` (free text noting a
subset *exists*, never the math), plus DERIVED `sf_method`, `sf_confidence`.

**Derived from ingestion (not labeled):** `scanned_or_low_text`, `vectorized_text_suspected`
(from `extract.py` representation type + vector/text counts + weird-char ratio).

### 8.4 Project rollups (DERIVED, post-labeling — not part of hand labeling)
- `sf_readiness` (provisional; §5) — best method + needs_human_ruler, marked provisional.
- **Content census** — derived analytics after the 5 (or 25): how many have finish schedules,
  where specs live, how many scanned, how many have usable scale, how many state areas. Good
  analytics; it must not slow per-page labeling.

### 8.5 The architecture bet
- **LLM = read + understand + route** (pull stated areas, identify room polygons, find scale, pick the rung).
- **Code = the measurement math** (vectors × scale). The LLM never eyeballs pixel lengths.
- **Human = the residual** (confirm scale, fix a mis-traced room, handle scanned).
The only thing this requires **now** is that observations + vectors are captured.

### 8.6 The bounded "now" win (trimmed per scope guardrail)
**Capture obvious SF-readiness observations.** A directly **stated** area may be recorded if
visible (`stated_area`). **Do not compute takeoff totals during the Model-1 bootstrap** — no
room summing, no flooring-subset math, no polygon tracing, no scale verification.

### 8.7 What NOT to do now
No SF calculation/summing, no polygon tracing, no Model 2/3/4 build, no runtime perf work.
Capture readiness facts + keep vectors. Routing and measuring come with Model 4.

---

## 9. Storage & migration

- **Lean JSONB.** v4 label = one JSONB document (new v4 table/column); enums/shape enforced in
  **code** (a JSON schema/validator), not DB columns.
- **Coexist, never overwrite.** v3 labels remain history; v4.0 written alongside (`spec_version`
  + `label_source` distinguish). Migration **005** adds the v4 JSONB store, non-destructive.

---

## 10. Bootstrap execution plan (after lock)

1. Lock this doc → write `V1_SPEC.md` v4.0 + update `V1_RUNBOOK.md` + one `DECISION_LOG` entry.
2. Migration 005 (v4 JSONB label store), non-destructive.
3. **Re-tag the 5** under v4.0 (new labels; v3 untouched), capturing `observations` byproduct-only.
4. **Label every page** in the 5 — incl. obvious negatives; **label `25-26809`** (residential) fully.
5. **Capture obvious stated area / scale / dimensions if visible. Do NOT compute flooring SF.**
6. **No review-UI rebuild yet** — review via JSON + minimal correction.
7. Human-review → adjust spec if needed → **then decide before going to 25.**

---

## 11. Explicitly NOT doing yet

- No trained Model 2/3/4; **no SF calculation / summing / polygon tracing.**
- No polished review UI (minimal correction path for the 5).
- No per-field DB columns (JSONB until the schema stops moving).
- No `bid_filter_result` logic beyond a demo stub.
- No runtime perf optimization.
- No scaling past the 5 until human review clears it.

---

## 12. Resolved decisions (both review rounds)

1. `primary_use` routing-only; combined sheets keep all tags at their own importance.
2. `overall_importance`, `project_profile`, `sf_readiness`, `sf_method`/`sf_confidence`,
   `scanned_or_low_text`, `vectorized_text_suspected` = **derived**, never hand-labeled.
3. `tag_confidence` ordinal (`high/med/low`), not floats.
4. `measurement_readiness` = 4 values (adds `maybe_measurable`).
5. `sf_method` enum adds `not_applicable` + `unknown`.
6. `observations` = lightweight, optional, `yes/no/unclear`, fill-when-obvious; `schedule_type`,
   `match_lines_present`, `multi_area_or_split_plan` included.
7. `stated_area` and `scale_value` capture the **literal printed value** (not booleans) so we
   never re-open the page — but a stated area is the **only** SF number recorded, and only when
   directly printed.
8. `sf_readiness.status` always `provisional_from_page_observations`; content census is derived
   post-labeling, not part of per-page labeling.
9. **Scope guardrail (top of doc):** §8 is observation capture, not extraction; **no SF
   computation during the bootstrap.**
10. Storage = JSONB + code-side validation; v3 coexists; review the 5 via JSON, not a polished UI.
