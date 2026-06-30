# Proposal: re-scope V1 from "company triage" to a "page-purpose" model

**Status:** DRAFT for external review (not yet applied to `V1_SPEC.md`)
**Date:** 2026-06-29
**Author:** working session (human + Claude)
**Purpose of this doc:** capture the full proposal + reasoning so it can be shared with a
second reviewer (GPT) for a sanity check *before* we change the canonical spec. It is written
to be read cold — no repo access required.

---

## 0. What this project is (context for a cold reader)

We are building a near-automated **commercial-flooring estimating tool**. Input: a permit's
document bundle (a set of PDFs — architectural plan sets, specs, agency paperwork, etc.).
Goal: get from raw permit PDFs → a flooring estimate (what finishes, what product, how much
area), with a human approving along the way.

The intended customer for the *demo* is one flooring contractor ("Elite" — commercial /
fitness / retail). **Important caveat that drives this proposal: the company does not yet know
this is being built.** The builder wants (a) something impressive to show them, and (b)
something that still has standalone value if Elite passes. That means we should avoid baking
one company's private business rules into the core asset.

### The intended model/system roadmap (4 stages)
1. **Model 1 — find the right pages.** Per page, decide whether it matters for a flooring
   takeoff and why. Runs on every page of every project → must be **cheap/serverless, not an
   LLM at runtime**. *This is the only stage that clearly needs a trained model.*
2. **Model 2 — extract flooring finishes/specs** from the pages Model 1 keeps (finish codes,
   material type, manufacturer, product/style/color, base, notes, source page, evidence).
   Likely **rules + table parsing + LLM extraction + human review**, *not* a trained model at
   first (maybe ever).
3. **Model 3 — assign finishes to rooms/areas** (read finish floor plans).
4. **Model 4 — square footage / polygons** (measure areas off dimensioned plans).

Stages 2–4 run only on the handful of pages Model 1 keeps, so per-project LLM cost is bounded.

### Current state
- We are in the **labeling stage** of Model 1, bootstrapping with **5 hand-labeled projects**.
- Only **human-reviewed** labels count as ground truth. We have not yet human-reviewed.
- We have a working **ingestion pipeline** (PyMuPDF) that, per page, extracts: the **text
  layer**, the **vector/CAD linework**, and a **rendered raster image** — with a verified
  PDF-point → pixel coordinate transform. (Details in Appendix A; relevant because it's the
  foundation for Models 3 & 4.)

### The current Model-1 label schema (what we want to change)
- **Project level:** `decision` = `keep` | `disqualify` (i.e. "is this worth bidding *for
  Elite*?"), plus `category` (retail / restaurant / fitness / residential / …).
- **Page level:** `page_usefulness` = a 4-value ladder `not_flooring` | `maybe_flooring` |
  `useful_flooring` | `critical_flooring`; plus `flooring_relevant` = `yes` | `no` | `maybe`;
  plus `page_role` (title, finish_schedule, floor_plan, rcp, mep, …); plus `confidence`.

---

## 1. The core problem we found

The schema conflates things that should be separate, and it bakes in a company-specific
decision we cannot actually train. Three concrete symptoms:

### Problem A — project-level "keep/disqualify for Elite" is the wrong target
- It answers a **business-policy** question (does *Elite* bid residential? what size? what
  geography?), not a **document** question. It's the least transferable, hardest-to-label part.
- **We have no ground truth for it** — only Elite knows their real bid/no-bid history.
- It's one bit per project → very low signal per unit of labeling effort.
- It actively **destroys useful data.** Example: we marked a residential project
  (`25-26809`) `disqualify` and labeled **0 of its pages** — even though residential plans
  are often the *easiest, cleanest* examples for the square-footage model (Model 4). The Elite
  filter and the data-collection goal are in direct conflict.

### Problem B — "not_flooring" is too blunt; it throws away keep-worthy pages
A single flooring/not-flooring axis collapses two different questions: *"is this a flooring
sheet?"* and *"is this page worth keeping?"* The title sheet is the clearest failure:

- `24-04531 / T1` (TJ Maxx title sheet) is labeled `not_flooring` → would be dropped. But it
  carries: scope-of-work that says NEW FLOORING is in scope; the building/remodel square
  footage (22,577 SF store / 1,366 SF remodel); the drawing index (tells you *which* sheets to
  open); and an approved-vendor list (Parterre flooring, Armstrong VCT — that's literally
  finish info). Any estimator keeps this page.

### Problem C — square-footage signal is invisible in the current scheme
A floor plan with **no finish callouts** is still the page you measure area from. Today it
gets buried as `maybe_flooring` or `useful_flooring`, indistinguishable from "has a little
flooring text." Examples:
- `24-21892 / A102` (Second Floor Plan), `24-21892 / D101` (Demo Plan): measurable, but no
  finish content → currently `useful_flooring`, which hides their real (SF) value.
- `25-16244 / A2.0` / `A3.0` (Existing/Proposed floor plans): `maybe`/`useful` — they're
  prime SF surfaces.

---

## 2. The proposal

**Re-frame Model 1 from "Elite triage" to a general "page-purpose classifier":** label each
page by *which downstream job it serves*, and stop encoding one company's bid rules in the
core dataset.

### Change 1 — Drop project-level keep/disqualify as a model target
- `decision` becomes a **human review note** and/or an **optional, swappable rules layer**
  ("flag commercial-only, ≥ X sqft") applied *after* the model — never a learned target.
- It can still appear in the demo as a configurable "Elite bid filter" toggle, so we keep the
  triage story without making it load-bearing.

### Change 2 — Replace the page label scheme with `useful_for` multi-tags
Replace `page_usefulness` (the 4-value ladder) **and** `flooring_relevant` (yes/no/maybe) with
a multi-label `useful_for`, drawn from a small set that maps 1:1 to the model roadmap:

| tag | feeds | example pages |
|-----|-------|---------------|
| `finish_spec`     | Model 2 | finish schedule, finish legend, spec section, vendor list, finish callouts |
| `room_layout`     | Model 3 | floor plans with room names/numbers |
| `square_footage`  | Model 4 | any **dimensioned** floor plan — *even with zero finish callouts* |
| `project_context` | triage/scope | title sheet (scope, index, SF totals), general notes |

- A page may carry **several** tags. **Empty = drop** (MEP, structural, RCP, roof, elevations,
  paperwork).
- **Keep** `page_role` (what kind of sheet it is) and `confidence`.
- "Keep this page" is then derived = *any tag set*, instead of a flat flooring/not guess.

### Change 3 — Selection rule: pick projects for *coverage*, not "best finish schedule"
When choosing the next projects to label, optimize for coverage across the four tags — not for
whichever has the densest finish schedule. Simple residential / small commercial with clean,
dimensioned plans **earn their place purely on `square_footage` value.**

### Change 4 — Negatives are intrinsic; stop sourcing whole "reject projects"
Once labels are page-level, negatives come **for free** inside every project (most pages in any
set are MEP / structural / paperwork). The earlier "~⅓ of the dataset should be reject
projects" policy was solving a project-level problem that no longer exists. The hard negatives
that matter are *pages* (a ceiling plan that looks like a floor plan; a door schedule that
looks like a finish schedule), and those are everywhere.

### Change 5 — Capture all four models' data in one labeling pass
Build the models in order (1 → 2 → 3/4), but **label for all four now.** Tagging a measurable
plan `square_footage` today costs nothing and means we never re-open projects when we build
Model 4. (Cost: slightly more work per page; benefit: one labeling pass feeds four models.)

---

## 3. Concrete before → after on the 5 labeled projects

| page | now (`page_usefulness`) | proposed `useful_for` |
|------|--------------------------|------------------------|
| `24-04531 / T1` Title | not_flooring | **`project_context` + `finish_spec`** (vendor list) |
| `24-04531 / RC1` Fixture Plan | useful_flooring | `room_layout` + `square_footage` |
| `24-04531 / RC2` Finish Schedule | critical_flooring | `finish_spec` (+`room_layout`) |
| `24-04531 / RC3` Elev/Details | useful_flooring | `finish_spec` (flooring detail) |
| `24-21892 / G000` Cover/Index | not_flooring | **`project_context`** |
| `24-21892 / A101` Floor Plan + Finish Sched | critical_flooring | `finish_spec` + `room_layout` + `square_footage` |
| `24-21892 / A102` Second Floor Plan | useful_flooring | `room_layout` + `square_footage` (no finish) |
| `24-21892 / A103` Roof, `A150` RCP, `M1xx` MEP | not_flooring | **drop** (no tags) — unchanged intent |
| `25-16244 / A2.0`/`A3.0` Floor Plans | maybe / useful | `square_footage` + `room_layout` |
| `25-26809` (residential) | `disqualify`, 0 pages labeled | **label its pages**; floor plan → `square_footage` + `room_layout` |

Note: Change 2 re-shapes **every existing label**, so the 4 done projects need a quick re-tag
pass, and `25-26809` needs labeling from scratch.

---

## 4. Why we think this is better (and the tradeoffs)

**Pros**
- Trains only what we *can* label (page purpose) and drops what we *can't* (Elite bid policy).
- Makes the asset **general** → valuable even if Elite passes; the demo gets *broader*, not
  narrower (works on any project bundle; bid filter is an optional toggle).
- Denser, cheaper labeling: many page-labels per project vs. one bit per project; one pass
  feeds all four models.
- Stops discarding SF-valuable data (residential, bare floor plans).
- Removes the need to hunt for "reject projects" — negatives are intrinsic.

**Cons / risks**
- Re-shapes the existing 5 labels (re-tag cost; small at this scale).
- `useful_for` is slightly more work per page than a single dropdown.
- We lose an explicit, demo-friendly "we triaged the whole project for you" headline unless we
  build the optional rules toggle.
- Multi-label boundaries can be fuzzy (e.g. is a fixture plan `room_layout`? is the vendor list
  really `finish_spec`?) — needs crisp definitions + examples in the spec.

---

## 5. Questions we'd like the reviewer (GPT) to weigh in on

1. Is dropping project-level keep/disqualify from the *model* the right call, given we have no
   bid/no-bid ground truth — or is there a defensible way to keep a learned triage signal?
2. Is the `useful_for` tag set right? Too few / too many? Should `project_context` be split
   (scope vs. index vs. general notes)? Should `square_footage` and `room_layout` be merged?
3. For Model 2 (finish extraction), is "rules + table parsing + LLM + human review" the right
   first approach vs. a trained extractor — and what would change that answer?
4. Is "negatives are intrinsic, don't source reject projects" sound, or do we still want some
   deliberately-chosen hard-negative *projects*?
5. Project = permit bundle as the ingestion unit, page as the labeling/training unit — is that
   the right granularity, or should documents (PDFs) be first-class somewhere?
6. Anything about the staged roadmap (1→2→3→4) you'd reorder or merge?

---

## Appendix A — ingestion / DPI / vector mechanics (feasibility context)

Per page, PyMuPDF (`fitz`) gives three layers:
1. **Text layer** (`get_text`) — actual words + bounding boxes in **PDF points**
   (resolution-independent). If present, you read schedules as exact strings — no OCR.
2. **Vector layer** (`get_drawings`) — every line/rect/curve/quad of CAD linework, also in PDF
   points. This is walls, room outlines, table grids, hatching → **the raw geometry for
   Models 3 & 4** (room polygons → square footage, via the sheet scale).
3. **Raster image** (`get_pixmap(matrix=Matrix(zoom, zoom))`) — the rendered PNG. The **only**
   layer that depends on DPI (`zoom = DPI/72`; pixels = points × zoom).

The glue is the transform `pixel = pdf_point × matrix`, verified by an overlay spike (draw text
boxes + vector lines on the rendered image and eyeball that they line up). Because text/vectors
are stored in DPI-free points, you can re-render at any DPI and the overlay still lines up.

**The DPI ↔ vector interaction (the non-obvious part):**
- If a page has a **real text layer**, DPI is irrelevant for *reading* it — read the text layer
  directly; a low-res image is fine.
- Some CAD exports convert text to **outline curves** ("vectorized text"): `get_text` returns
  almost nothing, but the **vector count explodes** (every letter becomes many curves). Then
  the *only* way to recover the words is to **rasterize at high DPI and OCR / vision-read**.
  Low DPI → too blurry to recover. We detect this (`vectors >> text_len` → flag
  `possible_vectorized_text`) and also flag `scanned_no_text` (no text layer at all → OCR).

Implication: the vector/text ratio decides whether DPI even matters for a page, and "make the
image clearer" = **re-render the same PDF at higher DPI** (no re-download / re-upload needed —
the source PDF is local; the browser zoom just enlarges existing pixels and can't add detail).

For the **vision model** specifically: the API downsamples images past ~1568px on the long
edge, so cranking DPS beyond that doesn't help Claude read a dense full sheet — better to
extract text or crop/tile the relevant block. Higher DPI mainly helps the *human* reviewer
zoom. This is why the labeling approach is text-first, vision-as-backup.
