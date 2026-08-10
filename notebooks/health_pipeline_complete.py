
# ============================================================================
# HEALTH DOCUMENTS TRANSFORMATION, INSERTION, AND EMBEDDING PIPELINE
# This code handles:
# 1. Transforming API responses to document structure
# 2. Inserting documents into health_documents table
# 3. Loading documents and chunking for embeddings
# 4. Computing embeddings
# 5. Inserting embeddings into health_embeddings table
# ============================================================================

import json
import psycopg2
import pandas as pd
from datetime import datetime

# ---------------------------------------------------------------------------
# PART 1: Document Transformation Functions
# ---------------------------------------------------------------------------

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
    """Extract location information as JSON."""
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
    """Transform ClinicalTrials.gov study to health_documents row."""
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
    
    return {
        "document_id": nct_id or f"study_{hash(json.dumps(study))}",
        "nct_id": nct_id,
        "title": title,
        "condition": condition,
        "document_type": "clinical_trial",
        "source_url": f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else None,
        "summary": brief_summary,
        "full_text": full_text,
        "study_status": safe_get(protocol, "statusModule", "overallStatus"),
        "sex": safe_get(protocol, "eligibilityModule", "sex"),
        "minimum_age": safe_get(protocol, "eligibilityModule", "minimumAge"),
        "maximum_age": safe_get(protocol, "eligibilityModule", "maximumAge"),
        "sponsor_name": safe_get(protocol, "sponsorCollaboratorsModule", "leadSponsor", "name"),
        "locations": extract_locations(study),
        "source_name": "ClinicalTrials.gov",
        "source_updated_at": safe_get(protocol, "statusModule", "lastUpdatePostDateStruct", "date"),
    }

# Transform studies
print(f"Transforming {len(studies)} studies...")
documents = [transform_study_to_document(s) for s in studies]
print(f"✅ Transformed {len(documents)} documents")

# ---------------------------------------------------------------------------
# PART 2: Insert Documents
# ---------------------------------------------------------------------------

if documents:
    print(f"\nInserting {len(documents)} documents...")
    conn = psycopg2.connect(
        host=db_host, port=db_port, dbname=db_name,
        user=db_user, password=db_password, sslmode="require"
    )
    
    try:
        cursor = conn.cursor()
        insert_data = [(d["document_id"], d["nct_id"], d["title"], d["condition"],
                       d["document_type"], d["source_url"], d["summary"], d["full_text"],
                       d["study_status"], d["sex"], d["minimum_age"], d["maximum_age"],
                       d["sponsor_name"], d["locations"], d["source_name"], d["source_updated_at"])
                      for d in documents]
        
        insert_sql = f"""
            INSERT INTO {HEALTH_DOCUMENTS_TABLE_NAME} (
                document_id, nct_id, title, condition, document_type, source_url,
                summary, full_text, study_status, sex, minimum_age, maximum_age,
                sponsor_name, locations, source_name, source_updated_at,
                created_at, updated_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
            ON CONFLICT (document_id) DO UPDATE SET
                title=EXCLUDED.title, full_text=EXCLUDED.full_text, updated_at=CURRENT_TIMESTAMP
        """
        
        cursor.executemany(insert_sql, insert_data)
        conn.commit()
        print(f"✅ Upserted {cursor.rowcount} documents")
    finally:
        cursor.close()
        conn.close()

# ---------------------------------------------------------------------------
# PART 3: Load Documents and Create Chunks
# ---------------------------------------------------------------------------

print(f"\nLoading documents from {HEALTH_DOCUMENTS_TABLE_NAME}...")
conn = psycopg2.connect(
    host=db_host, port=db_port, dbname=db_name,
    user=db_user, password=db_password, sslmode="require"
)
docs_df = pd.read_sql(f"SELECT document_id, full_text FROM {HEALTH_DOCUMENTS_TABLE_NAME}", conn)
conn.close()
print(f"Loaded {len(docs_df)} documents")

print(f"\nChunking documents (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})...")
chunks_data = []
for _, row in docs_df.iterrows():
    doc_id, text = row["document_id"], row["full_text"] or ""
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
print(f"✅ Created {len(chunks_df)} chunks")

# ---------------------------------------------------------------------------
# PART 4: Compute Embeddings
# ---------------------------------------------------------------------------

import os
from sentence_transformers import SentenceTransformer

os.environ["HF_HOME"] = "/tmp/.cache/huggingface"
os.environ["TRANSFORMERS_CACHE"] = "/tmp/.cache/huggingface"

print(f"\nLoading embedding model {EMBEDDING_MODEL_NAME}...")
model = SentenceTransformer(EMBEDDING_MODEL_NAME, cache_folder="/tmp/.cache/huggingface")

print(f"Computing embeddings for {len(chunks_df)} chunks...")
batch_size, all_embeddings = 32, []
for i in range(0, len(chunks_df), batch_size):
    batch = chunks_df.iloc[i:i+batch_size]
    vectors = model.encode(batch["chunk_text"].tolist(), show_progress_bar=False)
    all_embeddings.extend(vectors.tolist())
    if (i + batch_size) % 128 == 0:
        print(f"  Processed {min(i + batch_size, len(chunks_df))}/{len(chunks_df)}")

chunks_df["embedding"] = all_embeddings
chunks_df["model_name"] = EMBEDDING_MODEL_NAME
print(f"✅ Computed {len(chunks_df)} embeddings")

# ---------------------------------------------------------------------------
# PART 5: Insert Embeddings
# ---------------------------------------------------------------------------

if len(chunks_df) > 0:
    print(f"\nInserting {len(chunks_df)} embeddings...")
    conn = psycopg2.connect(
        host=db_host, port=db_port, dbname=db_name,
        user=db_user, password=db_password, sslmode="require"
    )
    
    try:
        cursor = conn.cursor()
        insert_data = [(row["embedding_id"], row["document_id"], int(row["chunk_index"]),
                       row["chunk_text"],
                       "{" + ",".join(str(float(x)) for x in row["embedding"]) + "}",
                       row["model_name"])
                      for _, row in chunks_df.iterrows()]
        
        insert_sql = f"""
            INSERT INTO {HEALTH_EMBEDDINGS_TABLE_NAME} (
                embedding_id, document_id, chunk_index, chunk_text,
                embedding, model_name, created_at
            ) VALUES (%s,%s,%s,%s,%s::double precision[],%s,CURRENT_TIMESTAMP)
            ON CONFLICT (embedding_id) DO NOTHING
        """
        
        cursor.executemany(insert_sql, insert_data)
        conn.commit()
        print(f"✅ Inserted {cursor.rowcount} embeddings")
        print(f"\nIMPORTANT: Run this SQL to cast arrays to vectors:")
        print(f"  UPDATE {HEALTH_EMBEDDINGS_TABLE_NAME} SET embedding = embedding::vector;")
    finally:
        cursor.close()
        conn.close()

print("\n" + "="*80)
print("✅ PIPELINE COMPLETE!")
print("="*80)
