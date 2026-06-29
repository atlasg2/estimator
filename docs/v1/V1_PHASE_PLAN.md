# V1 Phase Plan

Living doc — the gates and milestones. Current phase is mirrored in `CLAUDE.md` STATUS.

## Current: Phase 1 — Bootstrap (5 projects)

| Phase | What | Gate to advance |
|---|---|---|
| **1 — Bootstrap** *(NOW)* | 5 projects hand-labeled + human-reviewed under v3.0; refine the spec | Bootstrap report accepted → lock v3.0 or bump v3.1 |
| **2 — Dataset** | 25 projects labeled + verified; split **15 train / 5 val / 5 test** by whole project, stratified so each split has finish-rich projects | 25 verified, split frozen |
| **3 — First model + benchmark** | Train first model (predicts page_usefulness + page_role + confidence); run the **blind agent** vs human truth; build the labeler agent + skills | Benchmark measured on val/test |
| **4 — Scale** | 50 → 112, agent labels + humans spot-check | **Trust gate:** finish floor plan recall ≥97%, finish schedule/spec ≥98%, ~0 critical false negatives on held-out |
| **5 — Deploy** | Serverless triage model in production (ranks/selects pages, retains raw) | — |

## Rules across all phases
- Split **by project**, never by page (no drawing-style leakage).
- Project/document decisions are **derived** from page/doc predictions + metadata.
- Only `human_reviewed` labels are ground truth. Old prompt-v1/v2 labels = weak historical, kept, not trusted.
- Scaling (Phase 4) only happens **after** the benchmark clears the trust gate — never on faith.
