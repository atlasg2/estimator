-- v4.0 Page Purpose Classifier labels. NON-DESTRUCTIVE (CREATE TABLE / INDEX IF NOT EXISTS only).
-- v3 tables (project_labels / document_labels / page_labels) are left untouched.
-- v4 labels live as one JSONB document per row; shape/enums are validated in code
-- (a JSON schema), NOT as rigid DB columns, so enum tweaks during the bootstrap need no migration.
-- Claude + verifier + human_reviewed labels COEXIST (distinguished by label_source); never overwrite.

-- ---- project-level v4 labels ----
CREATE TABLE IF NOT EXISTS v4_project_labels (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    permit_number TEXT NOT NULL,
    label_source  TEXT NOT NULL,                 -- claude | verifier | human_reviewed | model
    spec_version  TEXT NOT NULL DEFAULT 'v4.0',
    reviewed      BOOLEAN NOT NULL DEFAULT FALSE,
    label         JSONB NOT NULL,                -- full project object (project_profile, sf_readiness, …)
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_v4_project_permit    ON v4_project_labels (permit_number);
CREATE INDEX IF NOT EXISTS idx_v4_project_source    ON v4_project_labels (label_source, reviewed);
CREATE INDEX IF NOT EXISTS idx_v4_project_label_gin ON v4_project_labels USING GIN (label);

-- ---- document-level v4 labels ----
CREATE TABLE IF NOT EXISTS v4_document_labels (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    permit_number TEXT NOT NULL,
    doc_id        TEXT NOT NULL,
    label_source  TEXT NOT NULL,
    spec_version  TEXT NOT NULL DEFAULT 'v4.0',
    reviewed      BOOLEAN NOT NULL DEFAULT FALSE,
    label         JSONB NOT NULL,                -- full document object (disposition, document_category, …)
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_v4_doc_permit    ON v4_document_labels (permit_number, doc_id);
CREATE INDEX IF NOT EXISTS idx_v4_doc_source    ON v4_document_labels (label_source, reviewed);
CREATE INDEX IF NOT EXISTS idx_v4_doc_label_gin ON v4_document_labels USING GIN (label);

-- ---- page-level v4 labels (primary training unit) ----
CREATE TABLE IF NOT EXISTS v4_page_labels (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    permit_number   TEXT NOT NULL,
    doc_id          TEXT NOT NULL,
    pdf_page_number INTEGER,                     -- 1-indexed (human)
    page_index      INTEGER,                     -- 0-indexed (internal)
    label_source    TEXT NOT NULL,
    spec_version    TEXT NOT NULL DEFAULT 'v4.0',
    reviewed        BOOLEAN NOT NULL DEFAULT FALSE,
    label           JSONB NOT NULL,              -- full page object (useful_for, tag_importance, observations, …)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_v4_page_permit    ON v4_page_labels (permit_number, doc_id, pdf_page_number);
CREATE INDEX IF NOT EXISTS idx_v4_page_source    ON v4_page_labels (label_source, reviewed);
CREATE INDEX IF NOT EXISTS idx_v4_page_label_gin ON v4_page_labels USING GIN (label);
