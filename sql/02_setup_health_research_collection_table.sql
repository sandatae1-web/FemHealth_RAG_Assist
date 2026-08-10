CREATE TABLE IF NOT EXISTS health_research_collection (
    collection_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    nct_id TEXT NOT NULL,
    document_id TEXT,
    notes TEXT,
    saved_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_user_health_study
        UNIQUE (user_id, nct_id)
);