"""
Configuration for MongoDB Document Store
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class MongoConfig:
    """MongoDB configuration settings."""
    
    # MongoDB connection settings
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DATABASE_NAME: str = os.getenv("MONGODB_DATABASE", "erp_document_store")
    
    # Collection names
    COLLECTIONS = {
        "products": "product_catalog",
        "reviews": "customer_reviews", 
        "support_tickets": "support_tickets",
        "marketing_campaigns": "marketing_campaigns",
        "knowledge_base": "knowledge_base",
        "user_interactions": "user_interactions"
    }
    
    # Data generation settings
    DEFAULT_SEED: int = 42
    
    # Batch processing settings
    BATCH_SIZE: int = 1000
    
    # Connection settings
    CONNECTION_TIMEOUT_MS: int = 5000
    SERVER_SELECTION_TIMEOUT_MS: int = 5000
    
    @classmethod
    def get_collection_name(cls, collection_type: str) -> str:
        """Get the collection name for a given type."""
        return cls.COLLECTIONS.get(collection_type, collection_type)
    
    @classmethod
    def validate_config(cls) -> bool:
        """Validate the configuration."""
        required_vars = ["MONGODB_URL", "DATABASE_NAME"]
        for var in required_vars:
            if not getattr(cls, var):
                raise ValueError(f"Missing required configuration: {var}")
        return True

# Global configuration instance
config = MongoConfig()