# MongoDB Integration Guide for LangGraph Agent

## Overview

The codebase already includes a **comprehensive MongoDB integration** that's ready to be connected to the LangGraph database agent. This integration provides document-based querying capabilities alongside the existing SQL database functionality.

## Existing MongoDB Infrastructure

### ✅ **Already Available:**

1. **Complete MongoDB Manager** (`mongodb_document_store/connection.py`)
   - Async connection management with Motor
   - Connection pooling and error handling
   - Health checks and database statistics

2. **Rich Data Models** (`mongodb_document_store/models.py`)
   - Product catalog with specifications and media
   - Customer reviews with sentiment analysis
   - Support tickets with full lifecycle tracking
   - Marketing campaigns with performance metrics
   - Knowledge base articles

3. **Advanced Query Interface** (`mongodb_document_store/query_interface.py`)
   - Natural language search capabilities
   - Complex aggregation pipelines
   - Analytics and reporting functions

4. **Synthetic Data Generation** (`mongodb_document_store/generator.py`)
   - Realistic test data generation
   - Proper relationships between documents
   - Configurable data volumes

## How Easy Is It to Connect?

### 🚀 **Super Easy! Just 3 Steps:**

## Step 1: Create MongoDB Database Client

```python
# langgraph_integration/mongo_db_client.py
import asyncio
import logging
from typing import List, Dict, Any, Optional
import sys
import os

# Add the project root to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from mongodb_document_store import mongodb_manager, mongo_query

logger = logging.getLogger(__name__)

class MongoDBClient:
    """MongoDB client for document-based queries."""
    
    def __init__(self):
        self.initialized = False
    
    async def _ensure_initialized(self):
        """Ensure MongoDB connection is initialized."""
        if not self.initialized:
            success = await mongodb_manager.connect()
            if success:
                self.initialized = True
            else:
                raise Exception("Failed to connect to MongoDB")
    
    async def search_products(self, query: str, **filters) -> str:
        """Search products in MongoDB."""
        try:
            await self._ensure_initialized()
            
            products = await mongo_query.search_products(
                query=query,
                **filters
            )
            
            if not products:
                return "No products found matching your criteria."
            
            # Format results
            result_lines = [f"Found {len(products)} products:"]
            for product in products[:10]:  # Limit to 10 results
                result_lines.append(
                    f"- {product['name']} (${product['price']}) - {product['category']}"
                )
            
            return "\n".join(result_lines)
            
        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return f"Error searching products: {str(e)}"
    
    async def get_product_reviews(self, product_id: int, **filters) -> str:
        """Get reviews for a specific product."""
        try:
            await self._ensure_initialized()
            
            reviews = await mongo_query.get_product_reviews(
                product_id=product_id,
                **filters
            )
            
            if not reviews:
                return f"No reviews found for product {product_id}."
            
            # Format results
            result_lines = [f"Found {len(reviews)} reviews for product {product_id}:"]
            for review in reviews[:5]:  # Limit to 5 reviews
                result_lines.append(
                    f"- Rating: {review['rating']}/5 - {review['title']}"
                )
                result_lines.append(f"  \"{review['content'][:100]}...\"")
            
            return "\n".join(result_lines)
            
        except Exception as e:
            logger.error(f"Error getting reviews: {e}")
            return f"Error getting reviews: {str(e)}"
    
    async def search_support_tickets(self, **filters) -> str:
        """Search support tickets."""
        try:
            await self._ensure_initialized()
            
            tickets = await mongo_query.search_support_tickets(**filters)
            
            if not tickets:
                return "No support tickets found matching your criteria."
            
            # Format results
            result_lines = [f"Found {len(tickets)} support tickets:"]
            for ticket in tickets[:10]:
                result_lines.append(
                    f"- {ticket['ticket_id']}: {ticket['subject']} ({ticket['status']})"
                )
            
            return "\n".join(result_lines)
            
        except Exception as e:
            logger.error(f"Error searching tickets: {e}")
            return f"Error searching tickets: {str(e)}"
    
    async def search_knowledge_base(self, query: str, **filters) -> str:
        """Search knowledge base articles."""
        try:
            await self._ensure_initialized()
            
            articles = await mongo_query.search_knowledge_base(
                query=query,
                **filters
            )
            
            if not articles:
                return "No knowledge base articles found."
            
            # Format results
            result_lines = [f"Found {len(articles)} knowledge base articles:"]
            for article in articles[:5]:
                result_lines.append(
                    f"- {article['title']} ({article['category']})"
                )
                result_lines.append(f"  {article['content'][:150]}...")
            
            return "\n".join(result_lines)
            
        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}")
            return f"Error searching knowledge base: {str(e)}"
    
    async def get_analytics(self, analytics_type: str, **params) -> str:
        """Get various analytics from MongoDB."""
        try:
            await self._ensure_initialized()
            
            if analytics_type == "review_analytics":
                product_id = params.get('product_id')
                analytics = await mongo_query.get_review_analytics(product_id)
                return f"Review Analytics: {analytics}"
            
            elif analytics_type == "ticket_analytics":
                analytics = await mongo_query.get_ticket_analytics()
                return f"Ticket Analytics: {analytics}"
            
            else:
                return f"Unknown analytics type: {analytics_type}"
                
        except Exception as e:
            logger.error(f"Error getting analytics: {e}")
            return f"Error getting analytics: {str(e)}"
    
    async def health_check(self) -> bool:
        """Check MongoDB connection health."""
        try:
            await self._ensure_initialized()
            return await mongodb_manager.health_check()
        except Exception:
            return False

# Global instance
_mongo_client = MongoDBClient()

# Utility functions
async def search_products(query: str, **filters) -> str:
    """Search products in MongoDB."""
    return await _mongo_client.search_products(query, **filters)

async def get_product_reviews(product_id: int, **filters) -> str:
    """Get product reviews from MongoDB."""
    return await _mongo_client.get_product_reviews(product_id, **filters)

async def search_support_tickets(**filters) -> str:
    """Search support tickets in MongoDB."""
    return await _mongo_client.search_support_tickets(**filters)

async def search_knowledge_base(query: str, **filters) -> str:
    """Search knowledge base in MongoDB."""
    return await _mongo_client.search_knowledge_base(query, **filters)

async def get_mongo_analytics(analytics_type: str, **params) -> str:
    """Get analytics from MongoDB."""
    return await _mongo_client.get_analytics(analytics_type, **params)

async def mongo_health_check() -> bool:
    """Check MongoDB health."""
    return await _mongo_client.health_check()
```

## Step 2: Update LangGraph Prompts for MongoDB

```python
# Add to langgraph_integration/prompts.py

MONGODB_INTENT_PARSER_PROMPT = """
You are an intent parser for a hybrid database system that includes both SQL (PostgreSQL) and NoSQL (MongoDB) databases.

SQL Database contains:
- Structured data: customers, orders, products, inventory
- Transactional data with relationships

MongoDB Database contains:
- Product catalog with detailed specifications
- Customer reviews and ratings
- Support tickets and conversations
- Marketing campaigns and analytics
- Knowledge base articles

Analyze the user's question and determine:
1. Which database type to use (SQL, MONGODB, or BOTH)
2. What specific operation to perform

Examples:

User: "Show me customer reviews for product 123"
Intent: MONGODB_QUERY
Operation: get_product_reviews
Parameters: {"product_id": 123}

User: "Find smartphones under $500"
Intent: MONGODB_QUERY  
Operation: search_products
Parameters: {"query": "smartphone", "price_max": 500}

User: "What support tickets are still open?"
Intent: MONGODB_QUERY
Operation: search_support_tickets
Parameters: {"status": "open"}

User: "How many orders did we have last month?"
Intent: SQL_QUERY
Operation: execute_sql
SQL: SELECT COUNT(*) FROM webshop.order WHERE EXTRACT(MONTH FROM ordertimestamp) = EXTRACT(MONTH FROM CURRENT_DATE - INTERVAL '1 month')

User: "Show me the order details and customer reviews for order 123"
Intent: HYBRID_QUERY
Operations: ["get_order_details", "get_product_reviews"]

User Question: {user_question}

Respond with:
Intent: [SQL_QUERY|MONGODB_QUERY|HYBRID_QUERY]
Operation: [operation_name]
Parameters: {parameters_dict}
SQL: [sql_query if SQL_QUERY]
"""

MONGODB_QUERY_EXAMPLES = """
MongoDB Query Examples:

1. Product Search:
   - "Find laptops under $1000" → search_products(query="laptop", price_max=1000)
   - "Show me gaming products" → search_products(category="Gaming")

2. Review Analysis:
   - "What do customers say about product 5?" → get_product_reviews(product_id=5)
   - "Show positive reviews for smartphones" → get_product_reviews(sentiment="positive", query="smartphone")

3. Support Tickets:
   - "What tickets are high priority?" → search_support_tickets(priority="high")
   - "Show resolved tickets from last week" → search_support_tickets(status="resolved")

4. Knowledge Base:
   - "How to install the app?" → search_knowledge_base(query="installation guide")
   - "Troubleshooting network issues" → search_knowledge_base(query="network troubleshooting")

5. Analytics:
   - "Review analytics for product 10" → get_mongo_analytics("review_analytics", product_id=10)
   - "Support ticket statistics" → get_mongo_analytics("ticket_analytics")
"""
```

## Step 3: Update Graph Definition for Hybrid Queries

```python
# Add to langgraph_integration/graph_definition.py

from .mongo_db_client import (
    search_products, get_product_reviews, search_support_tickets,
    search_knowledge_base, get_mongo_analytics, mongo_health_check
)

# Add MongoDB operations to the workflow
async def execute_mongodb_query(state: AgentState) -> AgentState:
    """Execute MongoDB document queries."""
    try:
        operation = state.get("operation")
        parameters = state.get("parameters", {})
        
        if operation == "search_products":
            result = await search_products(**parameters)
        elif operation == "get_product_reviews":
            result = await get_product_reviews(**parameters)
        elif operation == "search_support_tickets":
            result = await search_support_tickets(**parameters)
        elif operation == "search_knowledge_base":
            result = await search_knowledge_base(**parameters)
        elif operation == "get_mongo_analytics":
            result = await get_mongo_analytics(**parameters)
        else:
            result = f"Unknown MongoDB operation: {operation}"
        
        return {
            **state,
            "query_result": result,
            "operation": "mongodb_query_executed"
        }
        
    except Exception as e:
        logger.error(f"MongoDB query error: {e}")
        return {
            **state,
            "query_result": f"MongoDB Error: {str(e)}",
            "operation": "error"
        }

# Update the workflow to include MongoDB path
def create_enhanced_workflow():
    """Create workflow with both SQL and MongoDB support."""
    
    workflow = StateGraph(AgentState)
    
    # Add all existing nodes
    workflow.add_node("parse_intent", parse_intent)
    workflow.add_node("execute_sql_query", execute_sql_query)
    workflow.add_node("execute_mongodb_query", execute_mongodb_query)  # New!
    workflow.add_node("format_results", format_results)
    
    # Add routing logic
    def route_query(state: AgentState) -> str:
        intent = state.get("intent", "")
        if intent == "SQL_QUERY":
            return "execute_sql_query"
        elif intent == "MONGODB_QUERY":
            return "execute_mongodb_query"
        elif intent == "HYBRID_QUERY":
            return "execute_hybrid_query"  # Could implement this too
        else:
            return "format_results"
    
    # Set up the workflow
    workflow.set_entry_point("parse_intent")
    workflow.add_conditional_edges("parse_intent", route_query)
    workflow.add_edge("execute_sql_query", "format_results")
    workflow.add_edge("execute_mongodb_query", "format_results")
    workflow.add_edge("format_results", END)
    
    return workflow.compile()
```

## Configuration

### Environment Setup
```bash
# Add to .env file
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=erp_document_store
```

### Initialize MongoDB Data
```bash
cd mongodb_document_store
python setup_database.py --setup --populate
```

## Example Queries After Integration

### 1. Product Search
**User:** "Find smartphones under $800"
**Response:** MongoDB searches product catalog and returns matching products with specifications

### 2. Review Analysis  
**User:** "What do customers say about product 5?"
**Response:** MongoDB returns customer reviews with ratings and sentiment analysis

### 3. Support Insights
**User:** "What are the most common support issues?"
**Response:** MongoDB analyzes support tickets and returns categorized issues

### 4. Hybrid Queries
**User:** "Show me order 123 details and customer reviews for those products"
**Response:** SQL gets order details, MongoDB gets reviews, combined response

## Benefits of This Integration

### ✅ **Immediate Benefits:**
1. **Rich Document Queries**: Search products, reviews, support tickets
2. **Natural Language Search**: Full-text search across document fields
3. **Analytics & Insights**: Built-in aggregation pipelines for analytics
4. **Flexible Schema**: Handle complex nested data structures
5. **Complementary Data**: Documents complement relational data

### ✅ **Advanced Capabilities:**
1. **Sentiment Analysis**: Analyze customer sentiment from reviews
2. **Knowledge Base Search**: Find relevant help articles
3. **Support Ticket Analytics**: Track resolution times and patterns
4. **Marketing Campaign Analysis**: Measure campaign effectiveness
5. **Product Recommendation**: Based on reviews and specifications

## Current Status

### ✅ **Ready to Use:**
- Complete MongoDB infrastructure exists
- Comprehensive data models and query interface
- Async operations compatible with LangGraph
- Rich synthetic data for testing

### 🔧 **Integration Needed:**
- Connect MongoDB client to LangGraph workflow (3 steps above)
- Update prompts for hybrid SQL/MongoDB queries
- Add routing logic for different query types

## Summary

**Adding MongoDB to the LangGraph agent is extremely easy** because:

1. **Infrastructure exists**: Complete MongoDB system already built
2. **Simple integration**: Just 3 files to create/modify
3. **Rich capabilities**: Immediate access to document search, analytics, reviews
4. **Complementary**: Enhances SQL capabilities rather than replacing them

The MongoDB integration would give your agent powerful document search and analytics capabilities alongside the existing SQL database functionality!