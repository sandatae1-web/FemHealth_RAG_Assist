-- Setup script for health_documents table
-- Run this manually in your Lakebase Postgres database before running the notebook

-- Create the health documents table
CREATE TABLE IF NOT EXISTS health_documents (
    document_id TEXT PRIMARY KEY,
    nct_id TEXT,
    title TEXT NOT NULL,
    condition TEXT,
    document_type TEXT,
    source_url TEXT,
    summary TEXT,
    full_text TEXT NOT NULL,
    study_status TEXT,
    sex TEXT,
    minimum_age TEXT,
    maximum_age TEXT,
    sponsor_name TEXT,
    locations TEXT,
    source_name TEXT NOT NULL DEFAULT 'ClinicalTrials.gov',
    source_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Create index for NCT ID lookups
CREATE INDEX IF NOT EXISTS idx_health_documents_nct_id 
ON health_documents (nct_id);

-- Create index for condition lookups
CREATE INDEX IF NOT EXISTS idx_health_documents_condition 
ON health_documents (condition);

-- Create index for document type
CREATE INDEX IF NOT EXISTS idx_health_documents_type 
ON health_documents (document_type);

-- Verify the table was created
SELECT 
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name = 'health_documents'
ORDER BY ordinal_position;