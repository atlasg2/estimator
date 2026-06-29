-- v3.0 label fields. Non-destructive: only ADD COLUMN IF NOT EXISTS. Old labels untouched.
-- page_role/page_usefulness/etc. are TEXT (no enums), so new role values need no migration.

-- project_labels
ALTER TABLE project_labels ADD COLUMN IF NOT EXISTS candidate_id TEXT;
ALTER TABLE project_labels ADD COLUMN IF NOT EXISTS primary_reason_code TEXT;
ALTER TABLE project_labels ADD COLUMN IF NOT EXISTS reason_codes JSONB;
ALTER TABLE project_labels ADD COLUMN IF NOT EXISTS reason_text TEXT;
ALTER TABLE project_labels ADD COLUMN IF NOT EXISTS reviewed BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE project_labels ADD COLUMN IF NOT EXISTS spec_version TEXT;

-- document_labels
ALTER TABLE document_labels ADD COLUMN IF NOT EXISTS document_category TEXT;
ALTER TABLE document_labels ADD COLUMN IF NOT EXISTS primary_reason_code TEXT;
ALTER TABLE document_labels ADD COLUMN IF NOT EXISTS reason_codes JSONB;
ALTER TABLE document_labels ADD COLUMN IF NOT EXISTS reason_text TEXT;
ALTER TABLE document_labels ADD COLUMN IF NOT EXISTS reviewed BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE document_labels ADD COLUMN IF NOT EXISTS spec_version TEXT;

-- page_labels
ALTER TABLE page_labels ADD COLUMN IF NOT EXISTS document_id UUID;
ALTER TABLE page_labels ADD COLUMN IF NOT EXISTS filename TEXT;
ALTER TABLE page_labels ADD COLUMN IF NOT EXISTS page_index INTEGER;
ALTER TABLE page_labels ADD COLUMN IF NOT EXISTS primary_reason_code TEXT;
ALTER TABLE page_labels ADD COLUMN IF NOT EXISTS reason_codes JSONB;
ALTER TABLE page_labels ADD COLUMN IF NOT EXISTS reason_text TEXT;
ALTER TABLE page_labels ADD COLUMN IF NOT EXISTS evidence_keywords JSONB;
ALTER TABLE page_labels ADD COLUMN IF NOT EXISTS input_tier TEXT;
ALTER TABLE page_labels ADD COLUMN IF NOT EXISTS reviewed BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE page_labels ADD COLUMN IF NOT EXISTS spec_version TEXT;
