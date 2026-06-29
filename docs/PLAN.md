# PLAN — start here

Orientation doc: what's canonical, how the repo + database + storage are organized, what to clean
up and add, and the forward plan to a trusted, scalable labeler → model.

---1

## 1. Canonical spec
**`docs/spec/V3-SPEC.md` is the single source of truth for labeling.** Don't fork it; this file
only points to it.

V3 in four lines:
- Build a **human-verified labeled dataset** → train a **fast serverless triage model**.
- Label at 3 levels (project / document / page) with reason codes; **every page of a labeled doc gets text + image**.
- Gates: **5 (bootstrap) → 25 (first model, split 15/5/5 by project) → 50 → 112+**.
- Only `human_reviewed` rows are ground truth. Spec evolves in signed-off steps (v3 → v3.1).

---

## 2. Where things live (the DB-vs-local confusion, resolved)

| Home | Holds | Authoritative? |
|---|---|---|
| **RDS (Postgres)** | the **catalog**: candidates pool, extraction metadata, **labels** | ✅ source of truth |
| **S3** | the **bytes**: raw PDFs, page images, text/vector JSON | ✅ source of truth |
| **`data/` (local, gitignored)** | **working/staging** copies of candidates, evidence, label files | ❌ scratch; synced *up* to RDS |

**RDS tables:** pool → `candidates` (002); extraction catalog → `projects`, `project_files`,
`plan_pages`, `page_artifacts`, `processing_runs`, `ingestion_events` (001); labels →
`classification_runs`, `project_labels`, `document_labels`, `page_labels` (003; **004 adds v3 fields**).

**Rule:** a *fact* (label, page, file) lives in RDS/S3. A *working file* on disk is a staging copy we
push to RDS via `store_one.py`. `data/` is deletable/rebuildable; RDS/S3 are not.

---

## 3. Target layout — fold scripts + docs into real structure

The repo grew ad-hoc: a few scripts in `scripts/`, loose scratch at root, some one-offs only on the
EC2 box, and one flat `docs/` of 13 mixed files. Target:

```
estimator/
  README.md                 ADD   5 lines → "read docs/PLAN.md"
  CLAUDE.md                 ADD   rules auto-loaded into every session
  requirements.txt          ADD   pinned deps (psycopg, pymupdf, boto3, fastapi…)
  app/                      KEEP  extraction worker (config, extract, ingest)
  scripts/                  REGROUP by pipeline stage ↓
    collect/    discover_docs.py        (+ seed_candidates.py pulled from EC2)
    prep/       prep_candidate.py
    label/      verify_classification.py, store_one.py
    extract/    run_ingestion.py, extract_processed.py
    _archive/   spike_coordinates.py    (old phase-0 spike)
  migrations/               KEEP  001-003 (+ 004 for v3)
  tools/review_app.py       ADD   (Phase B) review UI
  docs/                     FOLDER it ↓
  data/                     KEEP  gitignored local staging

  DELETE:    spike_output/, .stored2/, scratchpad_emit_*.py, scratchpad_label.py
  GITIGNORE: .ec2-ip, .disc-ips, .stored2/, spike_output/   (currently leaking)
```

### docs/ → topical folders (not one flat pile)
```
docs/
  PLAN.md                   start here (this file)
  INDEX.md                  one-line index of every doc
  spec/
    V3-SPEC.md              canonical spec
    V3-SPEC-CHANGES.md      spec changelog (per V3-SPEC §11)
  reference/                durable how-it-works
    nola-portal.md
    nola-access-and-rate-limit.md
    data-pipeline-plan.md
  worklog/
    WORKLOG.md              running session log (replaces ad-hoc WHERE-WE-ARE)
    V1-RUN-2026-06-28.md    run logs
  archive/                  superseded / historical (kept for provenance, out of the way)
    CLASSIFICATION-PIPELINE-PROPOSAL.md  PARALLEL-RUN-PROPOSAL.md
    MODEL-LABELING-BRIEF.md  V1-SPEC-STATUS.md  WHERE-WE-ARE.md
    STATUS.md  SYSTEM-AUDIT.md  auto-takeoff-feasibility-conversation.md
```
Nothing is deleted from docs — superseded ≠ worthless (the v1/v2 story is our provenance); it's just
filed. A few one-off scripts live **only on the EC2 box** (`select_20.py`, `seed_candidates.py`,
`store_labels.py`) — pull keepers into `scripts/`, archive the rest, so the repo is the one source.

---

## 4. The `.claude/` folder — now vs. target

**Now:** `settings.local.json` + `agents/project-packet-builder.md` (draft).

**Target (built in Phase B, when rules settle — NOT now):**
```
.claude/
  settings.local.json
  agents/                        # WORKERS (judgment + tools)
    label-project-v3.md          # the v3 labeler
    label-verifier.md            # adjudicates contradiction-checker flags
  skills/                        # PLAYBOOKS (named commands; a skill can call an agent)
    label-project/SKILL.md       # /label-project <permit>: prep → label → verify → save
    review-labels/SKILL.md       # /review-labels: launch review UI
    sync-labels/SKILL.md         # /sync-labels: push verified labels local → RDS
```
**Agent = worker. Skill = playbook.** Build after the bootstrap settles the rules — hardening tooling
around a moving spec is the trap. Right now the "agent" is *me + you, by hand*.

---

## 5. Forward plan — manual → benchmark → trust → scale

**Phase A — Manual bootstrap (NOW).** Label the 5 by hand (me + you), one at a time, text+image,
human-corrected → 5 verified projects. Log spec gaps → v3.1. No agents/skills/scaling.

**Phase B — Build + benchmark the agent.** Crystallize v3.1 into the **labeler agent**. Run it
**blind** (isolated worktree — only raw evidence + spec, *cannot see our labels*) on the same
projects, in the background. **Compare blind output to human-verified truth** → the **benchmark**:
precision/recall, especially **critical-page recall**. Wrap stable steps into **skills**. Answers:
*can we trust the agent on its own?*

**Phase C — Scale, only once the benchmark clears.** Trust gate: finish floor plan recall ≥97%,
finish schedule/spec ≥98%, ~0 critical false negatives on held-out. Then scale (25 → 50 → 112) via the
skill/workflow, humans spot-checking. The verified dataset trains the **serverless model** that
replaces the agent at production volume.

**The point:** we don't scale on faith. The **blind benchmark is the proof** — only a proven agent
labels at scale.

---

## 6. Additions worth making (not just cleanup)

### Cross-session context — how Claude gets our rules every session
- **`CLAUDE.md`** (root, committed) — **project rules auto-loaded every session** for anyone in the
  repo: *"read docs/PLAN.md + spec/V3-SPEC.md first; one project at a time (no fan-out); text+image on
  every labeled page; don't scale without the blind benchmark; facts live in RDS/S3, `data/` is
  staging; secrets are gitignored."* **#1 gap — we don't have one.**
- **Memory files** (`~/.claude/.../memory/`, not in repo) — my persistent notes about *you* + working
  state. Already started (`MEMORY.md`).
- **`docs/worklog/WORKLOG.md`** (committed) — append-only: per session, what we did + decisions + next
  step. A new session reads "where we left off" in one place.

Rule: **durable rules → `CLAUDE.md`; what-happened → `WORKLOG.md`; how-to-work-with-you → memory.**

### Also missing
- `README.md`, `requirements.txt`, `docs/spec/V3-SPEC-CHANGES.md`.
- **Gold-set backup** — verified labels are the crown jewels; they must live in **RDS**, not only
  local `data/`; export a snapshot periodically.

---

## 7. Git / GitHub hygiene
- Remote exists: `github.com/atlasg2/estimator`. ~26 files **uncommitted** — commit current state, then
  commit after each meaningful step (a reviewed project, a spec change), and push.
- Secrets stay out. `data/`, `.rds-password`, `*.pem` are gitignored; **add `.ec2-ip`, `.disc-ips`,
  `.stored2/`, `spike_output/`**. The AWS + Supabase creds pasted in chat still need **rotation** —
  open security action.

---

## 8. Cleanup actions (proposed — execute on your OK)
1. **docs/**: make `spec/ reference/ worklog/ archive/`, move the 13 files in; add `INDEX.md`.
2. **scripts/**: make `collect/ prep/ label/ extract/ _archive/`, move scripts in; fix imports/paths.
3. **Add**: `README.md`, `CLAUDE.md`, `requirements.txt`, `docs/spec/V3-SPEC-CHANGES.md`,
   `docs/worklog/WORKLOG.md`.
4. **Delete**: `spike_output/`, `.stored2/`, root `scratchpad_*.py`; extend `.gitignore`.
5. **Commit + push** the tidy as one clean commit.

Nothing here touches RDS, S3, or `data/` contents — pure repo organization.
