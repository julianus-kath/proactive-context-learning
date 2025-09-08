"""
MongoDB connection management for the document store.
"""

import logging
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import asyncio

from config import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MongoDBManager:
    """Manages MongoDB connections and operations."""
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None
        self.sync_client: Optional[MongoClient] = None
        self._collections: Dict[str, AsyncIOMotorCollection] = {}
        
    async def connect(self) -> bool:
        """Establish connection to MongoDB."""
        try:
            # Create async client
            self.client = AsyncIOMotorClient(
                config.MONGODB_URL,
                serverSelectionTimeoutMS=config.SERVER_SELECTION_TIMEOUT_MS,
                connectTimeoutMS=config.CONNECTION_TIMEOUT_MS
            )
            
            # Test the connection
            await self.client.admin.command('ping')
            
            # Get database
            self.database = self.client[config.DATABASE_NAME]
            
            # Create sync client for certain operations
            self.sync_client = MongoClient(
                config.MONGODB_URL,
                serverSelectionTimeoutMS=config.SERVER_SELECTION_TIMEOUT_MS,
                connectTimeoutMS=config.CONNECTION_TIMEOUT_MS
            )
            
            logger.info(f"✅ Connected to MongoDB: {config.DATABASE_NAME}")
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"❌ Failed to connect to MongoDB: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error connecting to MongoDB: {e}")
            return False
    
    async def disconnect(self):
        """Close MongoDB connections."""
        if self.client:
            self.client.close()
            logger.info("✅ Disconnected from MongoDB")
        
        if self.sync_client:
            self.sync_client.close()
    
    def get_collection(self, collection_name: str) -> AsyncIOMotorCollection:
        """Get a collection by name."""
        if not self.database:
            raise RuntimeError("Database not connected")
        
        if collection_name not in self._collections:
            self._collections[collection_name] = self.database[collection_name]
        
        return self._collections[collection_name]
    
    async def create_indexes(self):
        """Create necessary indexes for optimal performance."""
        try:
            # Product catalog indexes
            products_collection = self.get_collection(config.COLLECTIONS["products"])
            await products_collection.create_index("product_id", unique=True)
            await products_collection.create_index("category")
            await products_collection.create_index("subcategory")
            await products_collection.create_index([("name", "text"), ("description", "text")])
            
            # Customer reviews indexes
            reviews_collection = self.get_collection(config.COLLECTIONS["reviews"])
            await reviews_collection.create_index("product_id")
            await reviews_collection.create_index("customer_id")
            await reviews_collection.create_index("rating")
            await reviews_collection.create_index("review_date")
            await reviews_collection.create_index("sentiment")
            await reviews_collection.create_index([("title", "text"), ("content", "text")])
            
            # Support tickets indexes
            tickets_collection = self.get_collection(config.COLLECTIONS["support_tickets"])
            await tickets_collection.create_index("ticket_id", unique=True)
            await tickets_collection.create_index("customer_id")
            await tickets_collection.create_index("product_id")
            await tickets_collection.create_index("status")
            await tickets_collection.create_index("priority")
            await tickets_collection.create_index("created_date")
            
            # Marketing campaigns indexes
            campaigns_collection = self.get_collection(config.COLLECTIONS["marketing_campaigns"])
            await campaigns_collection.create_index("campaign_id", unique=True)
            await campaigns_collection.create_index("status")
            await campaigns_collection.create_index("start_date")
            await campaigns_collection.create_index("end_date")
            await campaigns_collection.create_index("target_products")
            
            # Knowledge base indexes
            kb_collection = self.get_collection(config.COLLECTIONS["knowledge_base"])
            await kb_collection.create_index("article_id", unique=True)
            await kb_collection.create_index("category")
            await kb_collection.create_index("tags")
            await kb_collection.create_index([("title", "text"), ("content", "text")])
            
            logger.info("✅ Created MongoDB indexes")
            
        except Exception as e:
            logger.error(f"❌ Failed to create indexes: {e}")
            raise
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        if not self.database:
            raise RuntimeError("Database not connected")
        
        stats = {}
        
        try:
            # Get database stats
            db_stats = await self.database.command("dbStats")
            stats["database"] = {
                "name": config.DATABASE_NAME,
                "collections": db_stats.get("collections", 0),
                "objects": db_stats.get("objects", 0),
                "dataSize": db_stats.get("dataSize", 0),
                "storageSize": db_stats.get("storageSize", 0)
            }
            
            # Get collection stats
            stats["collections"] = {}
            for collection_type, collection_name in config.COLLECTIONS.items():
                try:
                    collection = self.get_collection(collection_name)
                    count = await collection.count_documents({})
                    stats["collections"][collection_type] = {
                        "name": collection_name,
                        "count": count
                    }
                except Exception as e:
                    logger.warning(f"Could not get stats for collection {collection_name}: {e}")
                    stats["collections"][collection_type] = {
                        "name": collection_name,
                        "count": 0,
                        "error": str(e)
                    }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the MongoDB connection."""
        try:
            if not self.client:
                return {"status": "disconnected", "error": "No client connection"}
            
            # Ping the database
            await self.client.admin.command('ping')
            
            # Get basic stats
            stats = await self.get_database_stats()
            
            return {
                "status": "healthy",
                "database": config.DATABASE_NAME,
                "url": config.MONGODB_URL.replace(config.MONGODB_URL.split('@')[-1].split('/')[0], "***") if '@' in config.MONGODB_URL else config.MONGODB_URL,
                "stats": stats
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

# Global MongoDB manager instance
mongodb_manager = MongoDBManager()