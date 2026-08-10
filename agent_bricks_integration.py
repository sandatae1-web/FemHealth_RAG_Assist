"""
Agent Bricks Integration for FemLens — Women's Health Research Companion

This module provides the Agent Bricks (Databricks Assistant) integration layer
that connects to the MCP server tools, enabling natural language interactions
with the health research database.

Features:
- Read operations: Search studies, get study details, search knowledge
- Write operations: Save studies, remove studies from collection
- Guardrails: Safety checks via MCP server validation
- User context: Automatically includes user_id from session
"""

import json
import logging
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# MCP Server Configuration
MCP_SERVER_URL = "http://localhost:8002"  # Update with your MCP server URL


class AgentBricksHealthTools:
    """
    Agent Bricks tool interface for FemLens health research.
    
    Provides natural language tools that wrap the MCP server endpoints,
    with automatic user context injection and error handling.
    """
    
    def __init__(self, mcp_server_url: str = MCP_SERVER_URL):
        self.mcp_server_url = mcp_server_url
    
    def search_health_studies(
        self,
        query: str,
        user_id: str,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Search women's health clinical studies using natural language.
        
        Args:
            query: Natural language research question
            user_id: User email/ID from session
            top_k: Number of results to return (max 20)
        
        Returns:
            {
                "status": "success" | "blocked" | "error",
                "results": [...],  # If successful
                "message": "...",   # If blocked
                "error": "..."      # If error
            }
        """
        try:
            response = requests.post(
                f"{self.mcp_server_url}/tools/search_health_studies",
                json={
                    "query": query,
                    "user_id": user_id,
                    "top_k": min(top_k, 20)  # Enforce max limit
                },
                timeout=30
            )
            return response.json()
        except Exception as e:
            logger.exception(f"Error calling search_health_studies: {e}")
            return {
                "status": "error",
                "error": "Research search service is temporarily unavailable"
            }
    
    def get_study_details(
        self,
        nct_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific clinical study.
        
        Args:
            nct_id: NCT ID (e.g., "NCT12345678")
            user_id: User email/ID from session
        
        Returns:
            {
                "status": "success" | "blocked" | "error",
                "study": {...},     # If successful
                "message": "...",   # If blocked
                "error": "..."      # If error
            }
        """
        try:
            response = requests.post(
                f"{self.mcp_server_url}/tools/get_study_details",
                json={
                    "nct_id": nct_id,
                    "user_id": user_id
                },
                timeout=30
            )
            return response.json()
        except Exception as e:
            logger.exception(f"Error calling get_study_details: {e}")
            return {
                "status": "error",
                "error": "Study details service is temporarily unavailable"
            }
    
    def search_health_knowledge(
        self,
        query: str,
        user_id: str,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Search the health knowledge base using semantic similarity.
        
        Args:
            query: Natural language query
            user_id: User email/ID from session
            top_k: Number of chunks to return (max 20)
        
        Returns:
            {
                "status": "success" | "blocked" | "error",
                "results": [...],  # If successful
                "message": "...",   # If blocked
                "error": "..."      # If error
            }
        """
        try:
            response = requests.post(
                f"{self.mcp_server_url}/tools/search_health_knowledge",
                json={
                    "query": query,
                    "user_id": user_id,
                    "top_k": min(top_k, 20)
                },
                timeout=30
            )
            return response.json()
        except Exception as e:
            logger.exception(f"Error calling search_health_knowledge: {e}")
            return {
                "status": "error",
                "error": "Knowledge search service is temporarily unavailable"
            }
    
    def save_research_study(
        self,
        nct_id: str,
        user_id: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Save a clinical study to the user's research collection.
        
        This is a WRITE operation that mutates the Lakebase database.
        
        Args:
            nct_id: NCT ID to save
            user_id: User email/ID from session
            notes: Optional research notes
        
        Returns:
            {
                "status": "success" | "blocked" | "error",
                "message": "..."
            }
        """
        try:
            response = requests.post(
                f"{self.mcp_server_url}/tools/save_research_study",
                json={
                    "nct_id": nct_id,
                    "user_id": user_id,
                    "notes": notes or ""
                },
                timeout=30
            )
            return response.json()
        except Exception as e:
            logger.exception(f"Error calling save_research_study: {e}")
            return {
                "status": "error",
                "error": "Unable to save study at this time"
            }
    
    def get_research_collection(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Get the user's saved research collection.
        
        Args:
            user_id: User email/ID from session
            page: Page number (1-indexed)
            page_size: Results per page (max 50)
        
        Returns:
            {
                "status": "success" | "error",
                "collection": [...],
                "total": int,
                "page": int,
                "error": "..."  # If error
            }
        """
        try:
            response = requests.post(
                f"{self.mcp_server_url}/tools/get_research_collection",
                json={
                    "user_id": user_id,
                    "page": page,
                    "page_size": min(page_size, 50)
                },
                timeout=30
            )
            return response.json()
        except Exception as e:
            logger.exception(f"Error calling get_research_collection: {e}")
            return {
                "status": "error",
                "error": "Unable to load collection at this time"
            }
    
    def remove_research_study(
        self,
        nct_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Remove a study from the user's research collection.
        
        This is a WRITE operation that mutates the Lakebase database.
        
        Args:
            nct_id: NCT ID to remove
            user_id: User email/ID from session
        
        Returns:
            {
                "status": "success" | "error",
                "message": "..."
            }
        """
        try:
            response = requests.post(
                f"{self.mcp_server_url}/tools/remove_research_study",
                json={
                    "nct_id": nct_id,
                    "user_id": user_id
                },
                timeout=30
            )
            return response.json()
        except Exception as e:
            logger.exception(f"Error calling remove_research_study: {e}")
            return {
                "status": "error",
                "error": "Unable to remove study at this time"
            }


# Tool definitions for Agent Bricks registration
TOOL_DEFINITIONS = [
    {
        "name": "search_health_studies",
        "description": "Search women's health clinical studies using natural language. Returns relevant studies from ClinicalTrials.gov with semantic similarity ranking.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language research question (e.g., 'Find recruiting menopause studies related to sleep problems')"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5, max: 20)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_study_details",
        "description": "Get detailed information about a specific clinical study by NCT ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "nct_id": {
                    "type": "string",
                    "description": "NCT ID of the study (e.g., 'NCT12345678')"
                }
            },
            "required": ["nct_id"]
        }
    },
    {
        "name": "search_health_knowledge",
        "description": "Search the health knowledge base using semantic similarity. Returns relevant text chunks from clinical studies.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query about health topics"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of chunks to return (default: 5, max: 20)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "save_research_study",
        "description": "Save a clinical study to the user's research collection. This creates a permanent record in the database.",
        "parameters": {
            "type": "object",
            "properties": {
                "nct_id": {
                    "type": "string",
                    "description": "NCT ID of the study to save"
                },
                "notes": {
                    "type": "string",
                    "description": "Optional research notes about why this study is relevant",
                    "default": ""
                }
            },
            "required": ["nct_id"]
        }
    },
    {
        "name": "get_research_collection",
        "description": "Get the user's saved research collection with pagination.",
        "parameters": {
            "type": "object",
            "properties": {
                "page": {
                    "type": "integer",
                    "description": "Page number (1-indexed, default: 1)",
                    "default": 1
                },
                "page_size": {
                    "type": "integer",
                    "description": "Results per page (default: 20, max: 50)",
                    "default": 20
                }
            },
            "required": []
        }
    },
    {
        "name": "remove_research_study",
        "description": "Remove a study from the user's research collection. This deletes the record from the database.",
        "parameters": {
            "type": "object",
            "properties": {
                "nct_id": {
                    "type": "string",
                    "description": "NCT ID of the study to remove"
                }
            },
            "required": ["nct_id"]
        }
    }
]
