# V1 Phase Plan

Living doc — the gates and milestones. Current phase is mirrored in `CLAUDE.md` STATUS.

## Current: Phase 1 — Bootstrap (5 projects)

| Phase | What | Gate to advance |
|---|---|---|
| **1 — Bootstrap** *(NOW)* | 5 projects **re-tagged under v4.0** (page-purpose) + human-reviewed; refine the spec | Bootstrap report accepted → lock v4.0 or bump v4.1 |
| **2 — Dataset** | 25 projects labeled + verified; split **15 train / 5 val / 5 test** by whole project, stratified for tag + representation coverage | 25 verified, split frozen |
| **3 — First model + benchmark** | Train first model (predicts `useful_for` + `tag_importance` + `page_role` + confidence per page); run the **blind agent** vs human truth; build the labeler agent + skills | Benchmark measured on val/test |
| **4 — Scale** | 50 → 112, agent labels + humans spot-check | **Trust gate:** finish floor plan recall ≥97%, finish schedule/spec ≥98%, ~0 critical false negatives on held-out |
| **5 — Deploy** | Serverless triage model in production (ranks/selects pages, retains raw) | — |

## Rules across all phases
- Split **by project**, never by page (no drawing-style leakage).
- Project/document decisions are **derived** from page/doc predictions + metadata.
- Only `human_reviewed` labels are ground truth. Old prompt-v1/v2 labels = weak historical, kept, not trusted.
- Scaling (Phase 4) only happens **after** the benchmark clears the trust gate — never on faith.

## Training cadence & RunPod
- **First training at 25 projects** (~600–1,000 labeled pages). The first model is a **text/metadata
  classifier** (page text + sheet title + vector/line counts + filename) — it trains on **CPU in
  minutes, no GPU / no RunPod**. Its job: prove the label→train→measure loop and give a first accuracy
  read on the 5 test projects. It is a *baseline*, not trusted.
- **RunPod (GPU) enters at ~50**, when we add the **image / fine-tuned-transformer** model — once the
  cheap text baseline plateaus and we know where it's blind. Don't pay for GPU to prove the loop.
- **Retrain** as the verified set grows (25 → 50 → 100 → …).
- **Accelerate with more agents only AFTER the agent-trust gate** below — then parallelize agents for
  throughput and retrain.

## Benchmark gates (starting targets — recalibrate on real data)
Through-line: **recall ≫ precision.** Over-keeping is fine (humans trim); a false negative loses flooring.

**Agent-trust gate** — when the agent may label on its own (humans just spot-check):
- finish floor plan recall ≥ **97%**; finish schedule/spec recall ≥ **98%**
- **~0 critical false negatives** on held-out projects
- project keep-recall ≥ **95%**

**First-model-useful gate** — the trained model is "good enough to help":
- critical-page recall ≥ **95%**; project keep-recall ≥ **95%** (don't lose a bid-worthy job)
- precision may be mediocre (it over-includes); it must never drop flooring
- practical: cuts a project's review from ~20 min to ~1–2 min with ~0 missed flooring

## Dataset composition (v4.0 — negatives are intrinsic, per page)
Under v4.0 the unit is the **page**, and **negatives come for free**: every project is mostly
non-flooring pages (MEP, structural, civil, RCP, paperwork), each labeled `useful_for: []`. So we
no longer source whole "reject projects" for training.
- **Every page of every selected project gets a row** — keeps (tagged) + negatives (`useful_for: []`).
  Full extraction (image + text + vector) runs on `process` documents.
- **Select projects for coverage** across the four tags, representation types (digital /
  vectorized-text / scanned), bundle quality, difficulty, and size — not "best finish schedule."
  Residential / simple commercial are welcome for `room_layout` + `quantity_takeoff` value.
- **Hard-negative whole projects** (paperwork-only, sign, facade-only, bad bundles) are kept only as
  **~5–10% of benchmark sets**, to test that ingestion yields a correctly-empty packet — they test
  the system, not the page classifier.
