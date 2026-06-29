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

### 2026-06-29 — Dataset must include rejects (negatives), not only keeps; extraction depth varies
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
