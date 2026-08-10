# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # Ingest Women's Health Clinical Trials -> Vector Embeddings (Lakebase)
# MAGIC
# MAGIC This notebook is part of the **FemHealth RAG Assist** project.
# MAGIC
# MAGIC It:
# MAGIC 1. Fetches women's health clinical trial data from the ClinicalTrials.gov API v2
# MAGIC    using the `health_client.py` module.
# MAGIC 2. Transforms the API response into structured documents and upserts them into
# MAGIC    the `health_documents` table in Lakebase Postgres.
# MAGIC 3. Chunks the full text of each document for embedding generation.
# MAGIC 4. Computes sentence embeddings for each chunk using Spark, distributed across
# MAGIC    the cluster via a pandas UDF, and writes them into the `health_embeddings`
# MAGIC    table.
# MAGIC
# MAGIC This follows the same architecture as `ingest_ticker_news_embeddings.py`.

# COMMAND ----------

# DBTITLE 1,Install all required packages
# MAGIC %pip uninstall -y psycopg2 psycopg2-binary
# MAGIC %pip install -q 'databricks-sdk>=0.118.0' sentence-transformers requests pandas

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Config
# MAGIC
# MAGIC Widgets let you override the destination table names, the embedding model,
# MAGIC and API parameters without editing the notebook - useful when running this
# MAGIC as a scheduled Databricks Job.

# COMMAND ----------

dbutils.widgets.text("health_documents_table_name", "health_documents", "Destination table (raw documents)")
dbutils.widgets.text("health_embeddings_table_name", "health_embeddings", "Destination table (vectors)")
dbutils.widgets.text("embedding_model", "sentence-transformers/all-MiniLM-L6-v2", "Embedding model")
dbutils.widgets.text("api_base_url", "https://clinicaltrials.gov/api/v2", "ClinicalTrials.gov API URL")
dbutils.widgets.text("max_studies", "100", "Max studies to fetch (None = all)")
dbutils.widgets.text("rate_limit_delay", "0.5", "Delay between API requests (seconds)")
dbutils.widgets.text("chunk_size", "800", "Document chunk size (chars)")
dbutils.widgets.text("chunk_overlap", "100", "Document chunk overlap (chars)")

HEALTH_DOCUMENTS_TABLE_NAME = dbutils.widgets.get("health_documents_table_name")
HEALTH_EMBEDDINGS_TABLE_NAME = dbutils.widgets.get("health_embeddings_table_name")
EMBEDDING_MODEL_NAME = dbutils.widgets.get("embedding_model")
API_BASE_URL = dbutils.widgets.get("api_base_url")
MAX_STUDIES = dbutils.widgets.get("max_studies")
MAX_STUDIES = int(MAX_STUDIES) if MAX_STUDIES and MAX_STUDIES.lower() != "none" else None
RATE_LIMIT_DELAY = float(dbutils.widgets.get("rate_limit_delay"))
CHUNK_SIZE = int(dbutils.widgets.get("chunk_size"))
CHUNK_OVERLAP = int(dbutils.widgets.get("chunk_overlap"))

# Map embedding model names to their output dimensions
match EMBEDDING_MODEL_NAME:
    case "sentence-transformers/all-MiniLM-L6-v2":
        EMBEDDING_DIM = 384
    case "sentence-transformers/all-MiniLM-L12-v2":
        EMBEDDING_DIM = 384
    case "sentence-transformers/all-mpnet-base-v2":
        EMBEDDING_DIM = 768
    case "sentence-transformers/paraphrase-multilingual-mpnet-base-v2":
        EMBEDDING_DIM = 768
    case "BAAI/bge-small-en-v1.5":
        EMBEDDING_DIM = 384
    case "BAAI/bge-base-en-v1.5":
        EMBEDDING_DIM = 768
    case "BAAI/bge-large-en-v1.5":
        EMBEDDING_DIM = 1024
    case "text-embedding-3-small":
        EMBEDDING_DIM = 1536
    case "text-embedding-3-large":
        EMBEDDING_DIM = 3072
    case _:
        raise ValueError(
            f"Unknown embedding model {EMBEDDING_MODEL_NAME!r} - add its output "
            "dimension to the match/case block above before running this notebook."
        )

print(f"Using model {EMBEDDING_MODEL_NAME!r} -> {EMBEDDING_DIM}-dim vectors")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Resolve the Lakebase connection URL
# MAGIC
# MAGIC Same secret, same decoding scheme as `lakebase.py`: a single base64-encoded
# MAGIC Postgres URL stored in a Databricks secret scope.

# COMMAND ----------

# DBTITLE 1,Parse Lakebase Connection Info
import base64
from urllib.parse import urlparse
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

def get_lakebase_url() -> str:
    secret = w.secrets.get_secret(scope="database", key="lakebase-url")
    return base64.b64decode(secret.value).decode("utf-8")

lakebase_url = get_lakebase_url()
parsed = urlparse(lakebase_url)

db_host = parsed.hostname
db_port = parsed.port or 5432
db_name = parsed.path.lstrip('/')
db_user = parsed.username
db_password = parsed.password

print(f"Connection details:")
print(f"  Host: {db_host}:{db_port}")
print(f"  Database: {db_name}")
print(f"  User: {db_user}")

# COMMAND ----------

# DBTITLE 1,Test Connection
import psycopg2

print(f"Testing connection to {db_host}:{db_port}/{db_name}\n")

try:
    conn = psycopg2.connect(
        host=db_host, port=db_port, dbname=db_name,
        user=db_user, password=db_password,
        sslmode='require', connect_timeout=10
    )
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    print(f"✅ Connection successful!")
    cursor.close()
    conn.close()
except Exception as e:
    print(f"❌ Connection failed: {e}")
    raise

# COMMAND ----------

# MAGIC %md
# MAGIC ## Fetch women's health studies from ClinicalTrials.gov
# MAGIC
# MAGIC Uses the `health_client.py` module with pagination and rate limiting.

# COMMAND ----------

# DBTITLE 1,Fetch studies using health_client
import sys
import os

sys.path.insert(0, '/Workspace/Users/sangeethakanagaraj.do@gmail.com/FemHealth_RAG_Assist')
os.environ['CLINICALTRIALS_API_BASE_URL'] = API_BASE_URL

from health_client import HealthClient

print("NOTE: Ensure you've run sql/03_setup_health_documents_table.sql first\n")

client = HealthClient(base_url=API_BASE_URL, rate_limit_delay=RATE_LIMIT_DELAY)

print(f"Fetching women's health studies (max: {MAX_STUDIES or 'unlimited'})...")
studies = []

try:
    for study in client.get_womens_health_studies(max_results=MAX_STUDIES):
        studies.append(study)
        if len(studies) % 10 == 0:
            print(f"  Fetched {len(studies)} studies...")
except Exception as e:
    print(f"Error: {e}")
    if studies:
        print(f"Continuing with {len(studies)} studies...")
    else:
        raise

print(f"\nTotal: {len(studies)} studies")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Data Transformation
# MAGIC
# MAGIC Transform API responses into structured documents for the health_documents table.

# COMMAND ----------

# DBTITLE 1,Transform studies to documents
import json
from datetime import datetime

# Transformation helpers
def safe_get(obj, *keys, default=None):
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
    locations = []
    protocol = safe_get(study, "protocolSection", default={})
    locs = safe_get(protocol, "contactsLocationsModule", "locations", default=[])
    for loc in locs:
        locations.append({"city": safe_get(loc, "city"), "state": safe_get(loc, "state"), "country": safe_get(loc, "country")})
    return json.dumps(locations) if locations else None

def transform_study_to_document(study):
    protocol = safe_get(study, "protocolSection", default={})
    nct_id = safe_get(protocol, "identificationModule", "nctId")
    brief_title = safe_get(protocol, "identificationModule", "briefTitle", default="")
    official_title = safe_get(protocol, "identificationModule", "officialTitle")
    title = official_title or brief_title or "Untitled Study"
    conditions = safe_get(protocol, "conditionsModule", "conditions", default=[])
    brief_summary = safe_get(protocol, "descriptionModule", "briefSummary")
    detailed_desc = safe_get(protocol, "descriptionModule", "detailedDescription")
    full_text_parts = [title]
    if brief_summary:
        full_text_parts.append(brief_summary)
    if detailed_desc:
        full_text_parts.append(detailed_desc)
    return {
        "document_id": nct_id or f"study_{hash(json.dumps(study))}",
        "nct_id": nct_id, "title": title, "condition": ", ".join(conditions) if conditions else None,
        "document_type": "clinical_trial", "source_url": f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else None,
        "summary": brief_summary, "full_text": "\n\n".join(full_text_parts),
        "study_status": safe_get(protocol, "statusModule", "overallStatus"),
        "sex": safe_get(protocol, "eligibilityModule", "sex"),
        "minimum_age": safe_get(protocol, "eligibilityModule", "minimumAge"),
        "maximum_age": safe_get(protocol, "eligibilityModule", "maximumAge"),
        "sponsor_name": safe_get(protocol, "sponsorCollaboratorsModule", "leadSponsor", "name"),
        "locations": extract_locations(study), "source_name": "ClinicalTrials.gov",
        "source_updated_at": safe_get(protocol, "statusModule", "lastUpdatePostDateStruct", "date"),
    }

print(f"Transforming {len(studies)} studies...")
documents = [transform_study_to_document(s) for s in studies]
print(f"✅ Transformed {len(documents)} documents")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Insert Documents into Lakebase

# COMMAND ----------

# DBTITLE 1,Insert documents using psycopg2
import psycopg2

if documents:
    print(f"\nInserting {len(documents)} documents...")
    conn = psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_password, sslmode="require")
    try:
        cursor = conn.cursor()
        insert_data = [(d["document_id"], d["nct_id"], d["title"], d["condition"], d["document_type"],
                       d["source_url"], d["summary"], d["full_text"], d["study_status"], d["sex"],
                       d["minimum_age"], d["maximum_age"], d["sponsor_name"], d["locations"],
                       d["source_name"], d["source_updated_at"]) for d in documents]
        insert_sql = f"""INSERT INTO {HEALTH_DOCUMENTS_TABLE_NAME} (document_id, nct_id, title, condition, document_type,
            source_url, summary, full_text, study_status, sex, minimum_age, maximum_age, sponsor_name, locations,
            source_name, source_updated_at, created_at, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) ON CONFLICT (document_id) DO UPDATE SET title=EXCLUDED.title,
            full_text=EXCLUDED.full_text, updated_at=CURRENT_TIMESTAMP"""
        cursor.executemany(insert_sql, insert_data)
        conn.commit()
        print(f"✅ Upserted {cursor.rowcount} documents")
    finally:
        cursor.close()
        conn.close()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load and Chunk Documents

# COMMAND ----------

# DBTITLE 1,Load documents and create chunks
import pandas as pd
import psycopg2

print(f"\nLoading documents from {HEALTH_DOCUMENTS_TABLE_NAME}...")
conn = psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_password, sslmode="require")
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
            chunks_data.append({"embedding_id": f"{doc_id}_chunk_{chunk_idx}", "document_id": doc_id,
                               "chunk_index": chunk_idx, "chunk_text": chunk_text})
        if start + CHUNK_SIZE >= len(text):
            break
chunks_df = pd.DataFrame(chunks_data)
print(f"✅ Created {len(chunks_df)} chunks")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Compute Embeddings

# COMMAND ----------

# DBTITLE 1,Compute embeddings for chunks
import os
from sentence_transformers import SentenceTransformer

os.environ["HF_HOME"] = "/tmp/.cache/huggingface"
os.environ["TRANSFORMERS_CACHE"] = "/tmp/.cache/huggingface"
print(f"\nLoading model {EMBEDDING_MODEL_NAME}...")
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

# COMMAND ----------

# MAGIC %md
# MAGIC ## Insert Embeddings

# COMMAND ----------

# DBTITLE 1,Insert embeddings into Lakebase
import psycopg2

if len(chunks_df) > 0:
    print(f"\nInserting {len(chunks_df)} embeddings...")
    conn = psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_password, sslmode="require")
    try:
        cursor = conn.cursor()
        insert_data = [(row["embedding_id"], row["document_id"], int(row["chunk_index"]), row["chunk_text"],
                       "{" + ",".join(str(float(x)) for x in row["embedding"]) + "}", row["model_name"])
                      for _, row in chunks_df.iterrows()]
        insert_sql = f"""INSERT INTO {HEALTH_EMBEDDINGS_TABLE_NAME} (embedding_id, document_id, chunk_index, chunk_text,
            embedding, model_name, created_at) VALUES (%s,%s,%s,%s,%s::double precision[],%s,CURRENT_TIMESTAMP)
            ON CONFLICT (embedding_id) DO NOTHING"""
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

# COMMAND ----------

