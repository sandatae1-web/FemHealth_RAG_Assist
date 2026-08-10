
# Complete Health Documents Ingestion and Embedding Pipeline
# This script contains all the logic for the health data ingestion notebook

# ============================================================================
# Part 1: Database Connection Setup
# ============================================================================

import base64
from urllib.parse import urlparse
from databricks.sdk import WorkspaceClient
import psycopg2

w = WorkspaceClient()

def get_lakebase_url() -> str:
    secret = w.secrets.get_secret(scope="database", key="lakebase-url")
    return base64.b64decode(secret.value).decode("utf-8")

lakebase_url = get_lakebase_url()
parsed = urlparse(lakebase_url)

db_host = parsed.hostname
db_port = parsed.port or 5432
db_name = parsed.path.lstrip("/")
db_user = parsed.username
db_password = parsed.password

print(f"Connection: {db_host}:{db_port}/{db_name} as {db_user}")

# ============================================================================
# Part 2: Fetch Women's Health Studies from ClinicalTrials.gov
# ============================================================================

import sys
import os

sys.path.insert(0, "/Workspace/Users/san.datae2@gmail.com/FemHealth_RAG_Assist")
os.environ["CLINICALTRIALS_API_BASE_URL"] = API_BASE_URL

from health_client import HealthClient

client = HealthClient(base_url=API_BASE_URL, rate_limit_delay=RATE_LIMIT_DELAY)

print(f"Fetching women's health studies (max: {MAX_STUDIES or 'unlimited'})...")
studies = []

for study in client.get_womens_health_studies(max_results=MAX_STUDIES):
    studies.append(study)
    if len(studies) % 10 == 0:
        print(f"  Fetched {len(studies)} studies...")

print(f"Total studies fetched: {len(studies)}")

# ============================================================================
# Part 3: Transform API Response to Document Structure
# ============================================================================

import json
from datetime import datetime

def safe_get(obj, *keys, default=None):
    """Safely navigate nested dict/list structures."""
    result = obj
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
        elif isinstance(result, list) and isinstance(key, int) and len(result) > key:
            result = result[key]
        else:
            return default
        if result is None:
            return default
    return result

def extract_locations(study):
    """Extract location information as a JSON string."""
    locations = []
    protocol = safe_get(study, "protocolSection", default={})
    locs = safe_get(protocol, "contactsLocationsModule", "locations", default=[])
    
    for loc in locs:
        locations.append({
            "city": safe_get(loc, "city"),
            "state": safe_get(loc, "state"),
            "country": safe_get(loc, "country")
        })
    
    return json.dumps(locations) if locations else None

def transform_study_to_document(study):
    """Transform a ClinicalTrials.gov study into a health_documents row."""
    protocol = safe_get(study, "protocolSection", default={})
    
    nct_id = safe_get(protocol, "identificationModule", "nctId")
    brief_title = safe_get(protocol, "identificationModule", "briefTitle", default="")
    official_title = safe_get(protocol, "identificationModule", "officialTitle")
    title = official_title or brief_title or "Untitled Study"
    
    conditions = safe_get(protocol, "conditionsModule", "conditions", default=[])
    condition = ", ".join(conditions) if conditions else None
    
    brief_summary = safe_get(protocol, "descriptionModule", "briefSummary")
    detailed_desc = safe_get(protocol, "descriptionModule", "detailedDescription")
    
    full_text_parts = [title]
    if brief_summary:
        full_text_parts.append(brief_summary)
    if detailed_desc:
        full_text_parts.append(detailed_desc)
    full_text = "\n\n".join(full_text_parts)
    
    status = safe_get(protocol, "statusModule", "overallStatus")
    sex = safe_get(protocol, "eligibilityModule", "sex")
    min_age = safe_get(protocol, "eligibilityModule", "minimumAge")
    max_age = safe_get(protocol, "eligibilityModule", "maximumAge")
    sponsor_name = safe_get(protocol, "sponsorCollaboratorsModule", "leadSponsor", "name")
    locations = extract_locations(study)
    last_update = safe_get(protocol, "statusModule", "lastUpdatePostDateStruct", "date")
    source_url = f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else None
    document_id = nct_id or f"study_{hash(json.dumps(study))}"
    
    return {
        "document_id": document_id,
        "nct_id": nct_id,
        "title": title,
        "condition": condition,
        "document_type": "clinical_trial",
        "source_url": source_url,
        "summary": brief_summary,
        "full_text": full_text,
        "study_status": status,
        "sex": sex,
        "minimum_age": min_age,
        "maximum_age": max_age,
        "sponsor_name": sponsor_name,
        "locations": locations,
        "source_name": "ClinicalTrials.gov",
        "source_updated_at": last_update,
    }

documents = [transform_study_to_document(s) for s in studies]
print(f"Transformed {len(documents)} studies")

# ============================================================================
# Part 4: Insert Documents into Lakebase
# ============================================================================

if documents:
    conn = psycopg2.connect(
        host=db_host, port=db_port, dbname=db_name,
        user=db_user, password=db_password, sslmode="require"
    )
    
    try:
        cursor = conn.cursor()
        insert_data = [
            (d["document_id"], d["nct_id"], d["title"], d["condition"],
             d["document_type"], d["source_url"], d["summary"], d["full_text"],
             d["study_status"], d["sex"], d["minimum_age"], d["maximum_age"],
             d["sponsor_name"], d["locations"], d["source_name"], d["source_updated_at"])
            for d in documents
        ]
        
        insert_sql = f"""
            INSERT INTO {HEALTH_DOCUMENTS_TABLE_NAME} (
                document_id, nct_id, title, condition, document_type, source_url,
                summary, full_text, study_status, sex, minimum_age, maximum_age,
                sponsor_name, locations, source_name, source_updated_at,
                created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (document_id) DO UPDATE SET
                title = EXCLUDED.title,
                full_text = EXCLUDED.full_text,
                updated_at = CURRENT_TIMESTAMP
        """
        
        cursor.executemany(insert_sql, insert_data)
        conn.commit()
        print(f"✅ Upserted {cursor.rowcount} documents")
    finally:
        cursor.close()
        conn.close()

# ============================================================================
# Part 5: Load Documents and Chunk for Embedding
# ============================================================================

import pandas as pd

# Load documents
conn = psycopg2.connect(
    host=db_host, port=db_port, dbname=db_name,
    user=db_user, password=db_password, sslmode="require"
)

docs_df = pd.read_sql(
    f"SELECT document_id, full_text FROM {HEALTH_DOCUMENTS_TABLE_NAME}",
    conn
)
conn.close()

print(f"Loaded {len(docs_df)} documents")

# Chunk documents
chunks_data = []
for _, row in docs_df.iterrows():
    doc_id = row["document_id"]
    text = row["full_text"] or ""
    
    for chunk_idx, start in enumerate(range(0, len(text), CHUNK_SIZE - CHUNK_OVERLAP)):
        chunk_text = text[start : start + CHUNK_SIZE].strip()
        if chunk_text:
            chunks_data.append({
                "embedding_id": f"{doc_id}_chunk_{chunk_idx}",
                "document_id": doc_id,
                "chunk_index": chunk_idx,
                "chunk_text": chunk_text
            })
        if start + CHUNK_SIZE >= len(text):
            break

chunks_df = pd.DataFrame(chunks_data)
print(f"Created {len(chunks_df)} chunks")

# ============================================================================
# Part 6: Compute Embeddings
# ============================================================================

import os
from sentence_transformers import SentenceTransformer

os.environ["HF_HOME"] = "/tmp/.cache/huggingface"
os.environ["TRANSFORMERS_CACHE"] = "/tmp/.cache/huggingface"

model = SentenceTransformer(EMBEDDING_MODEL_NAME, cache_folder="/tmp/.cache/huggingface")

batch_size = 32
all_embeddings = []

for i in range(0, len(chunks_df), batch_size):
    batch = chunks_df.iloc[i:i+batch_size]
    vectors = model.encode(batch["chunk_text"].tolist(), show_progress_bar=False)
    all_embeddings.extend(vectors.tolist())
    if (i + batch_size) % 128 == 0:
        print(f"  Processed {min(i + batch_size, len(chunks_df))}/{len(chunks_df)} chunks")

chunks_df["embedding"] = all_embeddings
chunks_df["model_name"] = EMBEDDING_MODEL_NAME
print(f"Computed {len(chunks_df)} embeddings")

# ============================================================================
# Part 7: Insert Embeddings into Lakebase
# ============================================================================

if len(chunks_df) > 0:
    conn = psycopg2.connect(
        host=db_host, port=db_port, dbname=db_name,
        user=db_user, password=db_password, sslmode="require"
    )
    
    try:
        cursor = conn.cursor()
        insert_data = [
            (
                row["embedding_id"],
                row["document_id"],
                int(row["chunk_index"]),
                row["chunk_text"],
                "{" + ",".join(str(float(x)) for x in row["embedding"]) + "}",
                row["model_name"]
            )
            for _, row in chunks_df.iterrows()
        ]
        
        insert_sql = f"""
            INSERT INTO {HEALTH_EMBEDDINGS_TABLE_NAME} (
                embedding_id, document_id, chunk_index, chunk_text,
                embedding, model_name, created_at
            ) VALUES (%s, %s, %s, %s, %s::double precision[], %s, CURRENT_TIMESTAMP)
            ON CONFLICT (embedding_id) DO NOTHING
        """
        
        cursor.executemany(insert_sql, insert_data)
        conn.commit()
        print(f"✅ Inserted {cursor.rowcount} embeddings")
        print("\nIMPORTANT: Run this SQL to cast arrays to vectors:")
        print(f"  UPDATE {HEALTH_EMBEDDINGS_TABLE_NAME} SET embedding = embedding::vector;")
    finally:
        cursor.close()
        conn.close()

print("\n✅ Health data ingestion and embedding pipeline complete!")
