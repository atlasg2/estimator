# System Audit Context — Construction Plan Data Pipeline

_Self-contained brief for an external audit (ChatGPT). Captures architecture,
database, storage, scripts, how the design evolved from the original plan, and
open concerns. Written 2026-06-27._

---

## 1. What we're building

A pipeline that turns **City of New Orleans building permits** into a clean,
queryable dataset of **construction plan pages** — rendered page images + extracted
text (with coordinates) + extracted vector geometry (with coordinates) — stored in
AWS. This is the **data foundation** for later flooring-takeoff ML (room polygons,
finish assignment, square footage). The end customer/partner is a **commercial
flooring + fitness-equipment installer** (Elite Installation Services), so the
dataset is biased toward commercial interiors (fitness, retail, restaurant, office),
with some residential for variety/simplicity.

**Two independent tracks:**
- **Collection** — find permits, discover their documents, download the PDFs.
- **Processing** — render each plan page and extract text + vectors into S3 + RDS.

Labeling/ML is explicitly **deferred** until the data foundation is solid.

---

## 2. Infrastructure (AWS, us-east-2, account 673611060332)

- **S3** `estimator-plans-673611060332` — all public access blocked. Holds bytes.
- **RDS Postgres 18.3** `estimator-db` (db.t4g.micro, 20GB, publicly accessible,
  default VPC + default security group). Holds metadata/catalog.
- **EC2 runner** `estimator-runner` (t3.large, Amazon Linux 2023, **Python 3.9**) —
  runs the worker **in-region**. See §7 for why this exists.
- **IAM user** `estimator` with AmazonS3FullAccess + AmazonRDSFullAccess +
  AmazonEC2FullAccess. (No IAM/SSM permissions — so no instance roles; the EC2 box
  uses the user's access keys.)
- Source permit index lives in a separate **Supabase** Postgres (`NolaPermit`
  table, ~456K rows) — this is *only* the permit metadata + a portal link, NOT the
  PDFs.

---

## 3. The NOLA portal (collection mechanics)

Each Supabase permit row has a `link` containing a `SearchString` (the portal "Ref
Code"). Two-step portal access:
- **Discover:** `GET PrmtView.aspx?ref=<SearchString>` → HTML listing each document
  with a hidden DocID (`onclick='DocRedirect(<DocID>)'`). **Rate-limited** (HTTP 429,
  `Retry-After: 3600`, ~20-30 calls then a 1-hr cooldown).
- **Download:** `GET GetDocument.aspx?DocID=<DocID>` → the PDF. **Not** rate-limited.

Key consequence: discovery is the scarce step. We seed candidates from SQL (free),
discover only when needed, and at scale will use a rotating-IP scraper (Apify) since
hundreds of discovery calls exceed the limit. WebFetch (different egress IP) can read
the doc list for fit-screening but strips DocIDs, so it can't download.

---

## 4. Database schema

### Ingestion tables (migrations/001_initial_schema.sql)
- **projects** — one row per processed permit (slug, name, s3 prefixes).
- **project_files** — one row per document (sha256, s3 key, file_slug=DocID,
  page_count, processing_status). Unique on (project_id, sha256).
- **plan_pages** — one row per processed page. Stores **measured facts**:
  width/height px, render_dpi, width/height pdf points, rotation,
  `coordinate_transform_json` (the PDF→pixel matrix), has_embedded_text,
  text_block_count, full_text_length, weird_character_ratio, vector_entity_count,
  line/rect/curve counts, image_object_count, vector_soft_cap_exceeded,
  vectors_truncated, page_representation_type (derived label, recomputable).
  Unique on (file_id, pdf_page_number).
- **page_artifacts** — pointers to S3 objects per page (page_image, text_json,
  vector_json[, overlay_image]). Unique on (page_id, artifact_type).
- **processing_runs**, **ingestion_events** — audit log.

All writes are idempotent upserts (`ON CONFLICT … DO UPDATE`).

### Candidate registry (migrations/002_candidates.sql)
- **candidates** — the resumable pool. One row per PERMIT (not document):
  permit_num (unique), code (RNVS/RNVN/NEWC), ref (SearchString), est_cost, sqft,
  address, description, fit_category (fitness/retail/restaurant/office/residential
  hint), **status** (`candidate → discovered → rejected | downloaded → processed`),
  **permit_json** (the WHOLE raw Supabase row, for fallback), documents_json
  (discovered doc list + which we selected), note.
- Currently seeded with **1,578 permits** (847 RNVS + 731 RNVN, applied 2024+,
  est_cost ≥ $150K).

---

## 5. Storage model

- **S3 holds bytes; RDS holds the catalog (pointers + facts).**
- Raw (every document kept — source of truth):
  `raw/<permit-slug>/documents/<DocID>.pdf`
- Processed (only selected plan docs):
  `processed/<permit-slug>/<DocID>/pages/page_NNN.png`
  `processed/<permit-slug>/<DocID>/text/page_NNN_text.json`
  `processed/<permit-slug>/<DocID>/vectors/page_NNN_vectors.json`

Size reference (one dense floor-plan page, ~59K vectors, **verbose** dual-coordinate
JSON): page PNG ~2MB, text JSON ~160KB, **vector JSON ~21MB**. A whole project's
vector JSON ≈ several hundred MB. Storage cost is trivial (~$0.02/GB-mo); the size
matters for **speed**, not cost (see §8).

---

## 6. Scripts / code

- **app/extract.py** — the proven per-page core. For a page: render to PNG at 150
  DPI; `get_text("dict")` → text spans with bbox in pdf points AND pixels;
  `get_drawings()` → every line/rect/curve/quad with geometry in pdf points AND
  pixels; compute the coordinate transform (`pixel = pdf_point * matrix`, matrix =
  scale by dpi/72; rotation handled by fitz); classify page representation from
  facts. Overlays (blue text boxes / red vector lines, for visual QA) are OFF by
  default — they're the heaviest step and regenerable.
- **app/ingest.py** — the worker. Per project: read manifest, register project +
  files, upload ALL raw PDFs to S3, then for selected plan docs extract every page →
  upload 3 artifacts → write plan_pages + page_artifacts rows. Idempotent.
- **app/config.py** — env config (S3 bucket, DATABASE_URL, render dpi, which doc
  classes to process).
- **scripts/run_ingestion.py** — CLI: `--project-dir`.
- **scripts/spike_coordinates.py** — Phase 0 spike that renders a page + overlay so
  a human (or Claude vision) can confirm the extracted boxes/lines actually align.
- **migrations/001, 002** — schema.

The coordinate transform is **verified correct** by vision spot-check on a real
floor-plan page (231 Carondelet A201): blue text boxes and red vector lines land
exactly on the real labels/walls, at full vector density.

---

## 7. How this EVOLVED from the original plan (`docs/data-pipeline-plan.md`)

The original plan (from ChatGPT) was a phased Phase 0 → AWS Batch design. Changes we
made as we learned:

1. **`import_from_supabase.py` premise was wrong.** Supabase has the permit index +
   a portal link, NOT the PDFs. Real collection is the **NOLA portal scrape**
   (discover + download), not a Supabase download.
2. **Vector caps were too low.** Plan said soft 10K / hard 20K; real sheets run
   25K–95K vectors (max seen 94,712), median ~26K, 30/59 pages over 20K. Raised the
   hard cap to 250K (safety ceiling only).
3. **Download ALL raw, then Claude selects which docs to process.** Replaces a
   brittle filename **regex** (which kept mis-classifying — e.g. grabbing inspection
   reports / fire-alarm review docs as "plans"). Raw is always kept so a wrong skip
   is recoverable.
4. **Overlays moved from per-page to QA-only / on-demand.** They were the slowest +
   bulkiest artifact and are regenerable from image+JSON.
5. **Store measured facts, not made-up judgments.** We removed an invented
   `needs_review`/`quality_flags` scoring layer (arbitrary thresholds). We keep raw
   facts; derived labels (page type) are recomputable in queries, not baked in.
6. **Candidate registry** (new) — resumable pool with status lifecycle + the whole
   raw permit row as JSON.
7. **EC2 in-region runner** (new). The dev box is a GitHub Codespace on **Azure**;
   RDS/S3 are on **AWS**. Cross-cloud caused frequent **connection timeouts**, made
   worse because the Codespace egress IP changes (breaking the RDS security-group
   allowlist). Running the worker on EC2 in us-east-2 eliminated the timeouts and is
   the precursor to the Docker → AWS Batch phase.
8. **Claude doc-selection will run on a Claude Max subscription via Claude Code
   agents/skills/workflows — NOT the Anthropic API** (cost decision). Plan: the
   lightweight judgment (which docs to process) runs in the Claude Code session on
   Max; the heavy render/extract runs on AWS Batch.

---

## 8. Open concerns (please audit)

1. **SPEED — biggest concern.** One project (~54 plan pages) takes ~20–30 minutes,
   which is too slow to iterate. The bottleneck is dense pages (60–95K vectors):
   - We compute AND store per-vector **pixel coordinates** in addition to pdf
     coordinates — this doubles both the CPU (60K+ matrix multiplies/page) and the
     JSON size (~21MB/page).
   - Planned fixes (want your take): **drop pixel coords**, store pdf-only and derive
     px from the stored transform; **gzip** the JSON; possibly **parallelize pages**
     (multiprocessing / bigger instance) and move to **Docker + AWS Batch** for the
     real scale run. Is there a better storage format (Parquet/binary) for the vector
     data given eventual ML use?
2. **Doc classification.** Currently still a filename regex in code; being replaced
   by explicit Claude-selected DocIDs. Want a sanity check on the selection approach.
3. **Untested page types.** Rotated/landscape pages (rotation code path never
   exercised — all test data is rotation 0) and scanned/raster pages (no OCR; we
   detect+flag but don't process). Is detect-and-skip acceptable for now?
4. **"Not flagged ≠ verified."** We store measured facts, not a correctness check.
   The only real accuracy measure is **sampled vision spot-checks** (deferred to the
   labeling phase). Is that an acceptable QA posture for the data foundation?
5. **Vectorized/outlined text risk.** If a CAD export renders text as vector outlines
   (no text layer), `get_text()` returns nothing → we'd silently lose room/finish
   labels with no flag. We have not added a detector for this yet.
6. **Storage verbosity.** Vector JSON is verbose (dual coords, no compression);
   compact + gzip planned (~10x smaller).
7. **Security.** AWS access keys and the RDS master password were pasted into a chat
   during setup (to be rotated). RDS is publicly accessible with a broad default
   security group. Acceptable for a short-lived pilot; should be tightened.

---

## 9. Current status

- Phase 0 extraction **proven** (coordinate overlay aligns on a real plan page).
- AWS fully stood up (S3 + RDS + EC2 runner); candidate registry seeded (1,578).
- One project (231 Carondelet) was ingested cleanly **before** the latest
  refinements; we are re-running a fitness project (Crunch) through the refined
  system (explicit doc-selection + speed fixes) as the first end-to-end validation
  of the *current* design. Then 4 more for variety, then scale (Apify + Batch), then
  labeling.
