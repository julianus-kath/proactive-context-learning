"""
Document Store API for the crawling agent system.
"""
import os
import json
import logging
import argparse
from typing import Dict, List, Any, Optional, Union
from fastapi import FastAPI, HTTPException, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import motor.motor_asyncio
from pymongo import ASCENDING, TEXT

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DocumentQuery(BaseModel):
    """Model for document queries."""
    query: str = Field(..., description="The query to execute")
    collection: str = Field(..., description="The collection to query")
    limit: int = Field(10, description="Maximum number of documents to return")
    skip: int = Field(0, description="Number of documents to skip")


class DocumentMetadata(BaseModel):
    """Model for document collection metadata."""
    name: str = Field(..., description="Collection name")
    document_count: int = Field(..., description="Number of documents in the collection")
    sample_document: Optional[Dict[str, Any]] = Field(None, description="Sample document from the collection")


class DocumentStoreMetadata(BaseModel):
    """Model for document store metadata."""
    collections: List[DocumentMetadata] = Field(..., description="List of collections in the document store")


class DocumentStoreAPI:
    """
    API for the document store.
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8002
    ):
        """
        Initialize the Document Store API.
        
        Args:
            host: Host to bind the server to
            port: Port to bind the server to
        """
        self.host = host
        self.port = port
        
        # Get MongoDB connection details from environment variables
        self.mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
        self.mongo_db = os.environ.get("MONGO_DB", "document_store")
        
        # Initialize MongoDB client
        self.client = motor.motor_asyncio.AsyncIOMotorClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]
        
        # Create the FastAPI app
        self.app = FastAPI(
            title="Document Store API",
            description="API for the document store",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc",
            openapi_url="/openapi.json"
        )
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Register routes
        self._register_routes()
        
        logger.info(f"Initialized Document Store API on {host}:{port}")
        logger.info(f"Connected to MongoDB at {self.mongo_uri}, database: {self.mongo_db}")
    
    async def _ensure_indexes(self):
        """Ensure text indexes exist on all collections."""
        collections = await self.db.list_collection_names()
        for collection_name in collections:
            # Create a text index on all string fields
            await self.db[collection_name].create_index([("$**", TEXT)])
            logger.info(f"Created text index on collection: {collection_name}")
    
    def _register_routes(self):
        """Register API routes."""
        
        @self.app.on_event("startup")
        async def startup_event():
            """Startup event handler."""
            await self._ensure_indexes()
        
        @self.app.get("/", tags=["General"])
        async def root():
            """Root endpoint that returns basic server information."""
            return {
                "service": "Document Store API",
                "version": "1.0.0",
                "status": "online",
                "mongo_uri": self.mongo_uri,
                "mongo_db": self.mongo_db
            }
        
        @self.app.get("/health", tags=["General"])
        async def health_check():
            """Health check endpoint."""
            try:
                # Ping the MongoDB server
                await self.client.admin.command("ping")
                return {"status": "healthy", "database": "connected"}
            except Exception as e:
                logger.error(f"Health check failed: {str(e)}")
                return {"status": "unhealthy", "error": str(e)}
        
        @self.app.get("/metadata", tags=["Metadata"], response_model=DocumentStoreMetadata)
        async def get_metadata():
            """Get metadata about the document store (collections and sample documents)."""
            try:
                # Get list of collections
                collections = await self.db.list_collection_names()
                
                # Get metadata for each collection
                collection_metadata = []
                for collection_name in collections:
                    # Get document count
                    document_count = await self.db[collection_name].count_documents({})
                    
                    # Get a sample document
                    sample_document = await self.db[collection_name].find_one()
                    if sample_document:
                        # Convert ObjectId to string
                        sample_document["_id"] = str(sample_document["_id"])
                    
                    collection_metadata.append(
                        DocumentMetadata(
                            name=collection_name,
                            document_count=document_count,
                            sample_document=sample_document
                        )
                    )
                
                return DocumentStoreMetadata(collections=collection_metadata)
                
            except Exception as e:
                logger.error(f"Error getting metadata: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/query", tags=["Query"])
        async def query_documents(query: DocumentQuery):
            """Query documents in the document store."""
            try:
                collection_name = query.collection
                
                # Check if collection exists
                collections = await self.db.list_collection_names()
                if collection_name not in collections:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Collection not found: {collection_name}"
                    )
                
                # Get the collection
                collection = self.db[collection_name]
                
                # Perform a text search if the query is not empty
                if query.query.strip():
                    # Use text search
                    cursor = collection.find(
                        {"$text": {"$search": query.query}},
                        {"score": {"$meta": "textScore"}}
                    ).sort([("score", {"$meta": "textScore"})]).skip(query.skip).limit(query.limit)
                else:
                    # Return all documents
                    cursor = collection.find({}).skip(query.skip).limit(query.limit)
                
                # Convert cursor to list
                documents = await cursor.to_list(length=query.limit)
                
                # Convert ObjectId to string
                for document in documents:
                    document["_id"] = str(document["_id"])
                
                # Return the results
                return {
                    "query": query.query,
                    "collection": collection_name,
                    "data": documents,
                    "metadata": {
                        "count": len(documents),
                        "skip": query.skip,
                        "limit": query.limit
                    }
                }
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error querying documents: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/populate", tags=["Admin"])
        async def populate_collection(
            collection_name: str = Body(..., embed=True),
            documents: List[Dict[str, Any]] = Body(..., embed=True)
        ):
            """
            Populate a collection with documents.
            
            This endpoint is for testing and development purposes.
            """
            try:
                # Get the collection
                collection = self.db[collection_name]
                
                # Insert the documents
                result = await collection.insert_many(documents)
                
                # Create text index
                await collection.create_index([("$**", TEXT)])
                
                return {
                    "status": "success",
                    "collection": collection_name,
                    "inserted_count": len(result.inserted_ids),
                    "inserted_ids": [str(id) for id in result.inserted_ids]
                }
                
            except Exception as e:
                logger.error(f"Error populating collection: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
    
    def run(self):
        """Run the Document Store API."""
        logger.info(f"Starting Document Store API on {self.host}:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port)


def main():
    """Run the Document Store API."""
    parser = argparse.ArgumentParser(description="Document Store API")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8002, help="Port to bind the server to")
    
    args = parser.parse_args()
    
    api = DocumentStoreAPI(
        host=args.host,
        port=args.port
    )
    
    api.run()


if __name__ == "__main__":
    main()