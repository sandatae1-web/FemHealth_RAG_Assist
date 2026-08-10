# Health Knowledge Vector Search - Testing Guide

## Overview

The `/health/search` endpoint performs semantic search over the health_documents and health_embeddings tables using vector similarity.

## Architecture

```
User Query
    ↓
POST /health/search
    ↓
embedding_service.py
    ↓
generate_query_embedding()
    ↓
sentence-transformers/all-MiniLM-L6-v2 (384-dim)
    ↓
vector_search_service.py
    ↓
Lakebase Postgres (pgvector)
    ↓
health_embeddings ← vector_cosine_ops → JOIN → health_documents
    ↓
JSON Response
```

## Endpoint

**URL**: `POST /health/search`

**Content-Type**: `application/json`

## Request Format

### Required Fields
* `query` (string) - Natural language search query

### Optional Fields
* `top_k` (integer) - Number of results to return (default: 5, max: 100)

### Example Request

```json
{
  "query": "menopause studies related to sleep problems",
  "top_k": 5
}
```

## Response Format

```json
{
  "query": "menopause studies related to sleep problems",
  "top_k": 5,
  "count": 5,
  "results": [
    {
      "document_id": "doc_001",
      "nct_id": "NCT01234567",
      "title": "Study of Menopause and Sleep Quality",
      "condition": "Menopause",
      "summary": "This study investigates...",
      "chunk_text": "The relevant chunk of text...",
      "chunk_index": 0,
      "similarity": 0.89,
      "study_status": "RECRUITING",
      "sex": "FEMALE",
      "age_range": "45 Years - 65 Years",
      "sponsor": "University Medical Center",
      "locations": "Boston, MA United States",
      "source": "ClinicalTrials.gov",
      "source_url": "https://clinicaltrials.gov/study/NCT01234567"
    }
  ]
}
```

## Error Responses

### 400 Bad Request - Missing Body
```json
{
  "error": "Request body is required"
}
```

### 400 Bad Request - Missing Query
```json
{
  "error": "query is required"
}
```

### 400 Bad Request - Invalid top_k
```json
{
  "error": "top_k must be between 1 and 100"
}
```

### 500 Internal Server Error
```json
{
  "error": "Unable to search health knowledge"
}
```

## Testing with curl

### Basic Search
```bash
curl -X POST http://localhost:8000/health/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "menopause and hot flashes"
  }'
```

### Custom top_k
```bash
curl -X POST http://localhost:8000/health/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "endometriosis treatment options",
    "top_k": 10
  }'
```

### Complex Query
```bash
curl -X POST http://localhost:8000/health/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "PCOS and insulin resistance in young women",
    "top_k": 5
  }'
```

## Testing with Python

```python
import requests

response = requests.post(
    "http://localhost:8000/health/search",
    json={
        "query": "postpartum depression risk factors",
        "top_k": 5
    }
)

data = response.json()
print(f"Found {data['count']} results")

for result in data['results']:
    print(f"- {result['title']} (similarity: {result['similarity']:.2f})")
    print(f"  NCT ID: {result['nct_id']}")
    print(f"  Condition: {result['condition']}")
    print()
```

## Prerequisites

1. **Lakebase Tables Created**
   - Run `sql/03_setup_health_documents_table.sql`
   - Run `sql/04_setup_health_embeddings_table.sql`

2. **Data Ingested**
   - Run `notebooks/ingest_health_documents_embeddings` notebook
   - This populates both health_documents and health_embeddings tables

3. **Dependencies Installed**
   - `pip install sentence-transformers` (already in requirements.txt)
   - Model will be cached in `/tmp/.cache/huggingface` on first use

## Performance Notes

* **First Request**: ~2-3 seconds (model loading)
* **Subsequent Requests**: ~100-300ms (model cached)
* **Vector Index**: Uses HNSW index for fast cosine similarity search
* **Model**: sentence-transformers/all-MiniLM-L6-v2 (384 dimensions, ~90MB)

## Similarity Scores

Scores range from 0.0 to 1.0:
* **0.9+**: Highly relevant
* **0.7-0.9**: Relevant
* **0.5-0.7**: Somewhat relevant
* **<0.5**: Less relevant

The endpoint returns all results above similarity threshold 0.0 and lets the client filter by score.

## Next Steps

Integrate this endpoint into the FemLens frontend:
1. Update the UI to call `/health/search` instead of `/api/ask`
2. Display results with similarity scores
3. Allow users to adjust top_k value
4. Add similarity threshold filtering in the UI
