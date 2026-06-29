# CLAUDE.md — read first

## STATUS
**Phase 1 · Bootstrap labeling (5 projects) · spec_version v3.0**
Next action: label project #1 — `24-21892` (fitness) under v3.0, then human review.

## North Star
End goal: a near-automated **commercial-flooring estimating tool**. Per project the system will:
ingest → **triage** (is it worth bidding?) → **select the pages that matter** (+ why/importance) →
*(later models)* extract finishes → square footage → estimate. Customer: **Elite Installation**
(commercial / fitness / retail flooring).
**The first model = the triage + page-select brain. All this labeling exists to train it.**

## V1 = what we're building now
V1 = a **trained, deployable triage model** that, per project, keeps/disqualifies (with a reason) and
**ranks/selects** the pages that matter for flooring. Deployed **serverless** (cheap, fast) — **NOT an
LLM at runtime**. (V2 later = finish/spec extraction + square footage.)
We are in V1's **labeling stage**: labeling exists only to build V1's training data.

## Rules — do not break
- **One project at a time. No multi-agent batch labeling.** Careful > fast.
- **Every labeled page gets text + image** (multimodal). Text-only only if the image is unavailable.
- **Don't scale on faith** — scale labeling only after the blind-agent benchmark clears the trust gate.
- **Facts live in RDS + S3** (source of truth); `data/` on disk is staging only.
- **Never delete/overwrite** raw PDFs or raw Claude labels. Claude + human labels coexist via `label_source`.
- **Only `human_reviewed` labels are ground truth.**
- Secrets are gitignored; the AWS/Supabase creds pasted in chat still need **rotation**.
- **Propose adjustments / surface new insights whenever you see a better way.** If something isn't
  being done the best way (e.g. "we need *bad* examples too, not just good"), say so — don't silently
  follow. Flag gaps, risks, and better options. Pushback/proposals are welcome while *planning*; once
  *executing*, run the agreed play.

## The doc system
- **Living docs** (edit in place — always current): `docs/v1/V1_SPEC.md`, `V1_PHASE_PLAN.md`,
  `V1_RUNBOOK.md`, and the STATUS block above.
- **Append-only logs**: `docs/worklog/WORKLOG.md` (session diary), `docs/v1/DECISION_LOG.md`
  (every change: what / why / when / does-it-need-relabel).
- **Rule:** every edit to a living doc = one `DECISION_LOG` entry. End each session → update STATUS +
  append one WORKLOG line. Versions live *inside* files (`spec_version: v3.x`), filenames stay stable.

## Doc map (read in order)
1. `docs/PLAN.md` — orientation
2. `docs/v1/V1_SPEC.md` — label spec (canonical; `spec_version` in header)
3. `docs/v1/V1_RUNBOOK.md` — how to label one project
4. `docs/v1/V1_PHASE_PLAN.md` — phases + gates
5. `docs/v1/DECISION_LOG.md` — why things changed
