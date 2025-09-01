"""
MongoDB query interface for the MCP server integration.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import json
import re

from connection import mongodb_manager
from config import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MongoQueryInterface:
    """Interface for querying MongoDB documents with natural language support."""
    
    def __init__(self):
        self.collection_mappings = {
            "products": config.COLLECTIONS["products"],
            "reviews": config.COLLECTIONS["reviews"],
            "tickets": config.COLLECTIONS["support_tickets"],
            "campaigns": config.COLLECTIONS["marketing_campaigns"],
            "knowledge": config.COLLECTIONS["knowledge_base"],
            "interactions": config.COLLECTIONS["user_interactions"]
        }
    
    async def search_products(self, 
                            query: Optional[str] = None,
                            category: Optional[str] = None,
                            price_min: Optional[float] = None,
                            price_max: Optional[float] = None,
                            in_stock: Optional[bool] = None,
                            limit: int = 20) -> List[Dict[str, Any]]:
        """Search products with various filters."""
        
        collection = mongodb_manager.get_collection(self.collection_mappings["products"])
        
        # Build query
        mongo_query = {}
        
        if query:
            # Text search on name and description
            mongo_query["$or"] = [
                {"name": {"$regex": query, "$options": "i"}},
                {"description": {"$regex": query, "$options": "i"}},
                {"detailed_description": {"$regex": query, "$options": "i"}}
            ]
        
        if category:
            mongo_query["category"] = {"$regex": category, "$options": "i"}
        
        if price_min is not None or price_max is not None:
            price_filter = {}
            if price_min is not None:
                price_filter["$gte"] = price_min
            if price_max is not None:
                price_filter["$lte"] = price_max
            mongo_query["price"] = price_filter
        
        if in_stock is not None:
            mongo_query["availability.in_stock"] = in_stock
        
        # Execute query
        cursor = collection.find(mongo_query).limit(limit)
        results = await cursor.to_list(length=limit)
        
        logger.info(f"Found {len(results)} products matching query")
        return results
    
    async def get_product_reviews(self, 
                                product_id: int,
                                sentiment: Optional[str] = None,
                                min_rating: Optional[int] = None,
                                limit: int = 50) -> List[Dict[str, Any]]:
        """Get reviews for a specific product."""
        
        collection = mongodb_manager.get_collection(self.collection_mappings["reviews"])
        
        # Build query
        mongo_query = {"product_id": product_id}
        
        if sentiment:
            mongo_query["sentiment"] = sentiment.lower()
        
        if min_rating is not None:
            mongo_query["rating"] = {"$gte": min_rating}
        
        # Execute query, sorted by date (newest first)
        cursor = collection.find(mongo_query).sort("review_date", -1).limit(limit)
        results = await cursor.to_list(length=limit)
        
        logger.info(f"Found {len(results)} reviews for product {product_id}")
        return results
    
    async def get_customer_reviews(self, 
                                 customer_id: int,
                                 limit: int = 20) -> List[Dict[str, Any]]:
        """Get all reviews by a specific customer."""
        
        collection = mongodb_manager.get_collection(self.collection_mappings["reviews"])
        
        cursor = collection.find({"customer_id": customer_id}).sort("review_date", -1).limit(limit)
        results = await cursor.to_list(length=limit)
        
        logger.info(f"Found {len(results)} reviews by customer {customer_id}")
        return results
    
    async def get_review_analytics(self, product_id: Optional[int] = None) -> Dict[str, Any]:
        """Get review analytics for a product or overall."""
        
        collection = mongodb_manager.get_collection(self.collection_mappings["reviews"])
        
        # Build match stage
        match_stage = {}
        if product_id:
            match_stage["product_id"] = product_id
        
        # Aggregation pipeline
        pipeline = []
        
        if match_stage:
            pipeline.append({"$match": match_stage})
        
        pipeline.extend([
            {
                "$group": {
                    "_id": None,
                    "total_reviews": {"$sum": 1},
                    "average_rating": {"$avg": "$rating"},
                    "sentiment_breakdown": {
                        "$push": "$sentiment"
                    },
                    "rating_breakdown": {
                        "$push": "$rating"
                    }
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "total_reviews": 1,
                    "average_rating": {"$round": ["$average_rating", 2]},
                    "sentiment_counts": {
                        "positive": {
                            "$size": {
                                "$filter": {
                                    "input": "$sentiment_breakdown",
                                    "cond": {"$eq": ["$$this", "positive"]}
                                }
                            }
                        },
                        "neutral": {
                            "$size": {
                                "$filter": {
                                    "input": "$sentiment_breakdown",
                                    "cond": {"$eq": ["$$this", "neutral"]}
                                }
                            }
                        },
                        "negative": {
                            "$size": {
                                "$filter": {
                                    "input": "$sentiment_breakdown",
                                    "cond": {"$eq": ["$$this", "negative"]}
                                }
                            }
                        }
                    },
                    "rating_distribution": {
                        "5_star": {
                            "$size": {
                                "$filter": {
                                    "input": "$rating_breakdown",
                                    "cond": {"$eq": ["$$this", 5]}
                                }
                            }
                        },
                        "4_star": {
                            "$size": {
                                "$filter": {
                                    "input": "$rating_breakdown",
                                    "cond": {"$eq": ["$$this", 4]}
                                }
                            }
                        },
                        "3_star": {
                            "$size": {
                                "$filter": {
                                    "input": "$rating_breakdown",
                                    "cond": {"$eq": ["$$this", 3]}
                                }
                            }
                        },
                        "2_star": {
                            "$size": {
                                "$filter": {
                                    "input": "$rating_breakdown",
                                    "cond": {"$eq": ["$$this", 2]}
                                }
                            }
                        },
                        "1_star": {
                            "$size": {
                                "$filter": {
                                    "input": "$rating_breakdown",
                                    "cond": {"$eq": ["$$this", 1]}
                                }
                            }
                        }
                    }
                }
            }
        ])
        
        cursor = collection.aggregate(pipeline)
        results = await cursor.to_list(length=1)
        
        if results:
            analytics = results[0]
            logger.info(f"Generated review analytics: {analytics['total_reviews']} reviews, avg rating {analytics['average_rating']}")
            return analytics
        else:
            return {
                "total_reviews": 0,
                "average_rating": 0,
                "sentiment_counts": {"positive": 0, "neutral": 0, "negative": 0},
                "rating_distribution": {"5_star": 0, "4_star": 0, "3_star": 0, "2_star": 0, "1_star": 0}
            }
    
    async def search_support_tickets(self,
                                   customer_id: Optional[int] = None,
                                   product_id: Optional[int] = None,
                                   status: Optional[str] = None,
                                   priority: Optional[str] = None,
                                   category: Optional[str] = None,
                                   limit: int = 50) -> List[Dict[str, Any]]:
        """Search support tickets with various filters."""
        
        collection = mongodb_manager.get_collection(self.collection_mappings["tickets"])
        
        # Build query
        mongo_query = {}
        
        if customer_id:
            mongo_query["customer_id"] = customer_id
        
        if product_id:
            mongo_query["product_id"] = product_id
        
        if status:
            mongo_query["status"] = status.lower()
        
        if priority:
            mongo_query["priority"] = priority.lower()
        
        if category:
            mongo_query["category"] = {"$regex": category, "$options": "i"}
        
        # Execute query, sorted by creation date (newest first)
        cursor = collection.find(mongo_query).sort("created_date", -1).limit(limit)
        results = await cursor.to_list(length=limit)
        
        logger.info(f"Found {len(results)} support tickets matching criteria")
        return results
    
    async def get_ticket_analytics(self) -> Dict[str, Any]:
        """Get support ticket analytics."""
        
        collection = mongodb_manager.get_collection(self.collection_mappings["tickets"])
        
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_tickets": {"$sum": 1},
                    "status_breakdown": {"$push": "$status"},
                    "priority_breakdown": {"$push": "$priority"},
                    "category_breakdown": {"$push": "$category"},
                    "avg_resolution_time": {"$avg": "$resolution_time_hours"},
                    "sla_breaches": {
                        "$sum": {"$cond": [{"$eq": ["$sla_breach", True]}, 1, 0]}
                    }
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "total_tickets": 1,
                    "avg_resolution_time_hours": {"$round": ["$avg_resolution_time", 2]},
                    "sla_breach_rate": {
                        "$round": [
                            {"$multiply": [{"$divide": ["$sla_breaches", "$total_tickets"]}, 100]}, 
                            2
                        ]
                    },
                    "status_counts": {
                        "open": {
                            "$size": {
                                "$filter": {
                                    "input": "$status_breakdown",
                                    "cond": {"$eq": ["$$this", "open"]}
                                }
                            }
                        },
                        "in_progress": {
                            "$size": {
                                "$filter": {
                                    "input": "$status_breakdown",
                                    "cond": {"$eq": ["$$this", "in_progress"]}
                                }
                            }
                        },
                        "resolved": {
                            "$size": {
                                "$filter": {
                                    "input": "$status_breakdown",
                                    "cond": {"$eq": ["$$this", "resolved"]}
                                }
                            }
                        },
                        "closed": {
                            "$size": {
                                "$filter": {
                                    "input": "$status_breakdown",
                                    "cond": {"$eq": ["$$this", "closed"]}
                                }
                            }
                        }
                    },
                    "priority_counts": {
                        "low": {
                            "$size": {
                                "$filter": {
                                    "input": "$priority_breakdown",
                                    "cond": {"$eq": ["$$this", "low"]}
                                }
                            }
                        },
                        "medium": {
                            "$size": {
                                "$filter": {
                                    "input": "$priority_breakdown",
                                    "cond": {"$eq": ["$$this", "medium"]}
                                }
                            }
                        },
                        "high": {
                            "$size": {
                                "$filter": {
                                    "input": "$priority_breakdown",
                                    "cond": {"$eq": ["$$this", "high"]}
                                }
                            }
                        },
                        "critical": {
                            "$size": {
                                "$filter": {
                                    "input": "$priority_breakdown",
                                    "cond": {"$eq": ["$$this", "critical"]}
                                }
                            }
                        }
                    }
                }
            }
        ]
        
        cursor = collection.aggregate(pipeline)
        results = await cursor.to_list(length=1)
        
        if results:
            return results[0]
        else:
            return {"total_tickets": 0}
    
    async def search_knowledge_base(self,
                                  query: str,
                                  category: Optional[str] = None,
                                  limit: int = 10) -> List[Dict[str, Any]]:
        """Search knowledge base articles."""
        
        collection = mongodb_manager.get_collection(self.collection_mappings["knowledge"])
        
        # Build query
        mongo_query = {
            "$or": [
                {"title": {"$regex": query, "$options": "i"}},
                {"content": {"$regex": query, "$options": "i"}},
                {"summary": {"$regex": query, "$options": "i"}},
                {"tags": {"$in": [re.compile(query, re.IGNORECASE)]}}
            ]
        }
        
        if category:
            mongo_query["category"] = {"$regex": category, "$options": "i"}
        
        # Execute query, sorted by views (most popular first)
        cursor = collection.find(mongo_query).sort("views", -1).limit(limit)
        results = await cursor.to_list(length=limit)
        
        logger.info(f"Found {len(results)} knowledge base articles matching '{query}'")
        return results
    
    async def get_marketing_campaign_performance(self,
                                               campaign_id: Optional[str] = None,
                                               status: Optional[str] = None,
                                               limit: int = 20) -> List[Dict[str, Any]]:
        """Get marketing campaign performance data."""
        
        collection = mongodb_manager.get_collection(self.collection_mappings["campaigns"])
        
        # Build query
        mongo_query = {}
        
        if campaign_id:
            mongo_query["campaign_id"] = campaign_id
        
        if status:
            mongo_query["status"] = status.lower()
        
        # Execute query
        cursor = collection.find(mongo_query).sort("start_date", -1).limit(limit)
        results = await cursor.to_list(length=limit)
        
        logger.info(f"Found {len(results)} marketing campaigns")
        return results
    
    async def execute_custom_query(self, 
                                 collection_name: str,
                                 query: Dict[str, Any],
                                 limit: int = 100) -> List[Dict[str, Any]]:
        """Execute a custom MongoDB query."""
        
        if collection_name not in self.collection_mappings:
            raise ValueError(f"Unknown collection: {collection_name}")
        
        collection = mongodb_manager.get_collection(self.collection_mappings[collection_name])
        
        try:
            cursor = collection.find(query).limit(limit)
            results = await cursor.to_list(length=limit)
            
            logger.info(f"Custom query returned {len(results)} results from {collection_name}")
            return results
        
        except Exception as e:
            logger.error(f"Error executing custom query: {e}")
            raise
    
    async def get_collection_schema(self, collection_name: str) -> Dict[str, Any]:
        """Get schema information for a collection."""
        
        if collection_name not in self.collection_mappings:
            raise ValueError(f"Unknown collection: {collection_name}")
        
        collection = mongodb_manager.get_collection(self.collection_mappings[collection_name])
        
        # Get a sample document to infer schema
        sample_doc = await collection.find_one()
        
        if not sample_doc:
            return {"error": "Collection is empty"}
        
        # Remove MongoDB's _id field for cleaner schema
        if "_id" in sample_doc:
            del sample_doc["_id"]
        
        # Generate schema information
        schema = {
            "collection": collection_name,
            "sample_document": sample_doc,
            "fields": self._analyze_document_structure(sample_doc),
            "indexes": await self._get_collection_indexes(collection)
        }
        
        return schema
    
    def _analyze_document_structure(self, doc: Dict[str, Any], prefix: str = "") -> Dict[str, str]:
        """Analyze document structure to generate field information."""
        fields = {}
        
        for key, value in doc.items():
            field_path = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                fields[field_path] = "object"
                # Recursively analyze nested objects
                nested_fields = self._analyze_document_structure(value, field_path)
                fields.update(nested_fields)
            elif isinstance(value, list):
                if value and isinstance(value[0], dict):
                    fields[field_path] = "array of objects"
                    # Analyze first object in array
                    nested_fields = self._analyze_document_structure(value[0], f"{field_path}[]")
                    fields.update(nested_fields)
                else:
                    fields[field_path] = f"array of {type(value[0]).__name__ if value else 'unknown'}"
            else:
                fields[field_path] = type(value).__name__
        
        return fields
    
    async def _get_collection_indexes(self, collection) -> List[Dict[str, Any]]:
        """Get index information for a collection."""
        try:
            indexes = []
            async for index in collection.list_indexes():
                indexes.append({
                    "name": index.get("name"),
                    "key": index.get("key"),
                    "unique": index.get("unique", False)
                })
            return indexes
        except Exception as e:
            logger.warning(f"Could not get index information: {e}")
            return []

# Global query interface instance
mongo_query = MongoQueryInterface()