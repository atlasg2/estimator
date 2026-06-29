# Where we are + open questions (for ChatGPT)

_Snapshot to re-orient. Detail lives in SYSTEM-AUDIT.md and
CLASSIFICATION-PIPELINE-PROPOSAL.md (v2)._

## The goal
NOLA building permits → a **labeled, fully-extracted plan-page dataset** for **commercial
flooring takeoff**. Partner/customer: **Elite Installation** — commercial / fitness / retail
flooring installer. So the dataset is biased to commercial interiors (fitness, retail,
restaurant, office) + some residential for variety.

## What's DONE
1. **Infra (AWS us-east-2, in-region):** S3 bucket + RDS Postgres + an EC2 runner. Running
   the worker on EC2 (not the Codespace) fixed constant cross-cloud timeouts. Supabase
   holds the permit index (~456K permits, scraped).
2. **Candidate pool:** a `candidates` table seeded with **1,578** permits (RNVS+RNVN, 2024+,
   ≥$150K) — each with curated columns + the whole raw permit row as JSON.
3. **Batch discovered (112):** all fitness (14) + all retail (48) + top 40 restaurants + 10
   residential. Pulled each permit's **full document list (filenames + DocIDs)** into
   `documents_json`. Key finding: the portal rate-limits discovery to **~12 requests/IP**,
   so we ran ~10 cheap EC2 boxes in parallel (distinct IPs) → 112 in ~5 min. WebFetch and
   single-IP both get throttled; multi-IP is the only fast way.
4. **Extraction worker (optimized):** renders page image + extracts text JSON + vector JSON
   (PDF coords only, gzipped), `--workers` page parallelism, `--docs`/`--max-pages` flags.
   ~3s/page (was ~37s). Proven on real projects (231 Carondelet, Crunch Fitness).

## What's NEXT (designed, not yet built)
The **classification + extraction pipeline** (see v2 proposal). Per project, 3 decisions:
- **Project:** keep / delete.
- **Document disposition:** process (plans/specs/manual) vs raw_only (paperwork/MEP — kept
  raw, not extracted).
- **Page labels:** classify every page of the process docs (type + flooring_relevant).

**Core trust principle:** the page classification is **labels, never a drop-filter** — we
extract every page of the documents we process, so a wrong label is a re-label, not a lost
floor plan. Classification stored versioned + separate from artifacts; everything reversible.

**Cleverness in v2:** index-driven classification (read the sheet index, reconcile pages
against it), tiered confidence (text → vision → human), adversarial verifier agent,
gold-set accuracy measured against our hand-done projects.

**Architecture:** script (gather: download all + per-page text) → subagent
`project-classifier` (the 3 decisions) → subagent `classification-verifier` (adversarial)
→ existing worker (full extraction) → workflow (orchestrate 112 in parallel + record
timing/tokens). Runs on the Claude Max plan, not the API.

## OPEN QUESTIONS for ChatGPT
1. **Extract-full vs surgical:** extract ALL pages of process docs now (labels not filter),
   go surgical only once accuracy is measured? What precision/recall bar would justify it?
2. **Index-driven backbone:** reconcile pages against the sheet index — right primary
   strategy, or over-engineered vs plain per-page classification?
3. **Scope of "process" for v1:** architectural drawings only, or also specs / project
   manuals (text-heavy, carry finish callouts)?
4. **Verification:** one adversarial verifier vs N independent refuters + majority vote?
   Where does human review enter?
5. **Schema/versioning:** separate versioned `page_labels` table (re-runnable without
   re-extracting) — agree? What fields (type, flooring_relevant, sheet#, evidence, tier,
   confidence, model_version)?
6. **Anything missing** before scaling 112 → thousands?

## Housekeeping
- EC2 runner is up (~$0.08/hr); can stop between work sessions.
- AWS keys + RDS password were pasted in chat during setup → rotate.
