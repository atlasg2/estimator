Construction Plan Data Pipeline: Phase 0 to AWS Batch
Goal
Build a construction-plan data pipeline that starts with locally testing PDF extraction, then moves into an AWS-native ingestion system capable of processing many projects.
The pipeline should support future machine learning work, page classification, finish extraction, and eventually takeoff assistance, but this document only covers the data foundation.
High-level architecture
Existing source system:
Supabase contains scraped permit/project/document metadata.
Supabase may contain document URLs, storage paths, or references to downloaded PDFs.
New processing system:
Local machine / Codespaces for development and Phase 0 testing.
AWS S3 for raw PDFs and processed artifacts.
AWS RDS Postgres for ingestion metadata, labels, predictions, and future ML experiment tracking.
Docker for repeatable worker execution.
AWS ECR for storing Docker images.
EC2 for first manual worker runs.
AWS Batch later for processing many projects in parallel.
Colab / RunPod later for ML training, not initial ingestion.
Source-of-truth decision
Do not re-scrape public websites unless necessary.
Use Supabase as the existing scraped project/document index.
For selected projects:
Supabase project/document records
→ import/copy PDFs into local raw folder for Phase 0
→ later import/copy PDFs into AWS S3 raw storage
→ process from our own raw copy
Once a document is selected for this pipeline, AWS S3 becomes the stable raw-file source of truth.
Reasons:
public document links can disappear or change
websites can block or throttle downloads
experiments need reproducible files
ML datasets need stable file references
future processing should not depend on live permit-site availability
Overall rollout
Phase 0: Local coordinate extraction spike
Purpose:
Prove that real construction PDFs can be rendered, extracted, and visually verified locally.
Process a few selected PDFs/pages from Supabase-imported projects.
Do not use AWS, RDS, Docker, Batch, OCR, ML, or LLM calls in Phase 0.
Pass condition:
rendered page image exists
text JSON exists
vector JSON exists
overlay image exists
summary JSON exists
coordinate_transform_json exists
blue text boxes align with real text
red vector lines align with drawing geometry
rotated/cropped/dense-vector pages do not break the script
Phase 1: AWS ingestion worker
Purpose:
Move the proven Phase 0 extraction logic into a real ingestion worker.
Use:
S3 for raw and processed files
RDS Postgres for metadata
Docker for repeatable execution
EC2 for first manual project runs
Process 1–5 full projects first.
Pass condition:
raw PDFs copied to S3
processed page artifacts created in S3
RDS rows written correctly
reruns are idempotent
reports are generated
overlays still align
Phase 2: 50-project dataset build
Purpose:
Process 50 selected projects into the AWS data foundation.
Use this as the first serious dataset for labeling and page classifier work.
Do not train models until the 50-project ingestion outputs are clean enough.
Pass condition:
50 projects ingested
project/page/file/artifact metadata queryable
page images/text/vectors/overlays available
failed pages and warnings logged
dataset can be sampled for labeling
Phase 3: Docker + ECR + EC2 production-style worker
Purpose:
Package the ingestion worker as a Docker image and run it manually on EC2.
Use this before AWS Batch.
Pass condition:
Docker image builds locally
Docker image pushed to ECR
EC2 can pull and run the image
worker can process one project from S3/local source
worker writes outputs to S3 and RDS
logs are captured
Phase 4: AWS Batch
Purpose:
Run the same Docker worker across many projects in parallel.
Only start Batch after EC2 manual worker is stable.
Pass condition:
Batch job definition created
Batch compute environment configured
one test job runs successfully
small batch of 3–5 projects runs successfully
failure/retry behavior works
costs are controlled with max vCPU limits
Phase 0 detailed spec
Create:
scripts/import_from_supabase.py
scripts/spike_coordinates.py
import_from_supabase.py
Purpose:
Pull selected project documents from Supabase into a local raw project folder.
Example:
python scripts/import_from_supabase.py --project-id <supabase_project_id> --download-local
Optional flags:
--limit 5
--dry-run
--download-local
--upload-s3
Environment variables:
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
RAW_PROJECTS_DIR
AWS_REGION
S3_BUCKET_NAME
Local output:
raw_projects/
  {project_slug}/
    documents/
      {document_slug}.pdf
    import_manifest.json
Import manifest:
{
  "project_slug": "project_001",
  "supabase_project_id": "abc123",
  "imported_at": "timestamp",
  "documents": [
    {
      "source_document_id": "doc123",
      "source_url": "https://...",
      "original_file_name": "A_Set.pdf",
      "document_slug": "a_set",
      "local_path": "raw_projects/project_001/documents/a_set.pdf",
      "sha256": "...",
      "file_size_bytes": 12345678,
      "status": "imported"
    }
  ]
}
Requirements:
connect to Supabase
query selected project/document records
identify usable PDFs
download/copy files locally
compute SHA256 in chunks
avoid duplicate downloads
log missing/failed/non-PDF documents
produce import_manifest.json
spike_coordinates.py
Purpose:
Run Phase 0 extraction on one local PDF page.
Example:
python scripts/spike_coordinates.py --pdf ./raw_projects/project_001/documents/a_set.pdf --page 1 --render-dpi 150
Inputs:
--pdf
--page
--render-dpi default 150
--output-dir default ./spike_output
--max-overlay-vectors default 5000
--debug-label-text optional
--debug-label-vectors optional
Outputs:
spike_output/
  a_set_page_001.png
  a_set_page_001_text.json
  a_set_page_001_vectors.json
  a_set_page_001_overlay.png
  a_set_page_001_summary.json
Text JSON format:
[
  {
    "text": "LVT-1",
    "bbox_pdf": [120.5, 168.2, 137.1, 175.0],
    "bbox_px": [500, 700, 570, 730],
    "source": "pymupdf_text_layer",
    "page_number": 1,
    "block_index": 37,
    "line_index": 2,
    "span_index": 1,
    "rotation": 0
  }
]
Vector JSON format:
[
  {
    "entity_type": "line",
    "path_index": 41,
    "item_index": 3,
    "raw_item": null,
    "geometry_pdf": [[24.1, 48.2], [216.8, 48.2]],
    "geometry_px": [[100, 200], [900, 200]],
    "stroke_width": 0.5,
    "color": "#000000",
    "fill_color": null,
    "dash_pattern": null,
    "is_closed": false,
    "source": "pymupdf_get_drawings",
    "page_number": 1,
    "entity_index": 882
  }
]
Summary JSON should include:
{
  "pdf_path": "./raw_projects/project_001/documents/a_set.pdf",
  "page_number": 1,
  "render_dpi": 150,
  "width_px": 1650,
  "height_px": 1275,
  "width_pdf_points": 792,
  "height_pdf_points": 612,
  "rotation": 0,
  "text_block_count": 438,
  "full_text_length": 6120,
  "weird_character_ratio": 0.01,
  "has_embedded_text": true,
  "vector_entity_count": 18240,
  "line_count": 17000,
  "rect_count": 400,
  "curve_count": 120,
  "image_object_count": 1,
  "vector_soft_cap_exceeded": true,
  "vectors_truncated": false,
  "page_representation_type": "digital_text_vector_page",
  "coordinate_transform_json": {},
  "warnings": [],
  "outputs": {
    "page_image": "spike_output/a_set_page_001.png",
    "text_json": "spike_output/a_set_page_001_text.json",
    "vector_json": "spike_output/a_set_page_001_vectors.json",
    "overlay_image": "spike_output/a_set_page_001_overlay.png"
  }
}
coordinate_transform_json should include:
{
  "render_dpi": 150,
  "zoom": 2.0833333333,
  "page_rect": [0, 0, 792, 612],
  "cropbox": [0, 0, 792, 612],
  "mediabox": [0, 0, 792, 612],
  "rotation": 0,
  "rendered_width_px": 1650,
  "rendered_height_px": 1275,
  "pdf_to_px_matrix": [],
  "derotation_matrix": [],
  "notes": []
}
Vector caps:
soft cap: 10,000 vector entities
hard cap: 20,000 vector entities
max overlay vectors: 5,000 by default
If soft cap exceeded:
continue
set vector_soft_cap_exceeded = true
add warning
If hard cap exceeded:
do not crash
store stats
store capped sample if practical
set vectors_truncated = true
create capped overlay
continue
Phase 0 manual test set:
Use pages with:
normal architect floor plan
finish schedule if available
rotated/landscape page
dense hatch/vector-heavy page
scanned or mixed page if available
Phase 1 AWS ingestion worker spec
Create repo structure:
app/
  __init__.py
  config.py
  db.py
  s3.py
  log.py

app/ingestion/
  __init__.py
  inventory.py
  pdf_render.py
  text_extract.py
  vector_extract.py
  overlays.py
  quality.py
  pipeline.py
  manifest.py
  reports.py

scripts/
  import_from_supabase.py
  spike_coordinates.py
  run_ingestion.py
  process_project.py
  process_pdf.py
  report_ingestion.py

migrations/
  001_initial_schema.sql

docs/
  data_pipeline_master_plan.md

Dockerfile
README.md
.env.example
Environment variables:
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY

AWS_REGION
S3_BUCKET_NAME
DATABASE_URL

RAW_PROJECTS_DIR
LOCAL_WORK_DIR
RENDER_DPI

WORKER_VERSION
LOG_LEVEL
THUMBNAIL_MAX_WIDTH
MAX_OVERLAY_VECTORS
VECTOR_SOFT_CAP
VECTOR_HARD_CAP
S3_RAW_PREFIX
S3_PROCESSED_PREFIX
Defaults:
RENDER_DPI=150
THUMBNAIL_MAX_WIDTH=400
MAX_OVERLAY_VECTORS=5000
VECTOR_SOFT_CAP=10000
VECTOR_HARD_CAP=20000
S3_RAW_PREFIX=raw
S3_PROCESSED_PREFIX=processed
S3 raw structure:
raw/{project_slug}/documents/{document_slug}.pdf
raw/{project_slug}/import_manifest.json
S3 processed structure:
processed/{project_slug}/manifest.json
processed/{project_slug}/{file_slug}/pages/page_{page_number:03d}.png
processed/{project_slug}/{file_slug}/thumbnails/page_{page_number:03d}_thumb.jpg
processed/{project_slug}/{file_slug}/text/page_{page_number:03d}_text.json
processed/{project_slug}/{file_slug}/vectors/page_{page_number:03d}_vectors.json
processed/{project_slug}/{file_slug}/overlays/page_{page_number:03d}_overlay.png
processed/{project_slug}/logs/{processing_run_id}.log
Phase 1 commands:
python scripts/import_from_supabase.py --project-id <id> --upload-s3
python scripts/run_ingestion.py --project project_001
python scripts/process_pdf.py --project project_001 --file ./raw_projects/project_001/documents/a_set.pdf
python scripts/report_ingestion.py
Optional flags:
--dry-run
--force
--render-dpi 150
--skip-overlays
--skip-vector-extraction
--skip-raw-upload
--max-pages
RDS schema
Use RDS Postgres.
projects
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    source TEXT,
    supabase_project_id TEXT,
    local_raw_path TEXT,
    s3_raw_prefix TEXT NOT NULL,
    s3_processed_prefix TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
project_files
CREATE TABLE IF NOT EXISTS project_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_document_id TEXT,
    original_file_name TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    local_path TEXT,
    s3_object_key TEXT NOT NULL,
    file_slug TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    sha256 TEXT NOT NULL,
    page_count INTEGER,
    processing_status TEXT NOT NULL DEFAULT 'pending',
    locked_by_run_id UUID,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uniq_project_sha256 UNIQUE (project_id, sha256),
    CONSTRAINT uniq_project_rel_path UNIQUE (project_id, relative_path)
);
plan_pages
CREATE TABLE IF NOT EXISTS plan_pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    file_id UUID NOT NULL REFERENCES project_files(id) ON DELETE CASCADE,
    pdf_page_number INTEGER NOT NULL,
    width_px INTEGER NOT NULL,
    height_px INTEGER NOT NULL,
    render_dpi INTEGER NOT NULL,
    width_pdf_points NUMERIC,
    height_pdf_points NUMERIC,
    rotation INTEGER DEFAULT 0,
    coordinate_transform_json JSONB,
    has_embedded_text BOOLEAN NOT NULL DEFAULT FALSE,
    text_block_count INTEGER NOT NULL DEFAULT 0,
    full_text_length INTEGER NOT NULL DEFAULT 0,
    weird_character_ratio NUMERIC DEFAULT 0.0,
    has_vectors BOOLEAN NOT NULL DEFAULT FALSE,
    vector_entity_count INTEGER NOT NULL DEFAULT 0,
    line_count INTEGER NOT NULL DEFAULT 0,
    rect_count INTEGER NOT NULL DEFAULT 0,
    curve_count INTEGER NOT NULL DEFAULT 0,
    image_object_count INTEGER DEFAULT 0,
    vector_soft_cap_exceeded BOOLEAN NOT NULL DEFAULT FALSE,
    vectors_truncated BOOLEAN NOT NULL DEFAULT FALSE,
    page_representation_type TEXT NOT NULL DEFAULT 'unknown',
    processing_status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uniq_file_page UNIQUE (file_id, pdf_page_number)
);
page_artifacts
CREATE TABLE IF NOT EXISTS page_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id UUID NOT NULL REFERENCES plan_pages(id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,
    s3_object_key TEXT NOT NULL,
    file_size_bytes BIGINT,
    content_type TEXT,
    metadata_json JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uniq_page_artifact UNIQUE (page_id, artifact_type)
);
Allowed artifact types:
page_image
thumbnail
text_json
vector_json
overlay_image
processing_runs
CREATE TABLE IF NOT EXISTS processing_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_type TEXT NOT NULL,
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    worker_version TEXT,
    docker_image_tag TEXT,
    log_s3_object_key TEXT,
    error_message TEXT,
    metadata_json JSONB
);
ingestion_events
CREATE TABLE IF NOT EXISTS ingestion_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    processing_run_id UUID NOT NULL REFERENCES processing_runs(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    file_id UUID REFERENCES project_files(id) ON DELETE SET NULL,
    page_id UUID REFERENCES plan_pages(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    event_level TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata_json JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
Indexes:
CREATE INDEX IF NOT EXISTS idx_projects_slug ON projects(slug);
CREATE INDEX IF NOT EXISTS idx_projects_supabase_project_id ON projects(supabase_project_id);

CREATE INDEX IF NOT EXISTS idx_project_files_project_id ON project_files(project_id);
CREATE INDEX IF NOT EXISTS idx_project_files_sha256 ON project_files(sha256);
CREATE INDEX IF NOT EXISTS idx_project_files_status ON project_files(processing_status);
CREATE INDEX IF NOT EXISTS idx_project_files_source_document_id ON project_files(source_document_id);

CREATE INDEX IF NOT EXISTS idx_plan_pages_project_id ON plan_pages(project_id);
CREATE INDEX IF NOT EXISTS idx_plan_pages_file_id ON plan_pages(file_id);
CREATE INDEX IF NOT EXISTS idx_plan_pages_representation ON plan_pages(page_representation_type);
CREATE INDEX IF NOT EXISTS idx_plan_pages_status ON plan_pages(processing_status);

CREATE INDEX IF NOT EXISTS idx_page_artifacts_page_id ON page_artifacts(page_id);
CREATE INDEX IF NOT EXISTS idx_page_artifacts_type ON page_artifacts(artifact_type);

CREATE INDEX IF NOT EXISTS idx_processing_runs_project_id ON processing_runs(project_id);
CREATE INDEX IF NOT EXISTS idx_processing_runs_status ON processing_runs(status);

CREATE INDEX IF NOT EXISTS idx_ingestion_events_run_id ON ingestion_events(processing_run_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_events_level ON ingestion_events(event_level);
Phase 1 processing behavior
For each project:
Create or update project row.
Import/copy raw PDFs from Supabase source into S3 raw prefix.
Register files in RDS.
Compute SHA256 hashes in chunks.
Process every PDF.
For each page:


render page image
create thumbnail
extract embedded text
extract vector geometry
create overlay
compute page representation metadata
upload artifacts to S3
write/update RDS page and artifact rows
log warnings/errors
Create/update project manifest.
Generate processing report.
Idempotency requirements
The pipeline must be safe to rerun.
Rules:
do not duplicate projects
do not duplicate files
do not duplicate pages
do not duplicate artifacts
upsert by project slug, source document id, file hash, page number, and artifact type
if artifact exists and –force is not set, skip or verify
if –force is set, regenerate and update
one failed page should not crash the whole project
Error handling
If a page fails:
mark page as failed
store error_message
add ingestion_event
continue
If a PDF fails:
mark project_file as failed
store error_message
add ingestion_event
continue
If S3 upload fails:
retry with backoff
if still failing, mark artifact/page/file failed
If DB write fails:
rollback that unit of work
log error clearly
Docker spec
Create Dockerfile for the ingestion worker.
The Docker image must support:
docker run --env-file .env plan-ingestion-worker python scripts/run_ingestion.py --project project_001
Docker image should include:
Python runtime
PyMuPDF
Pillow
OpenCV if used
boto3
psycopg or SQLAlchemy
Supabase client if used
any migration tooling
project code
Docker should not include local raw PDFs or secrets.
ECR + EC2 path
After Phase 1 works locally:
Build Docker image locally or in GitHub Actions.
Create ECR repo.
Push Docker image to ECR.
Launch EC2 worker instance.
Configure EC2 IAM role for S3/ECR/RDS access.
Pull Docker image on EC2.
Run ingestion manually for one project.
Verify S3/RDS outputs.
Run 1–5 full projects manually.
Only then move to Batch.
Example:
docker build -t plan-ingestion-worker .
docker tag plan-ingestion-worker:latest <aws_account_id>.dkr.ecr.<region>.amazonaws.com/plan-ingestion-worker:latest
docker push <aws_account_id>.dkr.ecr.<region>.amazonaws.com/plan-ingestion-worker:latest
EC2 run example:
docker run --env-file .env \
  <aws_account_id>.dkr.ecr.<region>.amazonaws.com/plan-ingestion-worker:latest \
  python scripts/run_ingestion.py --project project_001
AWS Batch path
Do not start with Batch.
Start Batch only after Docker worker is stable on EC2.
Batch setup:
ECR image already exists.
AWS Batch compute environment created.
Job queue created.
Job definition created using ingestion Docker image.
Each Batch job processes one project.
Job receives PROJECT_SLUG or project id as environment variable.
Batch max vCPU limit is set to control cost.
CloudWatch logs enabled.
Failed jobs are visible and retryable.
Batch job command:
python scripts/run_ingestion.py --project ${PROJECT_SLUG}
Recommended Batch rollout:
1 test project
3 projects
10 projects
50 projects
Do not run 50 first.
50-project dataset plan
After Phase 0 and Phase 1 are stable:
Select 50 projects from Supabase.
Import/copy raw PDFs into S3.
Process in controlled batches.
Generate reports.
Sample overlays.
Verify extraction quality.
Freeze dataset version v0.
Create dataset manifest:
datasets/page_dataset_v0/manifest.jsonl
Each row should include:
{
  "project_id": "uuid",
  "project_slug": "project_001",
  "file_id": "uuid",
  "page_id": "uuid",
  "pdf_page_number": 1,
  "page_image_s3_key": "processed/project_001/a_set/pages/page_001.png",
  "thumbnail_s3_key": "processed/project_001/a_set/thumbnails/page_001_thumb.jpg",
  "text_json_s3_key": "processed/project_001/a_set/text/page_001_text.json",
  "vector_json_s3_key": "processed/project_001/a_set/vectors/page_001_vectors.json",
  "overlay_s3_key": "processed/project_001/a_set/overlays/page_001_overlay.png",
  "page_representation_type": "digital_text_vector_page",
  "text_block_count": 438,
  "vector_entity_count": 18240
}
What not to build in this data pipeline doc
Do not build yet:
page classifier
model training
labeling UI
finish extraction
takeoff
square footage
Google Sheets export
OCR/Textract
Claude API extraction
estimator UI
Those come after the data foundation is stable.
Checkpoints
Checkpoint A: Phase 0 pass
Must pass before AWS build.
Required:
local PDF import works
spike_coordinates.py works
overlays align
coordinate_transform_json saved
dense/rotated pages handled
Checkpoint B: Phase 1 local/AWS pass
Must pass before Docker/EC2 scale.
Required:
S3 raw import works
RDS schema works
full project ingestion works
artifacts uploaded
reports generated
rerun is idempotent
Checkpoint C: Docker/EC2 pass
Must pass before Batch.
Required:
Docker image runs same pipeline
EC2 can run one project
S3/RDS permissions work
logs/errors visible
Checkpoint D: Batch pass
Must pass before 50-project run.
Required:
one Batch job passes
3–5 project Batch test passes
costs controlled
failures retryable
Checkpoint E: 50-project dataset ready
Required:
50 projects processed
artifacts exist
RDS metadata complete
reports clean enough
dataset manifest created
ready for labeling/model work

