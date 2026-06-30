# Project selection + future-proofing prep (for next consultation)

**Status:** DRAFT for the next human + GPT consultation. No code/spec changes implied.
**Date:** 2026-06-29
**Reads with:** `page-purpose-v4.0-final.md` (the locked-ish schema), `page-purpose-rescope.md`.
**Purpose:** decide **which projects to label next** (moving from 5 → ~25), choosing them so we
(a) build the best Model 1 (Page Purpose Classifier) training set, AND (b) seed Models 2–4 with
cheap prep now so we don't re-source or re-ingest later. Written to be read cold by GPT.

---

## 0. The objective (two goals at once)

1. **Model 1 robustness now.** Page-purpose classification + ranking must work across the real
   variety of permit bundles — not just clean retail plan sets.
2. **Future leverage.** Every project we touch should also drop breadcrumbs for Models 2
   (finish extraction), 3 (room assignment), 4 (quantity/SF) — *as a byproduct*, never as a
   dedicated extra pass.

Guiding tension: **coverage vs. labeling velocity.** We want ~25 well-chosen projects, not 5
perfect ones and not 50 sloppy ones. Selection should buy maximum learning per labeled page.

---

## 1. Selection rubric — the coverage axes

We propose choosing projects to span these axes (not one project per axis — each project hits
several):

**A. Downstream-tag coverage** (the four `useful_for` tags). Make sure we have many examples of
each, especially the ones the old schema under-collected:
- `finish_material`: finish schedules in *different formats* (matrix table vs. list vs.
  callouts), finish/material legends, spec sections, vendor/product lists.
- `room_layout`: floor plans with room names/numbers.
- `quantity_takeoff`: **clean, dimensioned plans with a stated scale** — deliberately include
  *simple* projects (residential, small commercial) for this; they're the best SF learners.
- `project_context`: varied title sheets (scope / index / area summary / vendor refs).

**B. Project-type diversity** (data diversity, NOT a bid gate): retail, restaurant,
fitness/assembly, office/medical, residential, mixed-use. Don't over-index on retail.

**C. Page-representation diversity** (the DPI/vector axis — see Appendix A of the rescope doc).
Force-include all three production types so Model 1 is robust to *how the PDF was made*:
- clean **digital text-layer** sets (easy),
- **vectorized-text** sets (text is outlined → near-empty text layer, must vision-read),
- **scanned / no-text** sets (OCR path).
If every training project is clean-digital, Model 1 will fail on scanned permits in the wild.

**D. Bundle-condition diversity:** clean single plan set vs. **messy multi-doc bundles with
duplicates / superseded sets** (tests dedup + `disposition`) vs. paperwork-heavy bundles.

**E. Difficulty / hard cases** (so the model learns the boundary, not just easy keeps):
- easy keeps (obvious finish schedule),
- **hard near-misses inside keeps:** existing-shell with **no new flooring** (the v2 over-call),
  ceiling RCP that resembles a floor plan, door/hardware schedule that resembles a finish
  schedule, a finish page whose *sheet name* hides its content (the TJ Maxx RC2 miss).

**F. Size distribution:** small (≤5 pp) through large (25+ pp), so ranking/selection works at
both scales.

**G. Hard-negative *projects*** (benchmark only, ~5–10%): paperwork-only bundles, sign permits,
facade-only jobs — to verify ingestion yields a correctly **empty** packet. These test the
*system*, they don't train the model.

---

## 2. Candidate pool (to attach)

We have a pool of already-discovered NOLA permits, ~25 already extracted into evidence bundles,
plus a larger availability list. **The concrete permit-by-permit inventory (permit #, type,
size, representation, bundle condition) should be attached to this doc before the consultation**
so we pick against real options, not abstractions. The 5 already labeled
(`24-21892`, `25-02683`, `24-04531`, `25-16244`, `25-26809`) get re-tagged under v4.0 and count
toward coverage.

---

## 3. The "do it now, cheap" prep list (future-proofing)

**Principle:** capture a future-model signal **only if it's a byproduct of work we're already
doing for Model 1**, or it's a one-time ingestion setting. No dedicated Model 2/3/4 labeling now.

| # | Do now | Saves later (which model) | Cost |
|---|--------|---------------------------|------|
| 1 | **Full ingestion per page**: store text + **vectors** + rendered image + coordinate transform for every selected project (not just the cheap labeling text). | Models 3 & 4 reuse the vector geometry directly → **no re-ingest**. | one-time compute |
| 2 | Because **vectors are resolution-independent** (geometry in PDF points), we do **not** need to re-render plans at high DPI later for measurement. Storing vectors now removes a future re-render pass. | Model 4 | free (consequence of #1) |
| 3 | **Capture scale when it's in front of you** (`measurement_readiness` + optional `measurement_basis`). You're reading the title block for Model 1 anyway. | Model 4 | ~free |
| 4 | **Jot finish codes/materials actually seen** (LVT, VCT, ceramic, cove base, rubber base, carpet tile, sealed concrete, transitions…) into a growing controlled vocabulary. You're reading the finish schedule anyway for the `finish_material` tag. | Model 2 (few-shot + normalization) | ~free |
| 5 | **Note room-tagging presence** — does the plan have room names/numbers / a room schedule? | Model 3 | ~free |
| 6 | **Lock provenance IDs** on every page: permit → doc_id → pdf_page_number → S3 key. | all models (traceability) | mostly done |
| 7 | **Mark duplicate / superseded documents** (`disposition`) so future extraction never reads a stale set. | Models 2–4 | already in schema |
| 8 | **Immutable raw + coexisting labels** (raw PDFs + raw labels never overwritten; v3/v4 coexist). | everything | already a rule |

**Velocity guardrail:** the test for any prep item is *"am I already looking at this to do
Model-1 labeling?"* If yes, capture it. If it needs opening extra pages or *proving* scale,
**defer** it to that model's own labeling pass.

---

## 4. Strategy question: all-at-once vs. waves

We just made a **major schema pivot at project #5** (v3 → v4.0). Labeling 25 projects in one
shot risks baking a v4.0 mistake into all 25. Proposed: **label in waves** — e.g. re-tag the 5 →
add ~5 more spanning the rubric → human review → adjust → then the remaining ~15. Open for
debate; the cost is slower ramp, the benefit is not re-labeling 25.

---

## 5. Questions for GPT (project-selection round)

1. Is the coverage rubric (A–G) the right set of axes — anything missing or redundant?
2. For ~25 projects, propose a **target composition**: how many per project-type (B), per
   representation type (C), per difficulty band (E), per size band (F)?
3. **Representation diversity (C):** how many *scanned* and *vectorized-text* projects should we
   force-include so Model 1 is robust, without overweighting rare cases?
4. **Hard near-misses (E):** which archetypes are most valuable to include first —
   existing-shell-no-new-flooring, RCP-looks-like-floor-plan,
   door-schedule-looks-like-finish-schedule, or name-mislabeled finish page?
5. **Future-proofing (§3):** is "capture only byproduct signals, defer dedicated work" the right
   line? Any item we should *promote* to required-now (e.g. always store vectors), or any we're
   over-doing this early?
6. **Waves vs. all-at-once (§4):** given the fresh schema, how big should the next wave be
   before a human-review checkpoint?
7. **Benchmark hard-negatives (G):** how many projects, and which archetypes, for the
   empty-packet test?
8. Anything we should do **now** for Models 2–4 that isn't on the §3 list but is similarly cheap
   and high-leverage?
