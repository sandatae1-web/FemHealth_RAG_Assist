CREATE TABLE IF NOT EXISTS health_search_history (
    search_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    search_query TEXT NOT NULL,
    search_type TEXT NOT NULL,
    filters JSONB,
    result_count INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);