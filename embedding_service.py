"""
Embedding service for health knowledge search.

Generates vector embeddings for text queries using sentence-transformers.
This module provides a singleton embedding model that can be reused across requests.
"""

import os
import logging
from typing import List

from sentence_transformers import SentenceTransformer

logger = logging.getLogger("embedding-service")

# Model configuration - must match the dimension used in health_embeddings table (VECTOR(384))
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # 384 dimensions
MODEL_CACHE_DIR = "/tmp/.cache/huggingface"

# Singleton model instance
_model = None


def get_embedding_model(model_name: str = DEFAULT_MODEL) -> SentenceTransformer:
    """Get or initialize the embedding model (singleton pattern for efficiency)."""
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {model_name}")
        os.environ["HF_HOME"] = MODEL_CACHE_DIR
        os.environ["TRANSFORMERS_CACHE"] = MODEL_CACHE_DIR
        _model = SentenceTransformer(model_name, cache_folder=MODEL_CACHE_DIR)
        logger.info(f"Model loaded: {model_name} (dimension: {_model.get_sentence_embedding_dimension()})")
    return _model


def generate_query_embedding(query: str, model_name: str = DEFAULT_MODEL) -> List[float]:
    """
    Generate a vector embedding for a search query.
    
    Args:
        query: Natural language search query
        model_name: Embedding model to use (default: all-MiniLM-L6-v2)
    
    Returns:
        List of floats representing the query embedding vector
    """
    if not query or not query.strip():
        raise ValueError("Query cannot be empty")
    
    model = get_embedding_model(model_name)
    embedding = model.encode(query.strip(), show_progress_bar=False)
    return embedding.tolist()


def get_embedding_dimension(model_name: str = DEFAULT_MODEL) -> int:
    """Get the dimension of the embedding model."""
    model = get_embedding_model(model_name)
    return model.get_sentence_embedding_dimension()
