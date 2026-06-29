# Status — current working state

_Disposable working notes. Updated as we go; not architecture._

**What this is:** pipeline that turns NOLA building permits → extracted plan-page
data (image + text + vectors) in AWS, for flooring-takeoff ML.

**Working now:**
- Phase 0 extraction proven (coordinate overlay aligns on a real plan page).
- AWS live: S3 bucket + RDS Postgres (schema migrated).
- Ingestion worker runs a project → S3 + RDS. 231 Carondelet ingested clean (117 pages).

**In progress / next:**
- `candidates` registry table (resumable: candidate → discovered → downloaded → processed).
- Claude-driven document selection (replace brittle filename regex).
- Clean re-run of the 3-project pilot (231 Carondelet ✓ + 27 Newcomb + Crunch Fitness).
- Then: scale collection (Apify) + processing (AWS Batch), then labeling.

**Known cleanup:**
- 27 Newcomb data is bloated (loose `review` classification pulled non-plan docs) — wipe + redo.
- Crunch Fitness ingest incomplete — redo with overlays-off + `keep`-only.
