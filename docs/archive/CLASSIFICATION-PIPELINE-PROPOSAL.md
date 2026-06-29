# Proposal v2: Classification + Extraction Pipeline (for review)

_Builds on SYSTEM-AUDIT.md. For external review (ChatGPT). v2 — deeper. 2026-06-27._

## Context / goal
NOLA permits → a **labeled, fully-extracted plan-page dataset** for **commercial flooring
takeoff** (customer = commercial / fitness / retail flooring installer). This document
designs the step between "we have the documents" and "we have clean, labeled page data,"
and it tries to be honest about *where an AI classifier will be wrong and how we contain
that*.

## Where we are
- **112 candidates discovered** (each permit's doc list + DocIDs in a `candidates` table),
  via a multi-IP crawl — the portal rate-limits discovery to **~12/IP**, so ~10 cheap EC2
  boxes in parallel did 112 in ~5 min.
- **Optimized extraction worker on EC2** (in-region): page image + text JSON + vector JSON
  (PDF coords only, gzipped), `--workers` parallelism, ~3s/page (was ~37s).
- Raw PDFs always kept (source of truth).

---

## 1. Design principles (the trust foundation — deepened)

1. **Labels, not filters.** The classifier's page labels never *drop* a page. We extract
   every page of every document we process; labels are metadata. A wrong label = a
   re-label, not a lost floor plan.
2. **Everything reversible.** Projects are *soft*-deleted (status flag, raw kept).
   Classification is stored in a **separate, versioned table**, re-runnable without
   re-extracting. We can improve the classifier and re-label the whole corpus for free.
3. **Every decision carries its evidence + a confidence.** No bare verdicts. A page label
   records *what text/image it was based on* and *how sure it is* — so any decision is
   auditable after the fact, and low-confidence ones can be routed for review.
4. **Extract text from ALL documents, not just the ones we'll "process."** Text is
   nearly free. Doing it for every doc means the *document-disposition* decision is itself
   auditable, and a doc we wrongly marked `raw_only` is catchable later from data we already
   have — no re-download, no re-guess. (This is the doc-level version of principle #1.)

These four turn "trust the AI" into "the AI proposes, everything is evidenced, reversible,
and measured."

---

## 2. The classification, done cleverly (the part that was missing)

A blind page-by-page "what is this sheet" is weak. Two structural ideas make it reliable:

### 2a. Index-driven backbone
Architectural sets almost always have a **cover / sheet index** listing every sheet
(`G000`, `A101`, `A201`, `A600 FINISH SCHEDULE`…). The classifier **reads the index first**
to get the *authoritative* sheet list, then maps each actual page to a sheet and
**reconciles**: which indexed sheets are present, which pages are unlisted, where the floor
plans and finish schedule *should* be. This is far more reliable than classifying pages in
isolation, and it **surfaces problems** (missing sheets, mis-ordered, a "combined" file that
merges disciplines).

### 2b. Tiered evidence / confidence escalation (cheap → expensive, only as needed)
- **Tier 1 — page text.** Most sheets carry their number+title in the text (`A201 FIRST
  FLOOR PLAN`). Cheap, high-confidence for the majority.
- **Tier 2 — render + vision.** Only for pages with thin/garbled text, or where the text
  label and the index disagree. The agent *looks*.
- **Tier 3 — human spot-check.** Only for low-confidence or verifier-flagged pages.
- Each page stores the **tier used + confidence**, so we know exactly how much we trusted
  each label and can audit the cheap ones.

### 2c. Right granularity for disposition
Disposition is **per-document by default, but per-page inside "combined" PDFs.** A
`939 Girod_Combined.pdf` that bundles arch + MEP + civil must not be marked `raw_only` (or
blindly all-`process`) as a unit — the index reconciliation tells us which *page ranges* are
architectural.

### 2d. Real-world messes it must handle (named, not hand-waved)
- **Revised/superseded sets** (`Rev 1`, `Rev 2`, dated): process the **latest**, record the
  superseded ones as `raw_only` with a `superseded_by` note — don't extract stale plans as
  if current.
- **Scanned/raster plan sets** (no text layer): vision path, **flagged `scanned`** (needs
  OCR later) — never silently mishandled.
- **Vectorized/outlined text** (CAD exports where labels are vector outlines, so `get_text`
  returns nothing on a real plan): caught because the index says floor plans exist but text
  is empty → escalate to vision.
- **Huge docs** (100+ pages): chunk the text bundle for the agent; classify in ranges.

---

## 3. The three decisions (each with evidence + confidence + reversibility)

| Decision | Values | Evidence recorded | Reversible |
|---|---|---|---|
| **Project** | keep / delete | description + which plan docs found | soft-delete, raw kept |
| **Document disposition** | process / raw_only (+ per-page for combined) | filename + actual content read | re-disposable from kept text |
| **Page label** | type + `flooring_relevant` + sheet # | text and/or image used, tier, confidence | versioned `page_labels` table |

"`process`" = architectural **plans**, **specs**, **project manual**. "`flooring_relevant`"
is **not** just "is a floor plan" — see §5.

---

## 4. Verification — adversarial and measured (this was the weakest part before)

Three layers, because "the model is probably right" is not a QA strategy:

1. **Deterministic cross-checks.** A page labeled "not flooring" whose text contains
   `FINISH SCHEDULE`; a "floor plan" with no plan-like text/room names; a kept project whose
   index lists no `A`-series sheets. These are cheap contradiction detectors that run on
   every page.
2. **An adversarial verifier subagent.** A *second* agent whose job is to **refute** the
   first: "find a floor plan or finish schedule that was mislabeled; find a `process` doc
   marked `raw_only`; find a kept project with no usable plans." Adversarial review catches
   misses that a confirming pass never would.
3. **A gold set + measured accuracy.** We already hand-did **231 Carondelet** and **Crunch**
   and can hand-label ~5 more. Run the classifier on those, compute **precision/recall** on
   "is this page a floor plan / finish schedule" and on the keep/delete call. That's a real
   accuracy *number*, not a vibe — and it's the gate before we'd ever trust surgical
   extraction.

Low-confidence + verifier-flagged pages go to a **human-review queue**; corrections become
gold-set data (active learning).

---

## 5. What "flooring-relevant" actually means (sharper taxonomy)

Relevance ≠ "is a floor plan." For a flooring takeoff:
- **Primary:** floor plans, **room finish schedule**, finish legend, finish/floor plans,
  enlarged plans (restrooms, etc. — they carry tile).
- **Secondary:** floor-transition & base details, sometimes RCP (room boundaries), demo
  plans (existing-to-remain vs new).
- **Type signals worth capturing:** rubber / sport surfaces (fitness — Elite's niche),
  tile / LVT / carpet / VCT codes. A *detail* sheet can be flooring-relevant even though
  it's not a "floor plan."

The label schema should carry `type` (the sheet kind) **and** `flooring_relevant` (does it
carry flooring info) as **separate** fields — they're not the same axis.

---

## 6. Architecture (Claude Code, on the Max plan — refined)

- **Scripts (hands):** `prep_candidate.py` (download all docs + extract per-page text for
  *all* of them); a small `reconcile_index` helper.
- **Subagents (brains):** `project-classifier` (index-driven, tiered, returns the three
  decisions + evidence + confidence) and `classification-verifier` (adversarial).
- **Worker (existing):** `run_ingestion.py` — full extraction of `process` docs/pages.
- **Workflow `classify-and-extract`:** `prep → classify → verify → extract`, fanned over
  112 in parallel; writes a **versioned `page_labels` table** + a **review queue**; records
  **timing + tokens per stage**.
- **Skill `/build-dataset`** — optional trigger.

Principle: **deterministic → scripts, judgment → subagents, adversarial check → second
subagent, orchestration → workflow, persistence → versioned tables.**

---

## 7. Cost / scale model (real estimates, not "cheap")

- **Classify per project:** text bundle for a ~40-sheet set ≈ 10–20k input tokens; a few
  vision pages ≈ 2–5k; structured output ≈ 2–3k → **~25–35k tokens/project**.
- **Verify per project:** ~10–15k tokens.
- **112 projects:** ~5M tokens total — trivial on the Max plan; wall-time bounded by the
  workflow's parallelism (~16 concurrent), so ~minutes, not hours.
- **Thousands:** scales linearly (~50M tokens/1k projects) — still Max-plan-feasible; the
  real cost is *extraction* compute, which the page disposition already minimizes (we only
  fully-extract the architectural docs of kept projects).

---

## 8. Open questions for ChatGPT
1. **Extract-full vs surgical:** agree we extract all pages of `process` docs now (labels
   not filter), and only go surgical once §4 accuracy is *measured*? What precision/recall
   bar would justify surgical?
2. **Index-driven backbone:** is reconciling against the sheet index the right primary
   strategy, or over-engineered vs. plain per-page classification?
3. **Disposition scope for v1:** architectural drawings only, or also extract specs /
   project manuals (text-heavy, carry finish callouts)?
4. **Adversarial verifier:** one verifier, or N independent refuters with a majority vote?
   Where does human review enter?
5. **Schema/versioning:** separate `page_labels` table (versioned, re-runnable) — agree?
   What belongs on it (type, flooring_relevant, sheet#, evidence, tier, confidence,
   model_version)?
6. **Anything missing** before scaling 112 → thousands?
