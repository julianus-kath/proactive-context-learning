"""
Demo script showcasing MongoDB Document Store capabilities.
"""

import asyncio
import json
import logging
from datetime import datetime

from connection import mongodb_manager
from query_interface import mongo_query
from setup_database import setup_database, populate_database

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def demo_product_queries():
    """Demonstrate product querying capabilities."""
    logger.info("\n" + "="*60)
    logger.info("PRODUCT QUERIES DEMO")
    logger.info("="*60)
    
    # Search for electronics
    logger.info("Searching for electronics...")
    products = await mongo_query.search_products(
        category="Electronics",
        limit=3
    )
    
    if products:
        logger.info(f"Found {len(products)} electronics products:")
        for product in products:
            logger.info(f"  - {product['name']} (${product['price']}) - {product['category']}")
    else:
        logger.info("No electronics products found")
    
    # Search by price range
    logger.info("\nSearching for products under $100...")
    affordable_products = await mongo_query.search_products(
        price_max=100,
        limit=5
    )
    
    if affordable_products:
        logger.info(f"Found {len(affordable_products)} affordable products:")
        for product in affordable_products:
            logger.info(f"  - {product['name']}: ${product['price']}")
    else:
        logger.info("No affordable products found")

async def demo_review_analytics():
    """Demonstrate review analytics capabilities."""
    logger.info("\n" + "="*60)
    logger.info("REVIEW ANALYTICS DEMO")
    logger.info("="*60)
    
    # Get overall review analytics
    logger.info("Getting overall review analytics...")
    analytics = await mongo_query.get_review_analytics()
    
    logger.info(f"Total reviews: {analytics['total_reviews']}")
    logger.info(f"Average rating: {analytics['average_rating']}")
    
    if analytics['total_reviews'] > 0:
        sentiment_counts = analytics['sentiment_counts']
        logger.info(f"Sentiment breakdown:")
        logger.info(f"  - Positive: {sentiment_counts['positive']}")
        logger.info(f"  - Neutral: {sentiment_counts['neutral']}")
        logger.info(f"  - Negative: {sentiment_counts['negative']}")
        
        rating_dist = analytics['rating_distribution']
        logger.info(f"Rating distribution:")
        for stars in range(5, 0, -1):
            count = rating_dist[f'{stars}_star']
            logger.info(f"  - {stars} stars: {count}")
    
    # Get reviews for a specific product (if any exist)
    if analytics['total_reviews'] > 0:
        logger.info("\nGetting reviews for first product...")
        reviews = await mongo_query.get_product_reviews(product_id=1, limit=3)
        
        if reviews:
            logger.info(f"Found {len(reviews)} reviews for product 1:")
            for review in reviews:
                logger.info(f"  - {review['rating']}⭐ '{review['title'][:50]}...'")
        else:
            logger.info("No reviews found for product 1")

async def demo_support_tickets():
    """Demonstrate support ticket analytics."""
    logger.info("\n" + "="*60)
    logger.info("SUPPORT TICKETS DEMO")
    logger.info("="*60)
    
    # Get ticket analytics
    logger.info("Getting support ticket analytics...")
    ticket_analytics = await mongo_query.get_ticket_analytics()
    
    if ticket_analytics.get('total_tickets', 0) > 0:
        logger.info(f"Total tickets: {ticket_analytics['total_tickets']}")
        logger.info(f"Average resolution time: {ticket_analytics.get('avg_resolution_time_hours', 0):.1f} hours")
        logger.info(f"SLA breach rate: {ticket_analytics.get('sla_breach_rate', 0):.1f}%")
        
        status_counts = ticket_analytics.get('status_counts', {})
        logger.info("Ticket status breakdown:")
        for status, count in status_counts.items():
            logger.info(f"  - {status.replace('_', ' ').title()}: {count}")
        
        # Search for high priority tickets
        logger.info("\nSearching for high priority tickets...")
        high_priority_tickets = await mongo_query.search_support_tickets(
            priority="high",
            limit=3
        )
        
        if high_priority_tickets:
            logger.info(f"Found {len(high_priority_tickets)} high priority tickets:")
            for ticket in high_priority_tickets:
                logger.info(f"  - {ticket['ticket_id']}: {ticket['subject'][:50]}...")
        else:
            logger.info("No high priority tickets found")
    else:
        logger.info("No support tickets found in database")

async def demo_knowledge_base():
    """Demonstrate knowledge base search."""
    logger.info("\n" + "="*60)
    logger.info("KNOWLEDGE BASE DEMO")
    logger.info("="*60)
    
    # Search knowledge base
    search_terms = ["installation", "troubleshooting", "FAQ"]
    
    for term in search_terms:
        logger.info(f"\nSearching knowledge base for '{term}'...")
        articles = await mongo_query.search_knowledge_base(query=term, limit=2)
        
        if articles:
            logger.info(f"Found {len(articles)} articles:")
            for article in articles:
                logger.info(f"  - {article['title'][:60]}...")
                logger.info(f"    Category: {article['category']}, Views: {article['views']}")
        else:
            logger.info(f"No articles found for '{term}'")

async def demo_database_stats():
    """Show database statistics."""
    logger.info("\n" + "="*60)
    logger.info("DATABASE STATISTICS")
    logger.info("="*60)
    
    stats = await mongodb_manager.get_database_stats()
    
    if 'database' in stats:
        db_stats = stats['database']
        logger.info(f"Database: {db_stats['name']}")
        logger.info(f"Collections: {db_stats.get('collections', 0)}")
        logger.info(f"Total objects: {db_stats.get('objects', 0):,}")
        logger.info(f"Data size: {db_stats.get('dataSize', 0):,} bytes")
    
    if 'collections' in stats:
        logger.info("\nCollection details:")
        for collection_type, collection_info in stats['collections'].items():
            logger.info(f"  - {collection_type}: {collection_info['count']} documents")

async def run_demo():
    """Run the complete demo."""
    logger.info("🚀 Starting MongoDB Document Store Demo")
    logger.info("="*80)
    
    # Connect to database
    logger.info("Connecting to MongoDB...")
    if not await mongodb_manager.connect():
        logger.error("❌ Failed to connect to MongoDB. Please ensure MongoDB is running.")
        return False
    
    logger.info("✅ Connected to MongoDB")
    
    # Check if database has data
    stats = await mongodb_manager.get_database_stats()
    total_objects = stats.get('database', {}).get('objects', 0)
    
    if total_objects == 0:
        logger.info("\n📝 Database is empty. Generating sample data...")
        logger.info("This may take a few minutes...")
        
        # Setup and populate with small dataset for demo
        await setup_database()
        await populate_database(
            num_products=20,
            num_reviews=50,
            num_tickets=30,
            num_campaigns=10,
            num_kb_articles=15,
            clear_existing=True
        )
        
        logger.info("✅ Sample data generated")
    else:
        logger.info(f"📊 Database contains {total_objects:,} documents")
    
    # Run demo sections
    try:
        await demo_database_stats()
        await demo_product_queries()
        await demo_review_analytics()
        await demo_support_tickets()
        await demo_knowledge_base()
        
        logger.info("\n" + "="*80)
        logger.info("🎉 Demo completed successfully!")
        logger.info("="*80)
        
        logger.info("\nNext steps:")
        logger.info("1. Explore the query_interface.py for more query options")
        logger.info("2. Check setup_database.py for data generation options")
        logger.info("3. Integrate with your MCP server using the query interface")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")
        return False
    
    finally:
        await mongodb_manager.disconnect()

if __name__ == "__main__":
    try:
        success = asyncio.run(run_demo())
        if not success:
            exit(1)
    except KeyboardInterrupt:
        logger.info("\n👋 Demo cancelled by user")
    except Exception as e:
        logger.error(f"❌ Demo crashed: {e}")
        exit(1)