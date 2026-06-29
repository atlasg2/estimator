-- Candidate registry: the resumable pool of permits we're considering.
-- One row = one PERMIT (project), NOT a document.
-- Curated columns (readable at a glance) + permit_json (the whole raw row, fallback).

CREATE TABLE IF NOT EXISTS candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    permit_num TEXT UNIQUE NOT NULL,
    code TEXT,                         -- RNVS / RNVN / NEWC ...
    ref TEXT,                          -- portal SearchString
    est_cost NUMERIC,                  -- curated, readable
    sqft NUMERIC,
    address TEXT,
    description TEXT,
    fit_category TEXT,                 -- fitness/retail/restaurant/office/residential (hint)
    -- lifecycle: candidate -> discovered -> rejected | downloaded -> processed
    status TEXT NOT NULL DEFAULT 'candidate',
    permit_json JSONB,                 -- the WHOLE raw permit row (everything, for later)
    documents_json JSONB,              -- [{docId, name, selected:bool}] once discovered
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status);
CREATE INDEX IF NOT EXISTS idx_candidates_code ON candidates(code);
