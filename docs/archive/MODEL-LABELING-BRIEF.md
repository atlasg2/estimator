# Labeling → Model Training — Alignment Brief

*Sanity-check / confirmation request. We're at the **labeling** step, whose only purpose is
to produce **training data for a model we will train and deploy**. Below is the goal, the
label parameters that follow from it, where we are, and the plan our coding agent (Claude)
proposes. Please confirm or push back before we build out tooling.*

---

## The end goal — the model (this is settled, not up for debate)

We are building a **trained ML model**, deployed on a **serverless pod** for cheap, fast,
high-volume inference. It is **NOT** an LLM reading pages at runtime — at hundreds of
thousands of plan pages per day that is too expensive, too slow, and not trustworthy enough.
The LLM's role is **offline only**: to help build the labeled training set.

What the model does in production:
- Ingest many construction-permit projects per day (potentially hundreds of thousands of
  plan pages).
- **Triage each project** → keep or **disqualify**, with a **human-readable reason**.
  "Fit" = relevant to a **commercial flooring takeoff** (customer: Elite Installation —
  commercial / fitness / retail flooring installer).
- For kept projects, **select the pages that matter** (floor plans, finish schedules,
  flooring details) and **discard the rest**.
- Be explainable/documented so humans trust the keep/disqualify calls.

## Why we're labeling

To train that model we need a **large, clean, human-verified labeled dataset** of real
permit projects, labeled exactly how we want the model to behave. **Claude orchestrates a
team of Claude agents** that read each page's cheap extracted text (plus the page image when
text is ambiguous) and apply our label parameters. **Humans then verify/correct** the agents'
labels — the corrected version is the trusted training data.

## The label parameters (what the model learns to output)

Three levels per project:
1. **Project:** `keep` / `disqualify` / `unknown` — with a reason.
2. **Document:** `process` (worth extracting) / `raw_only` (keep but skip).
3. **Page** (of process docs):
   - `usefulness`: critical / useful / maybe / not_flooring
   - `role`: finish_floor_plan / finish_schedule / spec / flooring_detail / title / notes /
     architectural_other / …
   - `flooring_relevant`: yes / no
   - plus `confidence` + a one-line `evidence` ("why")

## Where we are

- **Pipeline proven:** discover NOLA permits → pull each permit's document list → cheap
  per-page text prep → Claude agents label (project/doc/page) → store to Postgres →
  (separately) full page extraction (image + text JSON + vector JSON) to S3 for kept projects.
- **Working in gates:** 5 → 25 → 50 projects.
- **48 projects labeled:** 25 under prompt **v1**, 23 under prompt **v2** (we rewrote the
  prompt after noticing v1 problems). Every label is version-stamped in the DB.
- **Human review just started.** Findings so far (2 projects, eyes on every needed page):
  - **v1 under-calls** the important pages — e.g. a TJ Maxx **finish schedule** (the page
    that lists flooring material per room) was labeled `not_flooring`. A **true miss** — the
    dangerous kind, because the model would learn to throw that page away.
  - **v2 over-calls** critical (marks borderline pages critical) — the **safe** direction;
    nothing is lost, humans just trim the extras.

## The plan Claude proposes (please confirm / critique)

1. **Treat v1 + v2 labels as "old"** — useful for learning, not trusted training data. Lock
   down a final **parameter spec** before mass labeling.
2. **Claude agents re-label a full batch** fresh against the final spec, so we have one
   consistent version.
3. **Humans verify a subset into a small "gold set"** (every needed page checked) — used to
   (a) measure labeler accuracy and (b) anchor the parameters.
4. **Measure + tune** the prompt/parameters against the gold set (A/B competing versions,
   scored on the same gold set) until accuracy is high enough.
5. **Scale** the winning version across all projects → that becomes the training set.
6. **Only then** harden the reusable **agents / skills / workflows** for running it at scale
   (don't build tooling around a spec that's still moving).

## What we'd like you (ChatGPT) to confirm

1. Is "build a human-verified labeled dataset, then train a deployable model" the right shape
   for this goal — anything missing or out of order?
2. Is the **3-level label schema** above the right set of parameters to train a
   triage-then-page-selection model, or should we add/drop fields?
3. For the eventual **serverless model**: given the inputs are page **text + simple geometry
   features (vector/line counts, sheet number) + optionally the image**, what model
   type/architecture fits best? (e.g. gradient-boosted feature classifier on text+geometry, a
   small fine-tuned transformer on page text, a two-stage project-then-page design, image
   model, or a combo?) And does the **per-decision "reason"** come from the model, or a
   separate explanation step?
4. How large should the **verified gold set** and the **full training set** be before a first
   model is worth training?
5. Anything about the **gate plan (5→25→50)** or the **"retire v1/v2, relabel clean"** call
   you'd change?
