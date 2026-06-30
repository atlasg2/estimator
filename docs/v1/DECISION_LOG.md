# Decision Log

Append-only. Every meaningful change: what / why / when / does-it-need-relabel. Pairs with edits to
the living docs (`V1_SPEC.md`, `V1_PHASE_PLAN.md`, `V1_RUNBOOK.md`).

---

### 2026-06-29 — Lock spec_version v3.0; stand up the doc system
**What:** Locked the V1 label spec at `v3.0` (project/doc/page schema, reason codes, page roles,
usefulness definitions, contradiction checker). Set up living-docs + append-only-logs system and
`CLAUDE.md` as the session front door.
**Why:** Prompt v1/v2 labels were inconsistent (v1 under-called critical, e.g. a TJ Maxx finish
schedule labeled `not_flooring`; v2 over-called). Needed one clean, versioned spec for verified
training data.
**Relabel:** Old v1/v2 labels kept as weak historical (not trusted). Relabel bootstrap projects fresh
under v3.0.

### 2026-06-29 — page_role splits finish_schedule vs finish_legend (HYPOTHESIS)
**What:** v3.0 separates `finish_schedule` and `finish_legend` (and adds `architectural_floor_plan`,
`enlarged_flooring_plan`).
**Why:** They are different page types worth capturing separately.
**Risk/relabel:** More roles can add labeler noise. Treated as a hypothesis to validate on the
bootstrap 5; if unreliable, merge in v3.1 (would require re-tagging affected pages).

### 2026-06-29 — Labels written direct to RDS (not local-first)
**What:** Bootstrap labels write straight to Postgres (`spec_version=v3.0`), local JSON kept only as a
mirror. Requires allowlisting the Codespace IP to RDS + migration 004 (ADD new fields, non-destructive).
**Why:** Avoids a sync step and drift; the bootstrap should test the real save path; DB stays the
source of truth from project #1.
**Relabel:** None.

### 2026-06-29 — Bootstrap 5 selected
**What:** fitness `24-21892`, restaurant `25-02683`, retail `24-04531` (TJ Maxx), small `25-16244`,
disqualify `25-26809` (flood-elevation cert). From the existing discovered pool; two were already
deep-reviewed (validate v3 fixes the under/over-call).
**Why:** Archetype variety, manageable size, reuse existing evidence.
**Relabel:** N/A.

### 2026-06-30 — v4.0 tweak: drop single `primary_use` → derived `primary_uses` (no relabel)
**What:** Removed the required single `primary_use`. `tag_importance` is now the sole source of
truth for ranking. Added two **derived** fields: `primary_uses` = every `useful_for` tag whose
`tag_importance == primary` (0, 1, or many); `display_primary_use` = one tag for UI/legacy only,
picked by tie-break `quantity_takeoff > finish_material > room_layout > project_context`.
**Why:** Combined finish-floor-plan/schedule sheets are genuinely primary for finish_material AND
room_layout AND quantity_takeoff at once — forcing one main job was fake precision and produced an
inconsistency between TJ Maxx RC2 (was finish_material) and church A101 (was quantity_takeoff). The
new model dissolves it (neither must choose) and makes per-task ranking clean (finish packet =
`tag_importance.finish_material == primary`, etc.). Surfaced during the bootstrap re-tag; converged
with GPT.
**Relabel:** None beyond a mechanical re-derive — the 2 already-tagged projects (24-04531, 24-21892)
were transformed in place (derive `primary_uses`/`display_primary_use` from existing `tag_importance`).

### 2026-06-30 — v3.0 → v4.0: Model 1 becomes a Page Purpose Classifier (TARGET CHANGE)
**What:** Re-scoped Model 1 from "is this flooring-relevant / should Elite bid this project?" to
"what downstream job(s) can each page help with, and how important is it for each?" Concretely:
- Dropped project-level `keep/disqualify` as a **learned target** (no ground truth for it). Any
  Elite bid logic becomes an optional app-layer `bid_filter_result`; human judgment → `reviewer_note`.
- Replaced page `page_usefulness` (critical/useful/maybe/not) + `flooring_relevant` with a
  multi-label **`useful_for`** = `finish_material | room_layout | quantity_takeoff | project_context`,
  plus per-tag **`tag_importance`** (primary/supporting/incidental), derived `overall_importance`,
  deterministic `primary_use`, and ordinal `tag_confidence` (no decimals).
- Added optional, byproduct-only **`observations`** (yes/no/unclear) incl. an `observations.sf`
  block for square-footage *readiness facts* (stated_area, scale_value, dimensions, schedule_type,
  match_lines, …). **Scope guardrail:** observations are capture, not extraction — no SF
  computation/summing/polygon-tracing during the bootstrap.
- Every page now gets a row (incl. negatives `useful_for: []`); the residential `25-26809` is
  labeled fully instead of project-disqualified.
- Storage: v4 labels live in a **JSONB store** (migration 005), enums validated in code; v3 labels
  **coexist** untouched. Only `human_reviewed` v4.0 = ground truth.
**Why:** v3 conflated a document-intelligence question (what is this page) with a company business
question (should Elite bid). The bid question isn't trainable and biased data collection (e.g.
discarding residential, which is valuable for square footage). Page-purpose is general, trainable,
denser per project, and one labeling pass seeds Models 2–4. Title sheets (e.g. TJ Maxx T1) were
wrongly dropped as `not_flooring` despite carrying scope/area/vendor info — fixed by `project_context`
+ `finish_material` tags + `context_signals`.
**Process:** Converged over multiple rounds with an external reviewer (GPT). Full reasoning trail in
`docs/proposals/` (page-purpose-rescope → reply-to-gpt → page-purpose-v4.0 → project-selection-and-prep).
**Relabel:** YES — re-tag the bootstrap 5 under v4.0 (v3 labels kept as weak historical, not
overwritten). Re-scoped dataset policy supersedes the "⅔ keep / ⅓ reject project" entry below.

### 2026-06-29 — Dataset must include rejects (negatives), not only keeps; extraction depth varies
*(SUPERSEDED by the 2026-06-30 v4.0 entry: negatives are now intrinsic at the page level — every
project is mostly negative pages — so we no longer source whole "reject projects" for training.
Hard-negative whole projects are kept only as ~5–10% of benchmark sets, to test the system.)*
**What:** The verified dataset deliberately includes a real share of `disqualify` projects (target ≈ ⅓
reject / ⅔ keep, calibrate), labeled at project + doc + a sample of pages (`not_flooring`). Heavy
extraction (image+text+vector) runs only on KEEP/process pages; rejects get **light** extraction (page
text + a rendered image + labels). For the 25 we reuse already-discovered projects (prioritize the 20
already fully extracted) and re-label them under v3 — no new discovery.
**Why:** A triage model that only sees good projects can't learn to reject bad ones — it needs
negatives at both project and page level. Mirrors production (most daily volume is junk). Rejects don't
need pixel-level vector geometry, so cheap suffices — saves cost. Re-labeling the already-extracted 20
also upgrades their weak v1/v2 labels to trusted v3.
**Relabel:** Re-label the chosen already-discovered projects under v3 (was: weak v1/v2).
