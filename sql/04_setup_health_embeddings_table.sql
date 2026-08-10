-- Setup script for health_embeddings table
-- Run this manually in your Lakebase Postgres database before running the notebook
-- This table uses VECTOR(1536) for OpenAI text-embedding-ada-002 or similar models

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the embeddings table
-- IMPORTANT: Vector dimension is set to 1536 for OpenAI embeddings
-- If using a different model, update the dimension:
--   - sentence-transformers/all-MiniLM-L6-v2: 384
--   - sentence-transformers/all-mpnet-base-v2: 768
--   - text-embedding-ada-002 (OpenAI): 1536
--   - text-embedding-3-small (OpenAI): 1536
CREATE TABLE IF NOT EXISTS health_embeddings (
    embedding_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding VECTOR(384) NOT NULL,
    model_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT fk_health_embedding_document
        FOREIGN KEY (document_id)
        REFERENCES health_documents(document_id)
        ON DELETE CASCADE,

    CONSTRAINT uq_health_document_chunk
        UNIQUE (document_id, chunk_index)
);

-- Create HNSW index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS idx_health_embeddings_embedding
ON health_embeddings
USING hnsw (embedding vector_cosine_ops);

-- Create index for document lookups
CREATE INDEX IF NOT EXISTS idx_health_embeddings_document_id
ON health_embeddings (document_id);

-- Verify the table was created
SELECT 
    table_name,
    column_name,
    data_type,
    udt_name
FROM information_schema.columns
WHERE table_name = 'health_embeddings'
ORDER BY ordinal_position;