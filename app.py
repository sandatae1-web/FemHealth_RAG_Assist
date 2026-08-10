"""
FemLens — Women's Health Research Companion

A Databricks App that provides a clean research workspace for exploring 
women's-health clinical research:
- Ask natural-language research questions
- Search and explore clinical studies (via Agent Bricks + MCP tools)
- Save studies to personal research collection
- View and manage saved studies

Integrates with:
- Databricks Agent Bricks for natural language understanding
- Health Research MCP Server for ClinicalTrials.gov and vector search
- Lakebase (Postgres) for research collection storage

Run locally:
    python app.py
Deploy as a Databricks App using app.yaml.
"""

import logging
import os
import uuid
import json
from datetime import datetime

import requests
from databricks.sdk import WorkspaceClient
from flask import Flask, jsonify, render_template, request

import lakebase
from health_client import HealthClient
from embedding_service import generate_query_embedding
from vector_search_service import vector_search_health_knowledge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("femlens-app")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex())
_w = WorkspaceClient()

# Configuration
RESEARCH_COLLECTION_TABLE = os.environ.get("RESEARCH_COLLECTION_TABLE", "health_research_collection")
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8001")

# Initialize health client for direct API calls when needed
_health_client = None

def get_health_client():
    """Lazy-load the ClinicalTrials.gov API client."""
    global _health_client
    if _health_client is None:
        _health_client = HealthClient()
    return _health_client


def ensure_research_collection_table():
    """Create the research collection table in Lakebase if it doesn't exist yet."""
    lakebase.run_write(
        f"""
        CREATE TABLE IF NOT EXISTS {RESEARCH_COLLECTION_TABLE} (
            collection_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            nct_id TEXT NOT NULL,
            document_id TEXT,
            notes TEXT,
            saved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_user_health_study UNIQUE (user_id, nct_id)
        )
        """
    )


def _current_user_email() -> str:
    """
    Resolve the current user's email for personalized collection.

    Databricks Apps inject the logged-in user's identity via the
    X-Forwarded-Email header on every request. Fall back to the Databricks
    SDK's current_user API for local development where that header isn't set.
    """
    header_email = request.headers.get("X-Forwarded-Email")
    if header_email:
        return header_email
    return _w.current_user.me().user_name


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.errorhandler(Exception)
def handle_exception(err):
    """Ensure all unhandled errors return JSON (not an HTML error page),
    so the frontend's resp.json() call never chokes on HTML."""
    logger.exception("Unhandled exception while processing request")
    status_code = getattr(err, "code", 500)
    if not isinstance(status_code, int):
        status_code = 500
    return jsonify({"error": str(err)}), status_code


@app.route("/")
def index():
    """FemLens main research interface."""
    return render_template("index.html")


@app.route("/api/ask", methods=["POST"])
def ask_femlens():
    """
    Submit a natural-language research question to FemLens.
    Processes the question directly using HealthClient to search ClinicalTrials.gov.
    """
    try:
        body = request.json if request.is_json else {}
        question = body.get("question", "").strip()
        
        if not question:
            return jsonify({"error": "Please enter a research question"}), 400
        
        user_id = _current_user_email()
        logger.info(f"Processing research question for {user_id}: {question}")
        
        # Parse question and search directly using HealthClient
        client = get_health_client()
        studies = _search_studies_from_question(client, question)
        
        if not studies:
            return jsonify({
                "response": "I couldn't find any clinical studies matching your criteria. Try using different keywords or broader search terms.",
                "studies": []
            })
        
        # Generate response text
        response_text = f"I found {len(studies)} clinical study" + ("" if len(studies) == 1 else "ies") + " related to your question."
        if len(studies) >= 10:
            response_text += " Showing the first 10 results."
        
        return jsonify({
            "response": response_text,
            "studies": studies
        })
        
    except Exception as e:
        logger.exception("Error processing research question")
        return jsonify({"error": "An error occurred processing your request. Please try again."}), 500


def _search_studies_from_question(client: HealthClient, question: str) -> list:
    """
    Parse the research question and search ClinicalTrials.gov.
    Extracts condition keywords and recruitment status from natural language.
    """
    question_lower = question.lower()
    
    # Map common terms to ClinicalTrials.gov conditions
    conditions_map = {
        "menopause": "menopause",
        "hot flash": "menopause",
        "perimenopause": "perimenopause",
        "endometriosis": "endometriosis",
        "pcos": "Polycystic Ovary Syndrome",
        "polycystic ovary": "Polycystic Ovary Syndrome",
        "pregnancy": "pregnancy",
        "pregnant": "pregnancy",
        "gestational diabetes": "Gestational Diabetes",
        "preeclampsia": "Pre-Eclampsia",
        "postpartum depression": "Depression, Postpartum",
        "postpartum": "postpartum",
        "breast cancer": "Breast Neoplasms",
        "ovarian cancer": "Ovarian Neoplasms",
        "cervical cancer": "Cervical Neoplasms",
        "uterine cancer": "Uterine Neoplasms",
        "fertility": "Infertility",
        "infertility": "Infertility",
        "contraception": "Contraception",
        "birth control": "Contraception",
        "fibroids": "Leiomyoma",
        "uterine fibroids": "Leiomyoma",
        "osteoporosis": "Osteoporosis",
        "heart disease": "Cardiovascular Diseases",
        "cardiovascular": "Cardiovascular Diseases",
        "depression": "Depression",
        "anxiety": "Anxiety",
        "sleep": "Sleep Wake Disorders",
        "insomnia": "Sleep Initiation and Maintenance Disorders",
    }
    
    # Find matching condition
    condition = None
    for keyword, mesh_term in conditions_map.items():
        if keyword in question_lower:
            condition = mesh_term
            logger.info(f"Detected condition: {condition} from keyword: {keyword}")
            break
    
    # Extract recruitment status
    status = None
    if "recruiting" in question_lower:
        status = "RECRUITING"
        logger.info("Detected status: RECRUITING")
    elif "completed" in question_lower:
        status = "COMPLETED"
        logger.info("Detected status: COMPLETED")
    elif "active" in question_lower:
        status = "ACTIVE_NOT_RECRUITING"
        logger.info("Detected status: ACTIVE_NOT_RECRUITING")
    
    # If no specific condition found, use general terms from the question
    if not condition:
        # Extract potential search terms (skip common words)
        common_words = {'find', 'show', 'search', 'looking', 'for', 'about', 'related', 'to', 
                       'studies', 'trials', 'clinical', 'research', 'the', 'a', 'an', 'and', 'or'}
        words = [w for w in question_lower.split() if w not in common_words and len(w) > 3]
        if words:
            condition = ' '.join(words[:3])  # Use first few meaningful words
            logger.info(f"Using general search terms: {condition}")
    
    # Search ClinicalTrials.gov
    try:
        logger.info(f"Searching with condition={condition}, status={status}")
        results = client.search_studies(
            condition=condition,
            status=status,
            page_size=10
        )
        logger.info(f"Found {len(results)} studies")
        return results
    except Exception as e:
        logger.error(f"Error searching studies: {e}")
        return []


@app.route("/api/study/<nct_id>", methods=["GET"])
def get_study_details(nct_id: str):
    """
    Retrieve detailed information about a specific clinical study.
    First tries health_documents table, then falls back to ClinicalTrials.gov API.
    """
    try:
        nct_id = nct_id.strip().upper()
        
        if not nct_id.startswith("NCT"):
            return jsonify({"error": "Invalid NCT ID format"}), 400
        
        logger.info(f"Fetching study details for {nct_id}")
        
        # First try: Check if we have this study in our health_documents table
        try:
            rows = lakebase.run_query(
                "SELECT * FROM health_documents WHERE nct_id = %s LIMIT 1",
                (nct_id,)
            )
            
            if rows and len(rows) > 0:
                doc = rows[0]
                logger.info(f"Found {nct_id} in health_documents table")
                return jsonify({
                    "nct_id": doc["nct_id"],
                    "title": doc["title"],
                    "conditions": [doc["condition"]] if doc.get("condition") else [],
                    "summary": doc.get("summary"),
                    "detailed_description": doc.get("full_text"),
                    "status": doc.get("study_status"),
                    "sex": doc.get("sex"),
                    "minimum_age": doc.get("minimum_age"),
                    "maximum_age": doc.get("maximum_age"),
                    "sponsor": doc.get("sponsor_name"),
                    "locations": doc.get("locations", "").split(", ") if doc.get("locations") else [],
                    "url": doc.get("source_url") or f"https://clinicaltrials.gov/study/{nct_id}",
                    "source": "local_database"
                })
        except Exception as e:
            logger.warning(f"Could not query health_documents for {nct_id}: {e}")
        
        # Second try: Fetch from ClinicalTrials.gov API
        try:
            client = get_health_client()
            study = client.get_study_details(nct_id)
            
            if study:
                logger.info(f"Fetched {nct_id} from ClinicalTrials.gov API")
                study["source"] = "clinicaltrials_api"
                return jsonify(study)
        except Exception as e:
            logger.error(f"ClinicalTrials.gov API error for {nct_id}: {e}")
        
        # If both methods fail
        return jsonify({"error": f"Study {nct_id} not found in database or ClinicalTrials.gov"}), 404
        
    except Exception as e:
        logger.exception(f"Unexpected error fetching study details for {nct_id}")
        return jsonify({
            "error": "Unable to retrieve study details. Please try again."
        }), 500


@app.route("/api/collection", methods=["GET"])
def get_research_collection():
    """Return the current user's saved research studies."""
    try:
        ensure_research_collection_table()
        user_id = _current_user_email()
        
        rows = lakebase.run_query(
            f"""
            SELECT collection_id, user_id, nct_id, document_id, notes, saved_at
            FROM {RESEARCH_COLLECTION_TABLE}
            WHERE user_id = %s
            ORDER BY saved_at DESC
            """,
            (user_id,),
        )
        
        # Enrich with study details
        enriched = []
        client = get_health_client()
        
        for row in rows:
            try:
                study = client.get_study_details(row["nct_id"])
                enriched.append({
                    "collection_id": row["collection_id"],
                    "nct_id": row["nct_id"],
                    "notes": row["notes"],
                    "saved_at": row["saved_at"],
                    "study": study
                })
            except Exception as e:
                logger.warning(f"Could not enrich study {row['nct_id']}: {e}")
                enriched.append({
                    "collection_id": row["collection_id"],
                    "nct_id": row["nct_id"],
                    "notes": row["notes"],
                    "saved_at": row["saved_at"],
                    "study": None
                })
        
        return jsonify(enriched)
        
    except Exception as e:
        logger.exception("Error retrieving research collection")
        return jsonify({"error": "Unable to load research collection"}), 500


@app.route("/api/collection", methods=["POST"])
def save_to_collection():
    """
    Save a clinical study to the current user's research collection.
    """
    try:
        ensure_research_collection_table()
        
        body = request.json if request.is_json else {}
        nct_id = body.get("nct_id", "").strip().upper()
        notes = body.get("notes", "").strip()
        
        if not nct_id or not nct_id.startswith("NCT"):
            return jsonify({"error": "Invalid NCT ID"}), 400
        
        user_id = _current_user_email()
        collection_id = str(uuid.uuid4())
        
        # Insert or update
        lakebase.run_write(
            f"""
            INSERT INTO {RESEARCH_COLLECTION_TABLE} 
                (collection_id, user_id, nct_id, notes, saved_at)
            VALUES (%s, %s, %s, %s, now())
            ON CONFLICT (user_id, nct_id) DO UPDATE
                SET notes = EXCLUDED.notes,
                    saved_at = EXCLUDED.saved_at
            """,
            (collection_id, user_id, nct_id, notes),
        )
        
        return jsonify({
            "collection_id": collection_id,
            "nct_id": nct_id,
            "user_id": user_id,
            "notes": notes,
            "message": "Study saved to your research collection"
        })
        
    except Exception as e:
        logger.exception("Error saving study to collection")
        return jsonify({"error": "Unable to save study. Please try again."}), 500


@app.route("/api/collection/<nct_id>", methods=["DELETE"])
def remove_from_collection(nct_id: str):
    """Remove a clinical study from the current user's research collection."""
    try:
        ensure_research_collection_table()
        
        nct_id = nct_id.strip().upper()
        
        if not nct_id.startswith("NCT"):
            return jsonify({"error": "Invalid NCT ID"}), 400
        
        user_id = _current_user_email()
        deleted = lakebase.run_write(
            f"DELETE FROM {RESEARCH_COLLECTION_TABLE} WHERE user_id = %s AND nct_id = %s",
            (user_id, nct_id),
        )
        
        if not deleted:
            return jsonify({"error": f"{nct_id} is not in your research collection"}), 404
        
        return jsonify({
            "nct_id": nct_id,
            "user_id": user_id,
            "deleted": True,
            "message": "Study removed from your research collection"
        })
        
    except Exception as e:
        logger.exception("Error removing study from collection")
        return jsonify({"error": "Unable to remove study. Please try again."}), 500




@app.route("/api/dashboard", methods=["GET"])
def get_dashboard_metrics():
    """
    Aggregate dashboard metrics for FemLens.
    
    Returns:
        {
            "kpis": {
                "total_searches": int,
                "studies_found": int,
                "recruiting_studies": int,
                "saved_studies": int,
                "knowledge_documents": int
            },
            "research_pulse": [...],
            "research_interests": [...],
            "clinical_trial_landscape": {...},
            "knowledge_base": {...},
            "recent_activity": [...]
        }
    """
    try:
        ensure_research_collection_table()
        user_id = _current_user_email()
        
        # KPIs
        kpis = {}
        
        # Total saved studies (user-specific)
        try:
            saved_rows = lakebase.run_query(
                f"SELECT COUNT(*) as count FROM {RESEARCH_COLLECTION_TABLE} WHERE user_id = %s",
                (user_id,)
            )
            kpis["saved_studies"] = saved_rows[0]["count"] if saved_rows else 0
        except Exception as e:
            logger.warning(f"Could not count saved studies: {e}")
            kpis["saved_studies"] = 0
        
        # Knowledge documents
        try:
            doc_rows = lakebase.run_query("SELECT COUNT(*) as count FROM health_documents")
            kpis["knowledge_documents"] = doc_rows[0]["count"] if doc_rows else 0
        except Exception as e:
            logger.warning(f"Could not count knowledge documents: {e}")
            kpis["knowledge_documents"] = 0
        
        # Recruiting studies (from health_documents)
        try:
            recruiting_rows = lakebase.run_query(
                "SELECT COUNT(*) as count FROM health_documents WHERE study_status ILIKE '%recruiting%'"
            )
            kpis["recruiting_studies"] = recruiting_rows[0]["count"] if recruiting_rows else 0
        except Exception as e:
            logger.warning(f"Could not count recruiting studies: {e}")
            kpis["recruiting_studies"] = 0
        
        # Clinical Trial Landscape (study status distribution)
        clinical_trial_landscape = {}
        try:
            status_rows = lakebase.run_query(
                """
                SELECT study_status, COUNT(*) as count
                FROM health_documents
                WHERE study_status IS NOT NULL
                GROUP BY study_status
                ORDER BY count DESC
                """
            )
            total = sum(row["count"] for row in status_rows)
            if total > 0:
                clinical_trial_landscape = {
                    row["study_status"]: {
                        "count": row["count"],
                        "percentage": round((row["count"] / total) * 100, 1)
                    }
                    for row in status_rows
                }
        except Exception as e:
            logger.warning(f"Could not get clinical trial landscape: {e}")
        
        # Research Interests (top conditions)
        research_interests = []
        try:
            condition_rows = lakebase.run_query(
                """
                SELECT condition, COUNT(*) as count
                FROM health_documents
                WHERE condition IS NOT NULL AND condition != ''
                GROUP BY condition
                ORDER BY count DESC
                LIMIT 10
                """
            )
            research_interests = [
                {"condition": row["condition"], "count": row["count"]}
                for row in condition_rows
            ]
        except Exception as e:
            logger.warning(f"Could not get research interests: {e}")
        
        # Knowledge Base metrics
        knowledge_base = {}
        try:
            # Documents count (already have this)
            knowledge_base["documents"] = kpis.get("knowledge_documents", 0)
            
            # Chunks count
            try:
                chunk_rows = lakebase.run_query("SELECT COUNT(*) as count FROM health_embeddings")
                knowledge_base["chunks"] = chunk_rows[0]["count"] if chunk_rows else 0
            except:
                knowledge_base["chunks"] = 0
        except Exception as e:
            logger.warning(f"Could not get knowledge base metrics: {e}")
        
        # Recent Activity (recent saved studies for this user)
        recent_activity = []
        try:
            activity_rows = lakebase.run_query(
                f"""
                SELECT nct_id, notes, saved_at
                FROM {RESEARCH_COLLECTION_TABLE}
                WHERE user_id = %s
                ORDER BY saved_at DESC
                LIMIT 5
                """,
                (user_id,)
            )
            recent_activity = [
                {
                    "nct_id": row["nct_id"],
                    "notes": row["notes"],
                    "saved_at": row["saved_at"].isoformat() if hasattr(row["saved_at"], "isoformat") else str(row["saved_at"])
                }
                for row in activity_rows
            ]
        except Exception as e:
            logger.warning(f"Could not get recent activity: {e}")
        
        return jsonify({
            "kpis": kpis,
            "clinical_trial_landscape": clinical_trial_landscape,
            "research_interests": research_interests,
            "knowledge_base": knowledge_base,
            "recent_activity": recent_activity
        })
        
    except Exception as e:
        logger.exception("Error generating dashboard metrics")
        return jsonify({"error": "Unable to load dashboard metrics"}), 500


@app.route("/health/search", methods=["POST"])
def health_search():
    """
    Semantic search endpoint for health knowledge using vector embeddings.
    
    Request body:
        {
            "query": "menopause studies related to sleep problems",
            "top_k": 5  (optional, default 5)
        }
    
    Response:
        {
            "query": "...",
            "top_k": 5,
            "results": [
                {
                    "document_id": "...",
                    "nct_id": "NCT...",
                    "title": "...",
                    "condition": "...",
                    "chunk_text": "...",
                    "similarity": 0.89,
                    ...
                }
            ]
        }
    """
    try:
        # Parse request body
        body = request.json if request.is_json else None
        
        if not body:
            return jsonify({"error": "Request body is required"}), 400
        
        query = body.get("query", "").strip()
        
        if not query:
            return jsonify({"error": "query is required"}), 400
        
        # Validate and set top_k
        top_k = body.get("top_k", 5)
        try:
            top_k = int(top_k)
            if top_k < 1 or top_k > 100:
                return jsonify({"error": "top_k must be between 1 and 100"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "top_k must be a valid integer"}), 400
        
        user_id = _current_user_email()
        logger.info(f"Health search request from {user_id}: '{query}' (top_k={top_k})")
        
        # Generate embedding for the query
        try:
            query_embedding = generate_query_embedding(query)
        except Exception as e:
            logger.exception("Error generating query embedding")
            return jsonify({"error": "Failed to process query. Please try again."}), 500
        
        # Perform vector search
        try:
            results = vector_search_health_knowledge(
                query_embedding=query_embedding,
                top_k=top_k,
                similarity_threshold=0.0  # Return all results, let user decide threshold
            )
        except Exception as e:
            logger.exception("Error performing vector search")
            return jsonify({"error": "Unable to search health knowledge"}), 500
        
        return jsonify({
            "query": query,
            "top_k": top_k,
            "results": results,
            "count": len(results)
        })
        
    except Exception as e:
        logger.exception("Unexpected error in health search")
        return jsonify({"error": "An error occurred processing your request"}), 500



if __name__ == '__main__':
    host = os.getenv('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_RUN_PORT', 8000))
    app.run(debug=True, host=host, port=port)
