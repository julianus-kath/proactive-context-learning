"""
Configuration module for the crawling agent.

This module provides configuration settings for the crawling agent.
"""
import os
from typing import Dict, Any, Optional

# Default OpenAI API key (replace with your own or use environment variable)
OPENAI_API_KEY = "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"

# Default LLM settings
DEFAULT_LLM_TYPE = "openai"
DEFAULT_LLM_MODEL = "gpt-4o"

# Server URLs
ERP_SERVER_URL = "http://localhost:8001/sse"
DOCUMENT_STORAGE_SERVER_URL = "http://localhost:8002/sse"
KNOWLEDGE_GRAPH_SERVER_URL = "http://localhost:8003/sse"

# Agent settings
MAX_REASONING_STEPS = 5
DEBUG_MODE = False

# Database paths
DB_PATH = "/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/synthetic_data.db"
JSON_PATH = "/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/mongodb_data.json"

# Load environment variables
def load_from_env():
    """Load configuration from environment variables."""
    global OPENAI_API_KEY, DEFAULT_LLM_TYPE, DEFAULT_LLM_MODEL
    global ERP_SERVER_URL, DOCUMENT_STORAGE_SERVER_URL, KNOWLEDGE_GRAPH_SERVER_URL
    global MAX_REASONING_STEPS, DEBUG_MODE
    global DB_PATH, JSON_PATH
    
    # LLM settings
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", OPENAI_API_KEY)
    DEFAULT_LLM_TYPE = os.environ.get("DEFAULT_LLM_TYPE", DEFAULT_LLM_TYPE)
    DEFAULT_LLM_MODEL = os.environ.get("DEFAULT_LLM_MODEL", DEFAULT_LLM_MODEL)
    
    # Server URLs
    ERP_SERVER_URL = os.environ.get("ERP_SERVER_URL", ERP_SERVER_URL)
    DOCUMENT_STORAGE_SERVER_URL = os.environ.get("DOCUMENT_STORAGE_SERVER_URL", DOCUMENT_STORAGE_SERVER_URL)
    KNOWLEDGE_GRAPH_SERVER_URL = os.environ.get("KNOWLEDGE_GRAPH_SERVER_URL", KNOWLEDGE_GRAPH_SERVER_URL)
    
    # Agent settings
    MAX_REASONING_STEPS = int(os.environ.get("MAX_REASONING_STEPS", MAX_REASONING_STEPS))
    DEBUG_MODE = os.environ.get("DEBUG_MODE", "").lower() in ("true", "1", "yes")
    
    # Database paths
    DB_PATH = os.environ.get("DB_PATH", DB_PATH)
    JSON_PATH = os.environ.get("JSON_PATH", JSON_PATH)

# Load configuration from environment variables
load_from_env()

# Export all settings as a dictionary
def get_all_settings() -> Dict[str, Any]:
    """Get all configuration settings as a dictionary."""
    return {
        "OPENAI_API_KEY": OPENAI_API_KEY,
        "DEFAULT_LLM_TYPE": DEFAULT_LLM_TYPE,
        "DEFAULT_LLM_MODEL": DEFAULT_LLM_MODEL,
        "ERP_SERVER_URL": ERP_SERVER_URL,
        "DOCUMENT_STORAGE_SERVER_URL": DOCUMENT_STORAGE_SERVER_URL,
        "KNOWLEDGE_GRAPH_SERVER_URL": KNOWLEDGE_GRAPH_SERVER_URL,
        "MAX_REASONING_STEPS": MAX_REASONING_STEPS,
        "DEBUG_MODE": DEBUG_MODE,
        "DB_PATH": DB_PATH,
        "JSON_PATH": JSON_PATH,
    }