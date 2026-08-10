"""
Vector search service for health knowledge retrieval.

Performs semantic similarity search against the health_embeddings table in Lakebase
using pgvector's cosine similarity operator.
"""

import logging
from typing import List, Dict, Any

import lakebase

logger = logging.getLogger("vector-search-service")


def vector_search_health_knowledge(
    query_embedding: List[float],
    top_k: int = 5,
    similarity_threshold: float = 0.0
) -> List[Dict[str, Any]]:
    """
    Perform vector similarity search against health embeddings.
    
    Args:
        query_embedding: Query vector embedding (384-dim for all-MiniLM-L6-v2)
        top_k: Number of top results to return
        similarity_threshold: Minimum cosine similarity score (0.0 to 1.0)
    
    Returns:
        List of dicts with document info and similarity scores, ordered by similarity
    """
    if not query_embedding:
        raise ValueError("query_embedding cannot be empty")
    
    if top_k < 1 or top_k > 100:
        raise ValueError("top_k must be between 1 and 100")
    
    # Convert Python list to Postgres array string format
    embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
    
    # Query: Join health_embeddings with health_documents for full context
    # Use pgvector's <=> operator for cosine distance (lower = more similar)
    # Convert distance to similarity: 1 - distance
    sql = """
        SELECT 
            d.document_id,
            d.nct_id,
            d.title,
            d.condition,
            d.summary,
            d.study_status,
            d.sex,
            d.minimum_age,
            d.maximum_age,
            d.sponsor_name,
            d.locations,
            d.source_name,
            d.source_url,
            e.chunk_text,
            e.chunk_index,
            1 - (e.embedding <=> %s::vector) AS similarity
        FROM health_embeddings e
        JOIN health_documents d ON e.document_id = d.document_id
        WHERE 1 - (e.embedding <=> %s::vector) >= %s
        ORDER BY e.embedding <=> %s::vector
        LIMIT %s
    """
    
    try:
        logger.info(f"Searching with top_k={top_k}, threshold={similarity_threshold}")
        results = lakebase.run_query(
            sql,
            (embedding_str, embedding_str, similarity_threshold, embedding_str, top_k)
        )
        
        logger.info(f"Found {len(results)} results")
        
        # Convert to list of dicts with cleaner structure
        formatted_results = []
        for row in results:
            formatted_results.append({
                "document_id": row["document_id"],
                "nct_id": row["nct_id"],
                "title": row["title"],
                "condition": row["condition"],
                "summary": row["summary"],
                "chunk_text": row["chunk_text"],
                "chunk_index": row["chunk_index"],
                "similarity": float(row["similarity"]),
                "study_status": row["study_status"],
                "sex": row["sex"],
                "age_range": f"{row['minimum_age'] or 'N/A'} - {row['maximum_age'] or 'N/A'}",
                "sponsor": row["sponsor_name"],
                "locations": row["locations"],
                "source": row["source_name"],
                "source_url": row["source_url"]
            })
        
        return formatted_results
        
    except Exception as e:
        logger.exception("Error performing vector search")
        raise RuntimeError(f"Vector search failed: {e}") from e
