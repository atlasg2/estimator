-- V1 labeling schema. Versioned, separate from extracted artifacts so labels can be
-- re-run/improved without touching the data. Claude, verifier, and HUMAN labels coexist,
-- distinguished by label_source, so we can compare model vs human (the training signal).

CREATE TABLE IF NOT EXISTS classification_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_label TEXT NOT NULL,              -- e.g. 'v1-gate1'
    stage TEXT,                            -- 'v1a-claude' | 'verify' | 'human'
    model TEXT,                            -- model / agent id
    prompt_version TEXT,                   -- project-packet-builder version
    started_at TIMESTAMPTZ DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT DEFAULT 'running',
    metadata_json JSONB,
    notes TEXT
);

-- project-level decision: keep / delete / unknown_review_needed
CREATE TABLE IF NOT EXISTS project_labels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    classification_run_id UUID REFERENCES classification_runs(id) ON DELETE CASCADE,
    permit_num TEXT NOT NULL,
    decision TEXT NOT NULL,                -- keep | delete | unknown_review_needed
    confidence TEXT,                       -- high | medium | low
    evidence_text TEXT,
    reason TEXT,
    needs_review BOOLEAN NOT NULL DEFAULT FALSE,
    label_source TEXT NOT NULL DEFAULT 'claude',   -- claude | verifier | human | model
    created_at TIMESTAMPTZ DEFAULT now()
);

-- document-level disposition: process / raw_only / unknown_review_needed
CREATE TABLE IF NOT EXISTS document_labels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    classification_run_id UUID REFERENCES classification_runs(id) ON DELETE CASCADE,
    permit_num TEXT NOT NULL,
    doc_id TEXT NOT NULL,                  -- portal DocID
    doc_name TEXT,
    disposition TEXT NOT NULL,             -- process | raw_only | unknown_review_needed
    confidence TEXT,
    evidence_text TEXT,
    reason TEXT,
    needs_review BOOLEAN NOT NULL DEFAULT FALSE,
    label_source TEXT NOT NULL DEFAULT 'claude',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- page-level labels (the training target)
CREATE TABLE IF NOT EXISTS page_labels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    classification_run_id UUID REFERENCES classification_runs(id) ON DELETE CASCADE,
    permit_num TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    page_id UUID,                          -- nullable: FK to plan_pages once extracted
    pdf_page_number INTEGER NOT NULL,
    sheet_number TEXT,
    sheet_title TEXT,
    -- critical_flooring | useful_flooring | maybe_flooring | not_flooring | unknown_review_needed
    page_usefulness TEXT,
    -- finish_floor_plan | finish_schedule_or_legend | project_manual_or_spec | flooring_detail |
    -- title_or_project_info | general_notes | architectural_other | not_relevant | unknown
    page_role TEXT,
    flooring_relevant TEXT,                -- true | false | unknown
    confidence TEXT,
    evidence_text TEXT,
    needs_review BOOLEAN NOT NULL DEFAULT FALSE,
    label_source TEXT NOT NULL DEFAULT 'claude',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_project_labels_permit ON project_labels(permit_num);
CREATE INDEX IF NOT EXISTS idx_project_labels_source ON project_labels(label_source);
CREATE INDEX IF NOT EXISTS idx_document_labels_permit ON document_labels(permit_num);
CREATE INDEX IF NOT EXISTS idx_page_labels_permit ON page_labels(permit_num);
CREATE INDEX IF NOT EXISTS idx_page_labels_source ON page_labels(label_source);
CREATE INDEX IF NOT EXISTS idx_page_labels_review ON page_labels(needs_review);
CREATE INDEX IF NOT EXISTS idx_page_labels_role ON page_labels(page_role);
