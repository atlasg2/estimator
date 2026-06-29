# PLAN — orientation

Read **`CLAUDE.md`** first (the session front door: status, rules, doc map). This doc is the *why* +
where-things-live.

## North Star
A near-automated **commercial-flooring estimating tool**. Per project: ingest → **triage** (worth
bidding?) → **select the pages that matter** (+ why/importance) → *(later models)* extract finishes →
square footage → estimate. We are building the **first model = the triage + page-select brain**;
labeling exists to train it. Customer: Elite Installation (commercial / fitness / retail flooring).

## Where things live (DB vs local)
| Home | Holds | Authoritative? |
|---|---|---|
| **RDS (Postgres)** | catalog: candidates pool, extraction metadata, **labels** | ✅ source of truth |
| **S3** | bytes: raw PDFs, page images, text/vector JSON | ✅ source of truth |
| **`data/` (local, gitignored)** | working/staging + label mirror + page renders | ❌ scratch |

**Rule:** a *fact* (label, page, file) lives in RDS/S3; a working file on disk is staging. `data/` is
deletable/rebuildable, RDS/S3 are not. RDS tables: `candidates` (002); extraction catalog (001);
labels `classification_runs` / `project_labels` / `document_labels` / `page_labels` (003 + 004).

## Doc map
- `CLAUDE.md` — front door (status, rules, doc map)
- `docs/v1/V1_SPEC.md` — label spec (canonical; `spec_version` in header)
- `docs/v1/V1_RUNBOOK.md` — how to label one project
- `docs/v1/V1_PHASE_PLAN.md` — phases, training cadence, benchmark gates
- `docs/v1/DECISION_LOG.md` — why things changed · `docs/worklog/WORKLOG.md` — session diary
- `docs/reference/` — NOLA portal mechanics · `docs/archive/` — superseded/historical

## Repo
`app/` extraction worker · `scripts/` CLI tools · `migrations/` schema (001–004) ·
`tools/review_app.py` review UI · `data/` local staging (gitignored).
