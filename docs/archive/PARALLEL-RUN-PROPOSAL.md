# Proposal: Document Selection + Running Projects in Parallel

_For external review (ChatGPT). Builds on SYSTEM-AUDIT.md. Written 2026-06-27._

## Where we are now

The single-machine worker is **optimized and working on an EC2 box (us-east-2,
in-region with RDS/S3)**. Implemented since the last audit:
- **Dropped stored pixel coordinates** — vectors stored in PDF coords only; pixels
  derived on demand from the per-page transform.
- **Gzipped** text + vector JSON artifacts (`.json.gz`, content_encoding recorded).
- **Per-phase timing** instrumentation.
- **`--workers` page-level multiprocessing** (each worker owns its DB conn + S3
  client), plus `--max-pages` for fast benchmarks and `--docs` for explicit
  document selection.

**Timing result (validation, 4 light pages, 1 worker):** avg ~3.0s/page (was
~37s/page). Phase split: **render ~1.5s/pg (now dominant)**, vector-extract ~0.8,
gzip ~0.4, text ~0.2, S3 upload ~0.1, DB ~0. Render is pure CPU → parallelizes well
with `--workers`. (Dense 60–95k-vector sheets will raise vector-extract; full runs
will show real numbers.)

## Refinement 1 — Document selection (important)

We are NOT processing every document in a permit. Rule:

> **Claude selects only the documents that matter for a FLOORING takeoff — i.e. the
> ARCHITECTURAL plan set (floor plans + room finish schedule). Everything else
> (MEP, plumbing risers, structural-only, agency approvals, receipts, contracts) is
> kept as raw PDF in S3 but NOT processed.**

Rationale: flooring area + finish live on the architectural sheets. MEP/plumbing/
approvals add pages and cost with no flooring value. Raw is always retained, so we
can process more documents later if a need appears (e.g. MEP for a different trade),
with no re-download.

Example — 231 Carondelet (12 documents): process **only DocID 8400627 (Arch set,
~59 pages)**. Skip the MEP set, plumbing riser diagram, LDH/fire-marshal approvals,
contract, receipt, etc.

**Question for review:** is "architectural set only" the right default for a flooring
dataset, or should we also keep the MEP set for some projects (e.g. for slab/drain
penetrations that affect flooring)? Default for now is arch-only.

## Refinement 2 — Pilot is 3 projects, run in parallel

Three projects, each **arch set only**, for variety + the customer's niche
(commercial flooring, esp. fitness/retail):
1. **Crunch Fitness** (RNVN) — fitness; arch set
2. **231 Carondelet** (RNVS) — restaurant; arch set (DocID 8400627)
3. **One retail/restaurant** (RNVS/RNVN) — TBD, arch set

Goal: run all 3 **at the same time** and confirm the optimized pipeline end-to-end
across variety, then scale.

## How to run them in parallel — two options

**Option A — bigger EC2, parallel jobs (simplest).** Resize/launch a
compute-optimized instance (e.g. **c7i.2xlarge, 8 vCPU**) and run the 3 projects as
3 concurrent processes, each `--workers 2-3`. No new infra. Done in a few minutes.
Good for 3–10 projects.

**Option B — AWS Batch (scalable).** Dockerize the worker → push to ECR → Batch
compute environment + job queue + job definition. **1 Batch job = 1 project**, each
running `python run_ingestion.py --project <slug> --docs <archDocID> --workers N`.
Batch schedules many projects across instances. This is the right model for the real
scale run (dozens–hundreds of projects) but is more setup.

**Our lean:** for **3 projects, Option A** (bigger EC2, parallel) is enough and
fastest to results. **Invest in Option B (Batch) when we go past ~10–20 projects.**
The worker is already Batch-ready (it's parameterized by `--project`/`--docs`/
`--workers` and writes to S3+RDS).

## Questions for ChatGPT

1. Agree with **arch-set-only** as the flooring-dataset default? Any project types
   where MEP should also be processed?
2. For running 3 now: **Option A (bigger EC2 parallel) vs jumping to Option B
   (Batch)?** We lean A for 3, B for scale — reasonable?
3. Batch compute environment: instance family (c7i? mix?), and the tradeoff between
   **`--workers` per job** vs **more jobs in parallel** given total vCPUs.
4. Docker base image — pin **Python 3.11/3.12** (EC2 currently runs 3.9, which works
   but boto3 is deprecating 3.9). Any other pinning concerns?
5. Anything missing before we commit to the scale run (collection via Apify →
   process via Batch → then labeling)?
