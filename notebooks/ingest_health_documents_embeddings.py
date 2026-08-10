{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {
    "application/vnd.databricks.v1+cell": {
     "cellMetadata": {
      "byteLimit": 2048000,
      "rowLimit": 10000
     },
     "inputWidgets": {},
     "nuid": "71fce51c-63f1-44d4-a915-fa9a936d0040",
     "showTitle": false,
     "tableResultSettingsMap": {},
     "title": ""
    }
   },
   "source": [
    "# Ingest Women's Health Clinical Trials -> Vector Embeddings (Lakebase)\n",
    "\n",
    "This notebook is part of the **FemHealth RAG Assist** project.\n",
    "\n",
    "It:\n",
    "1. Fetches women's health clinical trial data from the ClinicalTrials.gov API v2\n",
    "   using the `health_client.py` module.\n",
    "2. Transforms the API response into structured documents and upserts them into\n",
    "   the `health_documents` table in Lakebase Postgres.\n",
    "3. Chunks the full text of each document for embedding generation.\n",
    "4. Computes sentence embeddings for each chunk using Spark, distributed across\n",
    "   the cluster via a pandas UDF, and writes them into the `health_embeddings`\n",
    "   table.\n",
    "\n",
    "This follows the same architecture as `ingest_ticker_news_embeddings.py`."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 0,
   "metadata": {
    "application/vnd.databricks.v1+cell": {
     "cellMetadata": {
      "byteLimit": 2048000,
      "rowLimit": 10000
     },
     "finishTime": 1786324810177,
     "inputWidgets": {},
     "nuid": "637c0b95-ae65-4469-a789-5d0c6a632cfa",
     "showTitle": true,
     "startTime": 1786324717016,
     "submitTime": 1786324716894,
     "tableResultSettingsMap": {},
     "title": "Install all required packages"
    }
   },
   "outputs": [
    {
     "output_type": "stream",
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Found existing installation: psycopg2 2.9.11\nNot uninstalling psycopg2 at /databricks/python3/lib/python3.12/site-packages, outside environment /local_disk0/.ephemeral_nfs/envs/pythonEnv-61cd6e8c-5c19-4d09-9377-aa4d83f2649a\nCan't uninstall 'psycopg2'. No files were found to uninstall.\n\u001B[33mWARNING: Skipping psycopg2-binary as it is not installed.\u001B[0m\u001B[33m\n\u001B[0m\u001B[43mNote: you may need to restart the kernel using %restart_python or dbutils.library.restartPython() to use updated packages.\u001B[0m\n\u001B[31mERROR: pip's dependency resolver does not currently take into account all the packages that are installed. This behaviour is the source of the following dependency conflicts.\ngoogleapis-common-protos 1.65.0 requires protobuf!=3.20.0,!=3.20.1,!=4.21.1,!=4.21.2,!=4.21.3,!=4.21.4,!=4.21.5,<6.0.0.dev0,>=3.20.2, but you have protobuf 6.33.6 which is incompatible.\ngrpcio-status 1.67.0 requires protobuf<6.0dev,>=5.26.1, but you have protobuf 6.33.6 which is incompatible.\u001B[0m\u001B[31m\n\u001B[0m\u001B[43mNote: you may need to restart the kernel using %restart_python or dbutils.library.restartPython() to use updated packages.\u001B[0m\n"
     ]
    }
   ],
   "source": [
    "%pip uninstall -y psycopg2 psycopg2-binary\n",
    "%pip install -q 'databricks-sdk>=0.118.0' sentence-transformers requests pandas"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 0,
   "metadata": {
    "application/vnd.databricks.v1+cell": {
     "cellMetadata": {
      "byteLimit": 2048000,
      "rowLimit": 10000
     },
     "finishTime": 1786324815702,
     "inputWidgets": {},
     "nuid": "88e2708d-473b-4f0f-b34b-59615294f77e",
     "showTitle": false,
     "startTime": 1786324810245,
     "submitTime": 1786324716897,
     "tableResultSettingsMap": {},
     "title": ""
    }
   },
   "outputs": [],
   "source": [
    "dbutils.library.restartPython()"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {
    "application/vnd.databricks.v1+cell": {
     "cellMetadata": {
      "byteLimit": 2048000,
      "rowLimit": 10000
     },
     "inputWidgets": {},
     "nuid": "862e55d3-49c5-476b-8e74-bfff8caa90eb",
     "showTitle": false,
     "tableResultSettingsMap": {},
     "title": ""
    }
   },
   "source": [
    "## Config\n",
    "\n",
    "Widgets let you override the destination table names, the embedding model,\n",
    "and API parameters without editing the notebook - useful when running this\n",
    "as a scheduled Databricks Job."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 0,
   "metadata": {
    "application/vnd.databricks.v1+cell": {
     "cellMetadata": {
      "byteLimit": 2048000,
      "rowLimit": 10000
     },
     "finishTime": 1786324816204,
     "inputWidgets": {},
     "nuid": "17a1c1b6-f5f8-4675-bbf4-5e10168d5f08",
     "showTitle": false,
     "startTime": 1786324815730,
     "submitTime": 1786324716911,
     "tableResultSettingsMap": {},
     "title": ""
    }
   },
   "outputs": [
    {
     "output_type": "stream",
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Using model 'sentence-transformers/all-MiniLM-L6-v2' -> 384-dim vectors\n"
     ]
    }
   ],
   "source": [
    "dbutils.widgets.text(\"health_documents_table_name\", \"health_documents\", \"Destination table (raw documents)\")\n",
    "dbutils.widgets.text(\"health_embeddings_table_name\", \"health_embeddings\", \"Destination table (vectors)\")\n",
    "dbutils.widgets.text(\"embedding_model\", \"sentence-transformers/all-MiniLM-L6-v2\", \"Embedding model\")\n",
    "dbutils.widgets.text(\"api_base_url\", \"https://clinicaltrials.gov/api/v2\", \"ClinicalTrials.gov API URL\")\n",
    "dbutils.widgets.text(\"max_studies\", \"100\", \"Max studies to fetch (None = all)\")\n",
    "dbutils.widgets.text(\"rate_limit_delay\", \"0.5\", \"Delay between API requests (seconds)\")\n",
    "dbutils.widgets.text(\"chunk_size\", \"800\", \"Document chunk size (chars)\")\n",
    "dbutils.widgets.text(\"chunk_overlap\", \"100\", \"Document chunk overlap (chars)\")\n",
    "\n",
    "HEALTH_DOCUMENTS_TABLE_NAME = dbutils.widgets.get(\"health_documents_table_name\")\n",
    "HEALTH_EMBEDDINGS_TABLE_NAME = dbutils.widgets.get(\"health_embeddings_table_name\")\n",
    "EMBEDDING_MODEL_NAME = dbutils.widgets.get(\"embedding_model\")\n",
    "API_BASE_URL = dbutils.widgets.get(\"api_base_url\")\n",
    "MAX_STUDIES = dbutils.widgets.get(\"max_studies\")\n",
    "MAX_STUDIES = int(MAX_STUDIES) if MAX_STUDIES and MAX_STUDIES.lower() != \"none\" else None\n",
    "RATE_LIMIT_DELAY = float(dbutils.widgets.get(\"rate_limit_delay\"))\n",
    "CHUNK_SIZE = int(dbutils.widgets.get(\"chunk_size\"))\n",
    "CHUNK_OVERLAP = int(dbutils.widgets.get(\"chunk_overlap\"))\n",
    "\n",
    "# Map embedding model names to their output dimensions\n",
    "match EMBEDDING_MODEL_NAME:\n",
    "    case \"sentence-transformers/all-MiniLM-L6-v2\":\n",
    "        EMBEDDING_DIM = 384\n",
    "    case \"sentence-transformers/all-MiniLM-L12-v2\":\n",
    "        EMBEDDING_DIM = 384\n",
    "    case \"sentence-transformers/all-mpnet-base-v2\":\n",
    "        EMBEDDING_DIM = 768\n",
    "    case \"sentence-transformers/paraphrase-multilingual-mpnet-base-v2\":\n",
    "        EMBEDDING_DIM = 768\n",
    "    case \"BAAI/bge-small-en-v1.5\":\n",
    "        EMBEDDING_DIM = 384\n",
    "    case \"BAAI/bge-base-en-v1.5\":\n",
    "        EMBEDDING_DIM = 768\n",
    "    case \"BAAI/bge-large-en-v1.5\":\n",
    "        EMBEDDING_DIM = 1024\n",
    "    case \"text-embedding-3-small\":\n",
    "        EMBEDDING_DIM = 1536\n",
    "    case \"text-embedding-3-large\":\n",
    "        EMBEDDING_DIM = 3072\n",
    "    case _:\n",
    "        raise ValueError(\n",
    "            f\"Unknown embedding model {EMBEDDING_MODEL_NAME!r} - add its output \"\n",
    "            \"dimension to the match/case block above before running this notebook.\"\n",
    "        )\n",
    "\n",
    "print(f\"Using model {EMBEDDING_MODEL_NAME!r} -> {EMBEDDING_DIM}-dim vectors\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {
    "application/vnd.databricks.v1+cell": {
     "cellMetadata": {
      "byteLimit": 2048000,
      "rowLimit": 10000
     },
     "inputWidgets": {},
     "nuid": "2c261690-d81e-4e33-ba67-836da9eba8ac",
     "showTitle": false,
     "tableResultSettingsMap": {},
     "title": ""
    }
   },
   "source": [
    "## Resolve the Lakebase connection URL\n",
    "\n",
    "Same secret, same decoding scheme as `lakebase.py`: a single base64-encoded\n",
    "Postgres URL stored in a Databricks secret scope."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 0,
   "metadata": {
    "application/vnd.databricks.v1+cell": {
     "cellMetadata": {
      "byteLimit": 2048000,
      "rowLimit": 10000
     },
     "finishTime": 1786324818455,
     "inputWidgets": {},
     "nuid": "5a9644ca-9a0a-4856-8131-3454d6612caf",
     "showTitle": true,
     "startTime": 1786324816340,
     "submitTime": 1786324716926,
     "tableResultSettingsMap": {},
     "title": "Parse Lakebase Connection Info"
    }
   },
   "outputs": [
    {
     "output_type": "stream",
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Connection details:\n  Host: ep-plain-lake-d8t85kaz.database.us-east-2.cloud.databricks.com:5432\n  Database: databricks_postgres\n  User: dev\n"
     ]
    }
   ],
   "source": [
    "import base64\n",
    "from urllib.parse import urlparse\n",
    "from databricks.sdk import WorkspaceClient\n",
    "\n",
    "w = WorkspaceClient()\n",
    "\n",
    "def get_lakebase_url() -> str:\n",
    "    secret = w.secrets.get_secret(scope=\"database\", key=\"lakebase-url\")\n",
    "    return base64.b64decode(secret.value).decode(\"utf-8\")\n",
    "\n",
    "lakebase_url = get_lakebase_url()\n",
    "parsed = urlparse(lakebase_url)\n",
    "\n",
    "db_host = parsed.hostname\n",
    "db_port = parsed.port or 5432\n",
    "db_name = parsed.path.lstrip('/')\n",
    "db_user = parsed.username\n",
    "db_password = parsed.password\n",
    "\n",
    "print(f\"Connection details:\")\n",
    "print(f\"  Host: {db_host}:{db_port}\")\n",
    "print(f\"  Database: {db_name}\")\n",
    "print(f\"  User: {db_user}\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 0,
   "metadata": {
    "application/vnd.databricks.v1+cell": {
     "cellMetadata": {
      "byteLimit": 2048000,
      "rowLimit": 10000
     },
     "finishTime": 1786324818859,
     "inputWidgets": {},
     "nuid": "d05099d1-adfc-49f7-8297-687fff182b1d",
     "showTitle": true,
     "startTime": 1786324818476,
     "submitTime": 1786324716928,
     "tableResultSettingsMap": {},
     "title": "Test Connection"
    }
   },
   "outputs": [
    {
     "output_type": "stream",
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Testing connection to ep-plain-lake-d8t85kaz.database.us-east-2.cloud.databricks.com:5432/databricks_postgres\n\n✅ Connection successful!\n"
     ]
    }
   ],
   "source": [
    "import psycopg2\n",
    "\n",
    "print(f\"Testing connection to {db_host}:{db_port}/{db_name}\\n\")\n",
    "\n",
    "try:\n",
    "    conn = psycopg2.connect(\n",
    "        host=db_host, port=db_port, dbname=db_name,\n",
    "        user=db_user, password=db_password,\n",
    "        sslmode='require', connect_timeout=10\n",
    "    )\n",
    "    cursor = conn.cursor()\n",
    "    cursor.execute(\"SELECT version();\")\n",
    "    print(f\"✅ Connection successful!\")\n",
    "    cursor.close()\n",
    "    conn.close()\n",
    "except Exception as e:\n",
    "    print(f\"❌ Connection failed: {e}\")\n",
    "    raise"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {
    "application/vnd.databricks.v1+cell": {
     "cellMetadata": {
      "byteLimit": 2048000,
      "rowLimit": 10000
     },
     "inputWidgets": {},
     "nuid": "f83e5b3e-2bda-4752-970f-32e7adb15f5b",
     "showTitle": false,
     "tableResultSettingsMap": {},
     "title": ""
    }
   },
   "source": [
    "## Fetch women's health studies from ClinicalTrials.gov\n",
    "\n",
    "Uses the `health_client.py` module with pagination and rate limiting."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 0,
   "metadata": {
    "application/vnd.databricks.v1+cell": {
     "cellMetadata": {
      "byteLimit": 2048000,
      "rowLimit": 10000
     },
     "finishTime": 1786324819462,
     "inputWidgets": {},
     "nuid": "246fec51-5cf8-4cc0-b74c-6d15afb67837",
     "showTitle": true,
     "startTime": 1786324818888,
     "submitTime": 1786324716941,
     "tableResultSettingsMap": {},
     "title": "Fetch studies using health_client"
    }
   },
   "outputs": [
    {
     "output_type": "stream",
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "NOTE: Ensure you've run sql/03_setup_health_documents_table.sql first\n\nFetching women's health studies (max: 100)...\n  Fetched 10 studies...\n  Fetched 20 studies...\n  Fetched 30 studies...\n  Fetched 40 studies...\n  Fetched 50 studies...\n  Fetched 60 studies...\n  Fetched 70 studies...\n  Fetched 80 studies...\n  Fetched 90 studies...\n  Fetched 100 studies...\n\nTotal: 100 studies\n"
     ]
    }
   ],
   "source": [
    "import sys\n",
    "import os\n",
    "\n",
    "sys.path.insert(0, '/Workspace/Users/san.datae2@gmail.com/FemHealth_RAG_Assist')\n",
    "os.environ['CLINICALTRIALS_API_BASE_URL'] = API_BASE_URL\n",
    "\n",
    "from health_client import HealthClient\n",
    "\n",
    "print(\"NOTE: Ensure you've run sql/03_setup_health_documents_table.sql first\\n\")\n",
    "\n",
    "client = HealthClient(base_url=API_BASE_URL, rate_limit_delay=RATE_LIMIT_DELAY)\n",
    "\n",
    "print(f\"Fetching women's health studies (max: {MAX_STUDIES or 'unlimited'})...\")\n",
    "studies = []\n",
    "\n",
    "try:\n",
    "    for study in client.get_womens_health_studies(max_results=MAX_STUDIES):\n",
    "        studies.append(study)\n",
    "        if len(studies) % 10 == 0:\n",
    "            print(f\"  Fetched {len(studies)} studies...\")\n",
    "except Exception as e:\n",
    "    print(f\"Error: {e}\")\n",
    "    if studies:\n",
    "        print(f\"Continuing with {len(studies)} studies...\")\n",
    "    else:\n",
    "        raise\n",
    "\n",
    "print(f\"\\nTotal: {len(studies)} studies\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {
    "application/vnd.databricks.v1+cell": {
     "cellMetadata": {
      "byteLimit": 2048000,
      "rowLimit": 10000
     },
     "inputWidgets": {},
     "nuid": "36d5c822-7775-444a-8950-3f4b53e730e5",
     "showTitle": false,
     "tableResultSettingsMap": {},
     "title": ""
    }
   },
   "source": [
    "## Complete Data Pipeline\n",
    "\n",
    "This cell handles:\n",
    "1. Document transformation (API → health_documents schema)\n",
    "2. Batch insert with deduplication\n",
    "3. Document loading and text chunking\n",
    "4. Embedding computation\n",
    "5. Embedding insertion"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 0,
   "metadata": {
    "application/vnd.databricks.v1+cell": {
     "cellMetadata": {
      "byteLimit": 2048000,
      "rowLimit": 10000
     },
     "finishTime": 1786324864625,
     "inputWidgets": {},
     "nuid": "dc9a6041-35b9-46a9-9c15-4c3e95ed8ab6",
     "showTitle": true,
     "startTime": 1786324819508,
     "submitTime": 1786324716955,
     "tableResultSettingsMap": {},
     "title": "Run complete pipeline"
    }
   },
   "outputs": [
    {
     "output_type": "stream",
     "name": "stderr",
     "output_type": "stream",
     "text": [
      "/local_disk0/.ephemeral_nfs/envs/pythonEnv-61cd6e8c-5c19-4d09-9377-aa4d83f2649a/lib/python3.12/site-packages/torch/_vmap_internals.py:9: FutureWarning: `isinstance(treespec, LeafSpec)` is deprecated, use `isinstance(treespec, TreeSpec) and treespec.is_leaf()` instead.\n  from torch.utils._pytree import _broadcast_to_and_flatten, tree_flatten, tree_unflatten\n"
     ]
    },
    {
     "output_type": "stream",
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Transforming 100 studies...\n✅ Transformed 100 documents\n\nInserting 100 documents...\n✅ Upserted 100 documents\n\nLoading documents from health_documents...\nLoaded 100 documents\n\nChunking documents (size=800, overlap=100)...\n✅ Created 389 chunks\n\nLoading model sentence-transformers/all-MiniLM-L6-v2...\n"
     ]
    },
    {
     "output_type": "stream",
     "name": "stderr",
     "output_type": "stream",
     "text": [
      "/home/spark-61cd6e8c-5c19-4d09-9377-aa/.ipykernel/72/command-5361514450709214-4270123132:88: UserWarning: pandas only supports SQLAlchemy connectable (engine/connection) or database string URI or sqlite3 DBAPI2 connection. Other DBAPI2 objects are not tested. Please consider using SQLAlchemy.\n  docs_df = pd.read_sql(f\"SELECT document_id, full_text FROM {HEALTH_DOCUMENTS_TABLE_NAME}\", conn)\nWarning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads.\n"
     ]
    },
    {
     "output_type": "display_data",
     "data": {
      "application/vnd.jupyter.widget-view+json": {
       "model_id": "11bd2231d602463f92bbbf21b4d52826",
       "version_major": 2,
       "version_minor": 0
      },
      "text/plain": [
       "modules.json:   0%|          | 0.00/349 [00:00<?, ?B/s]"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    },
    {
     "output_type": "display_data",
     "data": {
      "application/vnd.jupyter.widget-view+json": {
       "model_id": "99e0ca0b7c8e44218a8c06b59e5ff51e",
       "version_major": 2,
       "version_minor": 0
      },
      "text/plain": [
       "config_sentence_transformers.json:   0%|          | 0.00/116 [00:00<?, ?B/s]"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    },
    {
     "output_type": "display_data",
     "data": {
      "application/vnd.jupyter.widget-view+json": {
       "model_id": "9403bfd796144dce83ef21fdd255792a",
       "version_major": 2,
       "version_minor": 0
      },
      "text/plain": [
       "README.md:   0%|          | 0.00/10.5k [00:00<?, ?B/s]"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    },
    {
     "output_type": "display_data",
     "data": {
      "application/vnd.jupyter.widget-view+json": {
       "model_id": "c6bb5358a0ae49448b74df53b8b74893",
       "version_major": 2,
       "version_minor": 0
      },
      "text/plain": [
       "sentence_bert_config.json:   0%|          | 0.00/53.0 [00:00<?, ?B/s]"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    },
    {
     "output_type": "display_data",
     "data": {
      "application/vnd.jupyter.widget-view+json": {
       "model_id": "a664a0a862934b22b8412502bbc1d8c8",
       "version_major": 2,
       "version_minor": 0
      },
      "text/plain": [
       "config.json:   0%|          | 0.00/612 [00:00<?, ?B/s]"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    },
    {
     "output_type": "display_data",
     "data": {
      "application/vnd.jupyter.widget-view+json": {
       "model_id": "52685f9906d84c8089ce499e5c9bd7d6",
       "version_major": 2,
       "version_minor": 0
      },
      "text/plain": [
       "model.safetensors: reconstructing file:   0%|          |  0.00B / 90.9MB            "
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    },
    {
     "output_type": "display_data",
     "data": {
      "application/vnd.jupyter.widget-view+json": {
       "model_id": "db8ed2e4835b49eaba274a5edf4e86f0",
       "version_major": 2,
       "version_minor": 0
      },
      "text/plain": [
       "model.safetensors: downloading bytes:           |  0.00B            "
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    },
    {
     "output_type": "display_data",
     "data": {
      "application/vnd.jupyter.widget-view+json": {
       "model_id": "9371d5395f124defba7324e09a2f5ef4",
       "version_major": 2,
       "version_minor": 0
      },
      "text/plain": [
       "Loading weights:   0%|          | 0/103 [00:00<?, ?it/s]"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    },
    {
     "output_type": "display_data",
     "data": {
      "application/vnd.jupyter.widget-view+json": {
       "model_id": "5a1495d1ef0e41cc97cf546b609366db",
       "version_major": 2,
       "version_minor": 0
      },
      "text/plain": [
       "tokenizer_config.json:   0%|          | 0.00/350 [00:00<?, ?B/s]"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    },
    {
     "output_type": "display_data",
     "data": {
      "application/vnd.jupyter.widget-view+json": {
       "model_id": "41e4ca9dec5e45ed82a5bde89d7a2f15",
       "version_major": 2,
       "version_minor": 0
      },
      "text/plain": [
       "vocab.txt:   0%|          | 0.00/232k [00:00<?, ?B/s]"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    },
    {
     "output_type": "display_data",
     "data": {
      "application/vnd.jupyter.widget-view+json": {
       "model_id": "9f5d913fa6d44126ae4db6eefc1265d4",
       "version_major": 2,
       "version_minor": 0
      },
      "text/plain": [
       "tokenizer.json:   0%|          | 0.00/466k [00:00<?, ?B/s]"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    },
    {
     "output_type": "display_data",
     "data": {
      "application/vnd.jupyter.widget-view+json": {
       "model_id": "52ec63d2c8e24889a68a123cee950a5d",
       "version_major": 2,
       "version_minor": 0
      },
      "text/plain": [
       "special_tokens_map.json:   0%|          | 0.00/112 [00:00<?, ?B/s]"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    },
    {
     "output_type": "display_data",
     "data": {
      "application/vnd.jupyter.widget-view+json": {
       "model_id": "f70dca93c76a49bd8788693273bafae7",
       "version_major": 2,
       "version_minor": 0
      },
      "text/plain": [
       "config.json:   0%|          | 0.00/190 [00:00<?, ?B/s]"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    },
    {
     "output_type": "stream",
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Computing embeddings for 389 chunks...\n  Processed 128/389\n  Processed 256/389\n  Processed 384/389\n✅ Computed 389 embeddings\n\nInserting 389 embeddings...\n✅ Inserted 389 embeddings\n\nIMPORTANT: Run this SQL to cast arrays to vectors:\n  UPDATE health_embeddings SET embedding = embedding::vector;\n\n================================================================================\n✅ PIPELINE COMPLETE!\n================================================================================\n"
     ]
    }
   ],
   "source": [
    "import json\n",
    "import psycopg2\n",
    "import pandas as pd\n",
    "from datetime import datetime\n",
    "import os\n",
    "from sentence_transformers import SentenceTransformer\n",
    "\n",
    "# Transformation helpers\n",
    "def safe_get(obj, *keys, default=None):\n",
    "    result = obj\n",
    "    for key in keys:\n",
    "        if isinstance(result, dict):\n",
    "            result = result.get(key)\n",
    "        elif isinstance(result, list) and isinstance(key, int) and len(result) > key:\n",
    "            result = result[key]\n",
    "        else:\n",
    "            return default\n",
    "        if result is None:\n",
    "            return default\n",
    "    return result\n",
    "\n",
    "def extract_locations(study):\n",
    "    locations = []\n",
    "    protocol = safe_get(study, \"protocolSection\", default={})\n",
    "    locs = safe_get(protocol, \"contactsLocationsModule\", \"locations\", default=[])\n",
    "    for loc in locs:\n",
    "        locations.append({\"city\": safe_get(loc, \"city\"), \"state\": safe_get(loc, \"state\"), \"country\": safe_get(loc, \"country\")})\n",
    "    return json.dumps(locations) if locations else None\n",
    "\n",
    "def transform_study_to_document(study):\n",
    "    protocol = safe_get(study, \"protocolSection\", default={})\n",
    "    nct_id = safe_get(protocol, \"identificationModule\", \"nctId\")\n",
    "    brief_title = safe_get(protocol, \"identificationModule\", \"briefTitle\", default=\"\")\n",
    "    official_title = safe_get(protocol, \"identificationModule\", \"officialTitle\")\n",
    "    title = official_title or brief_title or \"Untitled Study\"\n",
    "    conditions = safe_get(protocol, \"conditionsModule\", \"conditions\", default=[])\n",
    "    brief_summary = safe_get(protocol, \"descriptionModule\", \"briefSummary\")\n",
    "    detailed_desc = safe_get(protocol, \"descriptionModule\", \"detailedDescription\")\n",
    "    full_text_parts = [title]\n",
    "    if brief_summary:\n",
    "        full_text_parts.append(brief_summary)\n",
    "    if detailed_desc:\n",
    "        full_text_parts.append(detailed_desc)\n",
    "    return {\n",
    "        \"document_id\": nct_id or f\"study_{hash(json.dumps(study))}\",\n",
    "        \"nct_id\": nct_id, \"title\": title, \"condition\": \", \".join(conditions) if conditions else None,\n",
    "        \"document_type\": \"clinical_trial\", \"source_url\": f\"https://clinicaltrials.gov/study/{nct_id}\" if nct_id else None,\n",
    "        \"summary\": brief_summary, \"full_text\": \"\\n\\n\".join(full_text_parts),\n",
    "        \"study_status\": safe_get(protocol, \"statusModule\", \"overallStatus\"),\n",
    "        \"sex\": safe_get(protocol, \"eligibilityModule\", \"sex\"),\n",
    "        \"minimum_age\": safe_get(protocol, \"eligibilityModule\", \"minimumAge\"),\n",
    "        \"maximum_age\": safe_get(protocol, \"eligibilityModule\", \"maximumAge\"),\n",
    "        \"sponsor_name\": safe_get(protocol, \"sponsorCollaboratorsModule\", \"leadSponsor\", \"name\"),\n",
    "        \"locations\": extract_locations(study), \"source_name\": \"ClinicalTrials.gov\",\n",
    "        \"source_updated_at\": safe_get(protocol, \"statusModule\", \"lastUpdatePostDateStruct\", \"date\"),\n",
    "    }\n",
    "\n",
    "# STEP 1: Transform\n",
    "print(f\"Transforming {len(studies)} studies...\")\n",
    "documents = [transform_study_to_document(s) for s in studies]\n",
    "print(f\"✅ Transformed {len(documents)} documents\")\n",
    "\n",
    "# STEP 2: Insert documents\n",
    "if documents:\n",
    "    print(f\"\\nInserting {len(documents)} documents...\")\n",
    "    conn = psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_password, sslmode=\"require\")\n",
    "    try:\n",
    "        cursor = conn.cursor()\n",
    "        insert_data = [(d[\"document_id\"], d[\"nct_id\"], d[\"title\"], d[\"condition\"], d[\"document_type\"],\n",
    "                       d[\"source_url\"], d[\"summary\"], d[\"full_text\"], d[\"study_status\"], d[\"sex\"],\n",
    "                       d[\"minimum_age\"], d[\"maximum_age\"], d[\"sponsor_name\"], d[\"locations\"],\n",
    "                       d[\"source_name\"], d[\"source_updated_at\"]) for d in documents]\n",
    "        insert_sql = f\"\"\"INSERT INTO {HEALTH_DOCUMENTS_TABLE_NAME} (document_id, nct_id, title, condition, document_type,\n",
    "            source_url, summary, full_text, study_status, sex, minimum_age, maximum_age, sponsor_name, locations,\n",
    "            source_name, source_updated_at, created_at, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,\n",
    "            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) ON CONFLICT (document_id) DO UPDATE SET title=EXCLUDED.title,\n",
    "            full_text=EXCLUDED.full_text, updated_at=CURRENT_TIMESTAMP\"\"\"\n",
    "        cursor.executemany(insert_sql, insert_data)\n",
    "        conn.commit()\n",
    "        print(f\"✅ Upserted {cursor.rowcount} documents\")\n",
    "    finally:\n",
    "        cursor.close()\n",
    "        conn.close()\n",
    "\n",
    "# STEP 3: Load and chunk\n",
    "print(f\"\\nLoading documents from {HEALTH_DOCUMENTS_TABLE_NAME}...\")\n",
    "conn = psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_password, sslmode=\"require\")\n",
    "docs_df = pd.read_sql(f\"SELECT document_id, full_text FROM {HEALTH_DOCUMENTS_TABLE_NAME}\", conn)\n",
    "conn.close()\n",
    "print(f\"Loaded {len(docs_df)} documents\")\n",
    "\n",
    "print(f\"\\nChunking documents (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})...\")\n",
    "chunks_data = []\n",
    "for _, row in docs_df.iterrows():\n",
    "    doc_id, text = row[\"document_id\"], row[\"full_text\"] or \"\"\n",
    "    for chunk_idx, start in enumerate(range(0, len(text), CHUNK_SIZE - CHUNK_OVERLAP)):\n",
    "        chunk_text = text[start : start + CHUNK_SIZE].strip()\n",
    "        if chunk_text:\n",
    "            chunks_data.append({\"embedding_id\": f\"{doc_id}_chunk_{chunk_idx}\", \"document_id\": doc_id,\n",
    "                               \"chunk_index\": chunk_idx, \"chunk_text\": chunk_text})\n",
    "        if start + CHUNK_SIZE >= len(text):\n",
    "            break\n",
    "chunks_df = pd.DataFrame(chunks_data)\n",
    "print(f\"✅ Created {len(chunks_df)} chunks\")\n",
    "\n",
    "# STEP 4: Compute embeddings\n",
    "os.environ[\"HF_HOME\"] = \"/tmp/.cache/huggingface\"\n",
    "os.environ[\"TRANSFORMERS_CACHE\"] = \"/tmp/.cache/huggingface\"\n",
    "print(f\"\\nLoading model {EMBEDDING_MODEL_NAME}...\")\n",
    "model = SentenceTransformer(EMBEDDING_MODEL_NAME, cache_folder=\"/tmp/.cache/huggingface\")\n",
    "print(f\"Computing embeddings for {len(chunks_df)} chunks...\")\n",
    "batch_size, all_embeddings = 32, []\n",
    "for i in range(0, len(chunks_df), batch_size):\n",
    "    batch = chunks_df.iloc[i:i+batch_size]\n",
    "    vectors = model.encode(batch[\"chunk_text\"].tolist(), show_progress_bar=False)\n",
    "    all_embeddings.extend(vectors.tolist())\n",
    "    if (i + batch_size) % 128 == 0:\n",
    "        print(f\"  Processed {min(i + batch_size, len(chunks_df))}/{len(chunks_df)}\")\n",
    "chunks_df[\"embedding\"] = all_embeddings\n",
    "chunks_df[\"model_name\"] = EMBEDDING_MODEL_NAME\n",
    "print(f\"✅ Computed {len(chunks_df)} embeddings\")\n",
    "\n",
    "# STEP 5: Insert embeddings\n",
    "if len(chunks_df) > 0:\n",
    "    print(f\"\\nInserting {len(chunks_df)} embeddings...\")\n",
    "    conn = psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_password, sslmode=\"require\")\n",
    "    try:\n",
    "        cursor = conn.cursor()\n",
    "        insert_data = [(row[\"embedding_id\"], row[\"document_id\"], int(row[\"chunk_index\"]), row[\"chunk_text\"],\n",
    "                       \"{\" + \",\".join(str(float(x)) for x in row[\"embedding\"]) + \"}\", row[\"model_name\"])\n",
    "                      for _, row in chunks_df.iterrows()]\n",
    "        insert_sql = f\"\"\"INSERT INTO {HEALTH_EMBEDDINGS_TABLE_NAME} (embedding_id, document_id, chunk_index, chunk_text,\n",
    "            embedding, model_name, created_at) VALUES (%s,%s,%s,%s,%s::double precision[],%s,CURRENT_TIMESTAMP)\n",
    "            ON CONFLICT (embedding_id) DO NOTHING\"\"\"\n",
    "        cursor.executemany(insert_sql, insert_data)\n",
    "        conn.commit()\n",
    "        print(f\"✅ Inserted {cursor.rowcount} embeddings\")\n",
    "        print(f\"\\nIMPORTANT: Run this SQL to cast arrays to vectors:\")\n",
    "        print(f\"  UPDATE {HEALTH_EMBEDDINGS_TABLE_NAME} SET embedding = embedding::vector;\")\n",
    "    finally:\n",
    "        cursor.close()\n",
    "        conn.close()\n",
    "\n",
    "print(\"\\n\" + \"=\"*80)\n",
    "print(\"✅ PIPELINE COMPLETE!\")\n",
    "print(\"=\"*80)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 0,
   "metadata": {
    "application/vnd.databricks.v1+cell": {
     "cellMetadata": {
      "byteLimit": 2048000,
      "rowLimit": 10000
     },
     "inputWidgets": {},
     "nuid": "0d62ed13-879e-4121-a074-293e06f51d69",
     "showTitle": false,
     "tableResultSettingsMap": {},
     "title": ""
    }
   },
   "outputs": [],
   "source": []
  }
 ],
 "metadata": {
  "application/vnd.databricks.v1+notebook": {
   "computePreferences": null,
   "dashboards": [],
   "environmentMetadata": {
    "base_environment": "",
    "environment_version": "5"
   },
   "inputWidgetPreferences": null,
   "language": "python",
   "notebookMetadata": {
    "pythonIndentUnit": 4
   },
   "notebookName": "ingest_health_documents_embeddings.py",
   "widgets": {
    "api_base_url": {
     "currentValue": "https://clinicaltrials.gov/api/v2",
     "nuid": "781135d9-433f-4930-bff9-9ba2b4ad5914",
     "typedWidgetInfo": {
      "autoCreated": false,
      "defaultValue": "https://clinicaltrials.gov/api/v2",
      "label": "ClinicalTrials.gov API URL",
      "name": "api_base_url",
      "options": {
       "widgetDisplayType": "Text",
       "validationRegex": null
      },
      "parameterDataType": "String",
      "dynamic": false
     },
     "widgetInfo": {
      "widgetType": "text",
      "defaultValue": "https://clinicaltrials.gov/api/v2",
      "label": "ClinicalTrials.gov API URL",
      "name": "api_base_url",
      "options": {
       "widgetType": "text",
       "autoCreated": false,
       "validationRegex": null
      }
     }
    },
    "chunk_overlap": {
     "currentValue": "100",
     "nuid": "e7758d6a-7ced-4681-a517-4d287e8094bc",
     "typedWidgetInfo": {
      "autoCreated": false,
      "defaultValue": "100",
      "label": "Document chunk overlap (chars)",
      "name": "chunk_overlap",
      "options": {
       "widgetDisplayType": "Text",
       "validationRegex": null
      },
      "parameterDataType": "String",
      "dynamic": false
     },
     "widgetInfo": {
      "widgetType": "text",
      "defaultValue": "100",
      "label": "Document chunk overlap (chars)",
      "name": "chunk_overlap",
      "options": {
       "widgetType": "text",
       "autoCreated": false,
       "validationRegex": null
      }
     }
    },
    "chunk_size": {
     "currentValue": "800",
     "nuid": "8d70c2cd-675c-4c0f-8c5e-535670ae2fca",
     "typedWidgetInfo": {
      "autoCreated": false,
      "defaultValue": "800",
      "label": "Document chunk size (chars)",
      "name": "chunk_size",
      "options": {
       "widgetDisplayType": "Text",
       "validationRegex": null
      },
      "parameterDataType": "String",
      "dynamic": false
     },
     "widgetInfo": {
      "widgetType": "text",
      "defaultValue": "800",
      "label": "Document chunk size (chars)",
      "name": "chunk_size",
      "options": {
       "widgetType": "text",
       "autoCreated": false,
       "validationRegex": null
      }
     }
    },
    "embedding_model": {
     "currentValue": "sentence-transformers/all-MiniLM-L6-v2",
     "nuid": "fd4d59dc-d6a0-43be-b061-bd8b4a920ab7",
     "typedWidgetInfo": {
      "autoCreated": false,
      "defaultValue": "sentence-transformers/all-MiniLM-L6-v2",
      "label": "Embedding model",
      "name": "embedding_model",
      "options": {
       "widgetDisplayType": "Text",
       "validationRegex": null
      },
      "parameterDataType": "String",
      "dynamic": false
     },
     "widgetInfo": {
      "widgetType": "text",
      "defaultValue": "sentence-transformers/all-MiniLM-L6-v2",
      "label": "Embedding model",
      "name": "embedding_model",
      "options": {
       "widgetType": "text",
       "autoCreated": false,
       "validationRegex": null
      }
     }
    },
    "health_documents_table_name": {
     "currentValue": "health_documents",
     "nuid": "b09ab621-7f3c-4bfc-9e92-3c0933c6f098",
     "typedWidgetInfo": {
      "autoCreated": false,
      "defaultValue": "health_documents",
      "label": "Destination table (raw documents)",
      "name": "health_documents_table_name",
      "options": {
       "widgetDisplayType": "Text",
       "validationRegex": null
      },
      "parameterDataType": "String",
      "dynamic": false
     },
     "widgetInfo": {
      "widgetType": "text",
      "defaultValue": "health_documents",
      "label": "Destination table (raw documents)",
      "name": "health_documents_table_name",
      "options": {
       "widgetType": "text",
       "autoCreated": false,
       "validationRegex": null
      }
     }
    },
    "health_embeddings_table_name": {
     "currentValue": "health_embeddings",
     "nuid": "b8bffb51-8fd1-4321-a117-786749940823",
     "typedWidgetInfo": {
      "autoCreated": false,
      "defaultValue": "health_embeddings",
      "label": "Destination table (vectors)",
      "name": "health_embeddings_table_name",
      "options": {
       "widgetDisplayType": "Text",
       "validationRegex": null
      },
      "parameterDataType": "String",
      "dynamic": false
     },
     "widgetInfo": {
      "widgetType": "text",
      "defaultValue": "health_embeddings",
      "label": "Destination table (vectors)",
      "name": "health_embeddings_table_name",
      "options": {
       "widgetType": "text",
       "autoCreated": false,
       "validationRegex": null
      }
     }
    },
    "max_studies": {
     "currentValue": "100",
     "nuid": "99ae7e93-7028-4aca-8eee-e9159c9deebd",
     "typedWidgetInfo": {
      "autoCreated": false,
      "defaultValue": "100",
      "label": "Max studies to fetch (None = all)",
      "name": "max_studies",
      "options": {
       "widgetDisplayType": "Text",
       "validationRegex": null
      },
      "parameterDataType": "String",
      "dynamic": false
     },
     "widgetInfo": {
      "widgetType": "text",
      "defaultValue": "100",
      "label": "Max studies to fetch (None = all)",
      "name": "max_studies",
      "options": {
       "widgetType": "text",
       "autoCreated": false,
       "validationRegex": null
      }
     }
    },
    "rate_limit_delay": {
     "currentValue": "0.5",
     "nuid": "6d07596f-7458-47df-9b42-4317e23f74a3",
     "typedWidgetInfo": {
      "autoCreated": false,
      "defaultValue": "0.5",
      "label": "Delay between API requests (seconds)",
      "name": "rate_limit_delay",
      "options": {
       "widgetDisplayType": "Text",
       "validationRegex": null
      },
      "parameterDataType": "String",
      "dynamic": false
     },
     "widgetInfo": {
      "widgetType": "text",
      "defaultValue": "0.5",
      "label": "Delay between API requests (seconds)",
      "name": "rate_limit_delay",
      "options": {
       "widgetType": "text",
       "autoCreated": false,
       "validationRegex": null
      }
     }
    }
   }
  },
  "language_info": {
   "name": "python"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 0
}