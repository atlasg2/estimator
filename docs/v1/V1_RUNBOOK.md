# V1 Runbook — how we label one project (v4.0)

The exact bootstrap process for **Model 1 — Page Purpose Classifier** (`spec_version v4.0`).
Living doc — edit in place + log changes in `DECISION_LOG.md`. See `V1_SPEC.md` for the schema and
the **scope guardrail** (observations are capture, not extraction — no SF computation).

## Mode (bootstrap)
**Full multimodal, one project at a time, no fan-out.** Review each page with extracted text **and**
the visual page. Text-only only if the image is genuinely unavailable.

## Per-project steps
1. **Evidence packet** — assemble: permit metadata, candidate id, permit number, project name,
   address (if any), document list with DocIDs + filenames + page counts, per-page text, sheet
   number/title (if any), and visual page access for **every** page (not just keeps).
2. **Claude labels the project (v4.0)** — produce strict JSON:
   - **Page rows for EVERY page** of each `process` document — incl. obvious negatives
     (`useful_for: []`). Set `useful_for` + per-tag `tag_importance` (the source of truth — a page
     can be `primary` for several jobs). `primary_uses`/`display_primary_use` are derived (§3.4),
     not chosen. Add `context_signals` for context pages, `measurement_readiness` for
     `quantity_takeoff` pages.
   - **`observations`** filled byproduct-only (`yes/no/unclear`); record a directly **stated**
     area / printed **scale value** if visible. **Never** sum rooms, compute SF, or trace polygons.
   - **Document rows** with `disposition` + `document_category` (dedup/superseded marked).
   - Derived fields (`overall_importance`, `sf_method`, `project_profile`, `sf_readiness`) are
     **computed**, not subjectively chosen.
   - A readable project explanation + an issues/confusions list.
3. **Contradiction checker** — run the deterministic flags (see `V1_SPEC.md §10`): empty
   `useful_for` but flooring text; `quantity_takeoff` without `measurement_readiness`;
   door/equipment `schedule_type` tagged `finish_material`; `raw_only`/superseded doc that looks
   architectural; high confidence + weak evidence; thin text but plan-like image.
4. **Human review** — correct issues. Watch for: missed finish schedules / legends / finish floor
   plans / flooring specs; docs wrongly `raw_only`/superseded; pages wrongly `useful_for: []`;
   wrong `schedule_type`.
5. **Save** — store separately: Claude initial (`label_source=claude, reviewed=false`) and
   human-corrected (`label_source=human_reviewed, reviewed=true`), plus contradiction flags and
   the issues list. For the bootstrap 5: **local JSON** is the working store + review path; write
   to RDS via the **v4 JSONB store** (migration 005) once DB access is confirmed. **Never overwrite
   v3 labels** — v4.0 coexists.

## After all 5 — bootstrap review report
Summarize: `useful_for` tag distribution; `tag_importance`/`primary_uses` distribution; did Claude
miss any finish schedules / legends / floor plans?; did multi-primary combined sheets label right?; were
the observations cheap + useful?; representation mix (digital/vectorized/scanned); derived
`sf_readiness` sanity; which pages were hard; what should change before the 25.
Then choose: **A.** v4.0 good → continue to 25 · **B.** small changes → v4.1, re-tag the 5 if needed
· **C.** major confusion → revise process and rerun the bootstrap.

## Do not (until after the bootstrap)
Don't train; don't run all 112; don't multi-agent label; **don't compute square footage / sum
rooms / trace polygons**; don't build Model 2/3/4; don't rebuild the review UI; don't use page
labels to skip extraction; don't delete/overwrite raw PDFs, raw Claude labels, or v3 labels.
