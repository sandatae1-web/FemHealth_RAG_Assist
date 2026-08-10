# SQL Setup Files for FemLens — Women's Health Research Companion

These SQL files must be run manually in your Lakebase Postgres database before running the FemLens application and the `ingest_health_document_embeddings` notebook.

## Setup Order

### 1. Run `01_setup_health_search_history _table.sql`
Creates the `health_search_history` table for tracking user research queries.

**Table:** `health_search_history`
- Stores user search queries and timestamps
- Used for dashboard analytics and research activity tracking

### 2. Run `02_setup_health_research_collection_table.sql`
Creates the `health_research_collection` table for storing user-saved clinical studies.

**Table:** `health_research_collection`
- User's personal collection of saved studies
- Includes NCT ID, notes, and saved timestamps
- Powers the "My Research Collection" feature

### 3. Run `03_setup_health_documents_table.sql`
Creates the `health_documents` table for storing clinical trial documents from ClinicalTrials.gov.

**Table:** `health_documents`
- Stores clinical trial metadata (title, summary, status, conditions, etc.)
- Source data from ClinicalTrials.gov API
- Foundation for semantic search

### 4. Run `04_setup_health_embeddings_table.sql`
Creates the `health_embeddings` table with pgvector support for chunked health document embeddings.

**Table:** `health_embeddings`
- Stores vector embeddings for semantic search
- Each row represents a text chunk from a clinical study
- Uses pgvector extension for similarity search

**IMPORTANT:** Update the vector dimension based on your embedding model:
* `sentence-transformers/all-MiniLM-L6-v2`: **384** (default)
* `sentence-transformers/all-mpnet-base-v2`: 768
* `text-embedding-ada-002` (OpenAI): 1536
* `BAAI/bge-small-en-v1.5`: 384
* `BAAI/bge-base-en-v1.5`: 768

## Post-Processing (After Notebook Execution)

### 5. Cast Arrays to Vectors

After the `ingest_health_document_embeddings` notebook writes embeddings, you need to cast the DOUBLE PRECISION arrays to VECTOR type.

Run this command in your Lakebase database:

```sql
UPDATE health_embeddings 
SET embedding = embedding::vector 
WHERE embedding IS NOT NULL;
```

### 6. Verify Setup

Verify all tables are populated correctly:

```sql
-- Check all health tables
SELECT 'health_documents' as table_name, COUNT(*) as total_rows 
FROM health_documents
UNION ALL
SELECT 'health_embeddings', COUNT(*) 
FROM health_embeddings
UNION ALL
SELECT 'health_embeddings (with vectors)', COUNT(embedding) 
FROM health_embeddings
UNION ALL
SELECT 'health_search_history', COUNT(*) 
FROM health_search_history
UNION ALL
SELECT 'health_research_collection', COUNT(*) 
FROM health_research_collection;
```

## Why Manual Setup?

The FemLens ingestion notebook uses **Spark JDBC only** (no psycopg2) to avoid kernel crashes on Databricks Serverless compute. Spark JDBC has limitations:
* Cannot execute arbitrary DDL (`CREATE EXTENSION`, `CREATE INDEX`)
* Cannot write to pgvector's `VECTOR` type directly
* Cannot use `ON CONFLICT` for upserts

By running setup SQL manually, you get:
* ✅ Proper pgvector `VECTOR` columns for embeddings
* ✅ HNSW indexes for fast similarity search  
* ✅ Stable notebook execution (no psycopg2 crashes)
* ✅ Idempotent writes (deduplication via left anti-join)
* ✅ User-specific tables for search history and collections

## FemLens Database Architecture

```
health_documents (source data)
        ↓
    [Chunking + Embedding]
        ↓
health_embeddings (vectors) ← [Semantic Search]
        ↓
    [Flask API]
        ↓
health_search_history (analytics)
health_research_collection (user data)
```

## Quick Start

1. Run SQL files 1-4 in order in your Lakebase database
2. Run the `ingest_health_document_embeddings` notebook
3. Cast embeddings to vectors (step 5)
4. Verify setup (step 6)
5. Start the FemLens Flask app: `python app.py`