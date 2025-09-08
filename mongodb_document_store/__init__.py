"""
MongoDB Document Store for ERP Assistant System

A comprehensive document storage system built on MongoDB for storing and querying
customer reviews, product information, support tickets, marketing campaigns,
and knowledge base articles.

This package provides:
- Async MongoDB connection management
- Comprehensive data models for various document types
- Synthetic data generation for testing and development
- Advanced query interface with natural language support
- Integration-ready design for MCP server architecture

Main Components:
- connection: MongoDB connection and database management
- models: Data models for all document types
- generator: Synthetic data generation
- query_interface: Advanced querying capabilities
- setup_database: Database initialization and population

Usage:
    from mongodb_document_store import mongodb_manager, mongo_query
    
    # Connect to database
    await mongodb_manager.connect()
    
    # Query products
    products = await mongo_query.search_products(query="smartphone")
    
    # Get review analytics
    analytics = await mongo_query.get_review_analytics(product_id=1)
"""

__version__ = "1.0.0"
__author__ = "Master Thesis Project"
__description__ = "MongoDB Document Store for Multi-Agent Data Fusion"

# Import main components for easy access
from .connection import mongodb_manager
from .query_interface import mongo_query
from .generator import document_generator
from .config import config

# Import models for type hints and direct usage
from .models import (
    ProductDocument,
    CustomerReview,
    SupportTicket,
    MarketingCampaign,
    KnowledgeBaseArticle,
    UserInteraction,
    SentimentType,
    TicketStatus,
    TicketPriority,
    CampaignStatus
)

__all__ = [
    # Main components
    "mongodb_manager",
    "mongo_query", 
    "document_generator",
    "config",
    
    # Data models
    "ProductDocument",
    "CustomerReview",
    "SupportTicket",
    "MarketingCampaign",
    "KnowledgeBaseArticle",
    "UserInteraction",
    
    # Enums
    "SentimentType",
    "TicketStatus",
    "TicketPriority",
    "CampaignStatus",
    
    # Package info
    "__version__",
    "__author__",
    "__description__"
]