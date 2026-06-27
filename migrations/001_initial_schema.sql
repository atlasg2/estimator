-- Phase 1 ingestion schema (RDS Postgres)
-- Mirrors data-pipeline-plan.md. Idempotent: safe to re-run.

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
