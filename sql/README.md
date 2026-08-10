# SQL Setup Files for Lakebase

These SQL files must be run manually in your Lakebase Postgres database before running the `ingest_ticker_news_embeddings` notebook.

## Setup Order

### 1. Run `01_setup_news_table.sql`
Creates the `ticker_news_documents` table for storing raw news articles from the Massive API.

### 2. Run `02_setup_embeddings_table.sql`
Creates the `ticker_news_embeddings` table with pgvector support.

**IMPORTANT:** Replace `{{EMBEDDING_DIM}}` with your model's dimension:
* `sentence-transformers/all-MiniLM-L6-v2`: 384
* `sentence-transformers/all-mpnet-base-v2`: 768
* `BAAI/bge-small-en-v1.5`: 384
* `BAAI/bge-base-en-v1.5`: 768
* `BAAI/bge-large-en-v1.5`: 1024

### 3. Run `03_setup_chunk_embeddings_table.sql`
Creates the `ticker_news_chunk_embeddings` table for article content chunks.

**IMPORTANT:** Replace `{{EMBEDDING_DIM}}` with the same dimension as step 2.

### 4. Run `03_setup_health_documents_table.sql`
Creates the `health_documents` table for storing clinical trial documents from ClinicalTrials.gov.

### 5. Run `04_setup_health_embeddings_table.sql`
Creates the `health_embeddings` table with pgvector support for chunked health document embeddings.

**Note:** This table uses VECTOR(1536) for OpenAI embeddings. If using a different model, update the dimension in the SQL file.

## Post-Processing (After Notebook Execution)

### 6. Cast Arrays to Vectors

After the notebook writes embeddings, you need to cast the DOUBLE PRECISION arrays to VECTOR type.

Run these commands in your Lakebase database (add similar commands for health_embeddings as needed):

```
UPDATE ticker_news_embeddings SET embedding = embedding::vector WHERE embedding IS NOT NULL;
UPDATE ticker_news_chunk_embeddings SET embedding = embedding::vector WHERE embedding IS NOT NULL;
```

Verify with:
```
SELECT 'ticker_news_embeddings', COUNT(*), COUNT(embedding) FROM ticker_news_embeddings
UNION ALL
SELECT 'ticker_news_chunk_embeddings', COUNT(*), COUNT(embedding) FROM ticker_news_chunk_embeddings
UNION ALL
SELECT 'health_embeddings', COUNT(*), COUNT(embedding) FROM health_embeddings;
```

## Why Manual Setup?

The notebook uses **Spark JDBC only** (no psycopg2) to avoid kernel crashes on Serverless compute. Spark JDBC has limitations:
* Cannot execute arbitrary DDL (CREATE EXTENSION, CREATE INDEX)
* Cannot write to pgvector's VECTOR type directly
* Cannot use ON CONFLICT for upserts

By running setup SQL manually, you get:
* ✅ Proper pgvector VECTOR columns
* ✅ HNSW indexes for fast similarity search  
* ✅ Stable notebook execution (no psycopg2 crashes)
* ✅ Idempotent writes (deduplication via left anti-join)