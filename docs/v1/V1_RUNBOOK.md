# V1 Runbook — how we label one project

The exact bootstrap process. Living doc — edit in place + log changes in `DECISION_LOG.md`.

## Mode (bootstrap)
**Full multimodal, one project at a time, no fan-out.** Review each relevant page with extracted
text **and** the visual page. Text-only only if the image is genuinely unavailable.

## Per-project steps
1. **Evidence packet** — assemble: permit metadata, candidate id, permit number, project name,
   address (if any), document list with DocIDs + filenames + page counts, cheap per-page text,
   sheet number/title (if any), and visual page access for every page reviewed.
2. **Claude labels the project** — produce: a readable project-level explanation; document-by-document
   decisions; page-by-page labels for process / possibly-relevant docs; strict JSON; and an
   issues/confusions list.
3. **Contradiction checker** — run the deterministic flags (see `V1_SPEC.md`) for likely
   misses/overcalls.
4. **Human review** — correct obvious issues. Watch especially for: missed finish schedules / finish
   legends / finish floor plans / flooring specs; docs wrongly `raw_only`; pages wrongly `not_flooring`.
5. **Save** — store separately: Claude initial labels (`label_source=claude, reviewed=false`),
   human-corrected final labels (`label_source=human_reviewed, reviewed=true`), contradiction flags,
   and the issues/confusions list. Write straight to RDS (`spec_version=v3.0`); keep a local mirror.

## After all 5 — bootstrap review report
Summarize: keep/disqualify/unknown counts; page usefulness distribution; did Claude miss any finish
schedules / legends / floor plans?; did the page roles work?; were reason codes enough?; did full
visual review help?; which pages were hard; what should change before the 25.
Then choose: **A.** v3.0 good → continue to 25 · **B.** small changes → v3.1, relabel the 5 if needed,
continue · **C.** major confusion → revise process and rerun the bootstrap.

## Do not (until after the bootstrap)
Don't train; don't run all 112; don't use multi-agent labeling; don't build V2 extraction or square
footage; don't use page labels to skip extraction; don't delete/overwrite raw PDFs or raw Claude labels.
