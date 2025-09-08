"""
Setup and populate MongoDB document store with synthetic data.
"""

import asyncio
import argparse
import logging
import sys
from typing import List, Dict, Any

from connection import mongodb_manager
from generator import document_generator
from config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def get_relational_data_ids() -> Dict[str, List[int]]:
    """
    Get product and customer IDs from the existing relational database.
    This would typically connect to your PostgreSQL database.
    For now, we'll generate some sample IDs.
    """
    # TODO: Replace with actual database connection to get real IDs
    # from your existing synthetic_data_service
    
    logger.info("Getting relational database IDs...")
    
    # Sample data - replace with actual database queries
    product_ids = list(range(1, 101))  # 100 products
    customer_ids = list(range(1, 201))  # 200 customers
    
    logger.info(f"Found {len(product_ids)} products and {len(customer_ids)} customers")
    
    return {
        "product_ids": product_ids,
        "customer_ids": customer_ids
    }

async def setup_database():
    """Initialize MongoDB database and create indexes."""
    logger.info("Setting up MongoDB database...")
    
    # Connect to MongoDB
    if not await mongodb_manager.connect():
        logger.error("Failed to connect to MongoDB")
        return False
    
    # Create indexes
    await mongodb_manager.create_indexes()
    
    logger.info("✅ Database setup complete")
    return True

async def populate_database(
    num_products: int = 100,
    num_reviews: int = 500,
    num_tickets: int = 200,
    num_campaigns: int = 50,
    num_kb_articles: int = 100,
    clear_existing: bool = False
):
    """Populate the database with synthetic data."""
    
    logger.info("Starting database population...")
    
    # Get existing relational data IDs
    relational_ids = await get_relational_data_ids()
    product_ids = relational_ids["product_ids"]
    customer_ids = relational_ids["customer_ids"]
    
    # Clear existing data if requested
    if clear_existing:
        logger.info("Clearing existing data...")
        for collection_name in config.COLLECTIONS.values():
            collection = mongodb_manager.get_collection(collection_name)
            await collection.delete_many({})
        logger.info("✅ Cleared existing data")
    
    # Generate and insert product documents
    logger.info("Generating product documents...")
    products = await document_generator.generate_product_documents(num_products, product_ids)
    await document_generator.insert_documents_batch(config.COLLECTIONS["products"], products)
    
    # Generate and insert customer reviews
    logger.info("Generating customer reviews...")
    reviews = await document_generator.generate_customer_reviews(num_reviews, product_ids, customer_ids)
    await document_generator.insert_documents_batch(config.COLLECTIONS["reviews"], reviews)
    
    # Generate and insert support tickets
    logger.info("Generating support tickets...")
    tickets = await document_generator.generate_support_tickets(num_tickets, customer_ids, product_ids)
    await document_generator.insert_documents_batch(config.COLLECTIONS["support_tickets"], tickets)
    
    # Generate marketing campaigns
    logger.info("Generating marketing campaigns...")
    campaigns = await generate_marketing_campaigns(num_campaigns, product_ids)
    await document_generator.insert_documents_batch(config.COLLECTIONS["marketing_campaigns"], campaigns)
    
    # Generate knowledge base articles
    logger.info("Generating knowledge base articles...")
    kb_articles = await generate_knowledge_base_articles(num_kb_articles, product_ids)
    await document_generator.insert_documents_batch(config.COLLECTIONS["knowledge_base"], kb_articles)
    
    logger.info("✅ Database population complete")

async def generate_marketing_campaigns(num_campaigns: int, product_ids: List[int]) -> List[Dict[str, Any]]:
    """Generate marketing campaign documents."""
    from datetime import datetime, timedelta
    from models import MarketingCampaign, CampaignStatus
    import random
    import uuid
    
    documents = []
    campaign_types = ["email", "social_media", "print", "television", "radio", "event", "influencer"]
    channels = ["email", "facebook", "instagram", "twitter", "linkedin", "youtube", "tiktok"]
    
    for i in range(num_campaigns):
        start_date = document_generator.faker.date_time_between(start_date="-1y", end_date="+3m")
        end_date = start_date + timedelta(days=random.randint(7, 90))
        
        # Determine status based on dates
        now = datetime.now()
        if end_date < now:
            status = CampaignStatus.COMPLETED
        elif start_date <= now <= end_date:
            status = CampaignStatus.ACTIVE
        else:
            status = CampaignStatus.SCHEDULED
        
        # Generate performance metrics for completed campaigns
        performance = None
        if status == CampaignStatus.COMPLETED:
            budget = random.uniform(5000, 100000)
            performance = {
                "impressions": random.randint(10000, 1000000),
                "clicks": random.randint(500, 50000),
                "conversions": random.randint(50, 5000),
                "revenue": round(random.uniform(budget * 0.5, budget * 8), 2),
                "cost_per_click": round(random.uniform(0.5, 5.0), 2),
                "conversion_rate": round(random.uniform(0.01, 0.15), 4),
                "return_on_ad_spend": round(random.uniform(1.5, 8.0), 2)
            }
        else:
            budget = random.uniform(5000, 100000)
        
        campaign = MarketingCampaign(
            campaign_id=f"CAMP-{i+1:04d}",
            name=f"{document_generator.faker.company()} {document_generator.faker.word().capitalize()} Campaign",
            description=document_generator.faker.paragraph(nb_sentences=3),
            type=random.choice(campaign_types),
            channels=random.sample(channels, random.randint(1, 4)),
            target_audience={
                "demographics": {
                    "age_range": random.choice(["18-24", "25-34", "35-44", "45-54", "55+"]),
                    "gender": random.choice(["all", "male", "female"]),
                    "locations": [document_generator.faker.country() for _ in range(random.randint(1, 3))],
                    "income_level": random.choice(["low", "medium", "high", "all"])
                },
                "interests": [document_generator.faker.word() for _ in range(random.randint(2, 5))],
                "behaviors": [document_generator.faker.word() for _ in range(random.randint(1, 3))]
            },
            target_products=random.sample(product_ids, min(random.randint(1, 10), len(product_ids))),
            target_segments=random.sample(["new_customers", "returning_customers", "vip_customers", "at_risk"], 
                                        random.randint(1, 3)),
            budget=round(budget, 2),
            currency="USD",
            start_date=start_date,
            end_date=end_date,
            status=status,
            creative_assets={
                "images": [f"campaign_{i+1}_image_{j}.jpg" for j in range(1, random.randint(2, 6))],
                "videos": [f"campaign_{i+1}_video_{j}.mp4" for j in range(1, random.randint(1, 3))],
                "copy_variants": [document_generator.faker.sentence() for _ in range(random.randint(3, 6))]
            },
            performance=performance,
            ab_test_variants=[
                {
                    "variant_id": f"A_{i}",
                    "name": "Control",
                    "traffic_split": 0.5,
                    "performance": {
                        "clicks": random.randint(100, 1000),
                        "conversions": random.randint(10, 100)
                    } if performance else None
                },
                {
                    "variant_id": f"B_{i}",
                    "name": "Test",
                    "traffic_split": 0.5,
                    "performance": {
                        "clicks": random.randint(100, 1000),
                        "conversions": random.randint(10, 100)
                    } if performance else None
                }
            ] if random.random() < 0.3 else None,
            created_by=document_generator.faker.name(),
            created_at=start_date - timedelta(days=random.randint(7, 30)),
            updated_at=document_generator.faker.date_time_between(start_date=start_date, end_date="now")
        )
        
        documents.append(campaign.to_dict())
    
    return documents

async def generate_knowledge_base_articles(num_articles: int, product_ids: List[int]) -> List[Dict[str, Any]]:
    """Generate knowledge base articles."""
    from datetime import datetime, timedelta
    from models import KnowledgeBaseArticle
    import random
    import uuid
    
    documents = []
    categories = ["FAQ", "Troubleshooting", "How-to", "Product Guide", "Installation", "Maintenance"]
    content_types = ["faq", "tutorial", "troubleshooting", "guide", "reference"]
    difficulty_levels = ["beginner", "intermediate", "advanced"]
    
    for i in range(num_articles):
        category = random.choice(categories)
        content_type = random.choice(content_types)
        difficulty = random.choice(difficulty_levels)
        
        # Generate realistic content based on category
        if category == "FAQ":
            title = f"Frequently Asked Questions: {document_generator.faker.sentence()}"
            content = f"Q: {document_generator.faker.sentence()}?\nA: {document_generator.faker.paragraph()}\n\n" * random.randint(3, 8)
        elif category == "Troubleshooting":
            title = f"How to Fix: {document_generator.faker.sentence()}"
            content = f"Problem: {document_generator.faker.sentence()}\n\nSolution:\n{document_generator.faker.paragraph(nb_sentences=5)}"
        else:
            title = f"{category}: {document_generator.faker.sentence()}"
            content = document_generator.faker.paragraph(nb_sentences=random.randint(8, 15))
        
        published_date = document_generator.faker.date_time_between(start_date="-2y", end_date="-1m")
        last_updated = document_generator.faker.date_time_between(start_date=published_date, end_date="now")
        
        article = KnowledgeBaseArticle(
            article_id=f"KB-{i+1:06d}",
            title=title,
            content=content,
            summary=document_generator.faker.paragraph(nb_sentences=2),
            category=category,
            subcategory=random.choice([f"{category} - Basic", f"{category} - Advanced"]),
            tags=random.sample(["popular", "updated", "featured", "technical", "beginner-friendly"], 
                             random.randint(1, 3)),
            content_type=content_type,
            difficulty_level=difficulty,
            estimated_read_time=random.randint(2, 15),
            related_products=random.sample(product_ids, min(random.randint(0, 5), len(product_ids))),
            related_articles=[f"KB-{j:06d}" for j in random.sample(range(1, num_articles+1), 
                                                                  min(random.randint(0, 3), num_articles-1))],
            views=random.randint(10, 5000),
            helpful_votes=random.randint(0, 100),
            unhelpful_votes=random.randint(0, 20),
            author=document_generator.faker.name(),
            reviewer=document_generator.faker.name() if random.random() < 0.7 else None,
            published_date=published_date,
            last_updated=last_updated,
            version=f"{random.randint(1, 5)}.{random.randint(0, 9)}",
            seo_keywords=[document_generator.faker.word() for _ in range(random.randint(5, 10))],
            meta_description=document_generator.faker.sentence()
        )
        
        documents.append(article.to_dict())
    
    return documents

async def get_database_status():
    """Get current database status and statistics."""
    logger.info("Getting database status...")
    
    if not await mongodb_manager.connect():
        logger.error("Failed to connect to MongoDB")
        return
    
    # Get health check
    health = await mongodb_manager.health_check()
    print("\n" + "="*50)
    print("MONGODB DATABASE STATUS")
    print("="*50)
    print(f"Status: {health['status']}")
    print(f"Database: {health['database']}")
    
    if 'stats' in health:
        stats = health['stats']
        if 'database' in stats:
            db_stats = stats['database']
            print(f"Collections: {db_stats.get('collections', 0)}")
            print(f"Total Objects: {db_stats.get('objects', 0)}")
            print(f"Data Size: {db_stats.get('dataSize', 0):,} bytes")
        
        if 'collections' in stats:
            print("\nCollection Details:")
            for collection_type, collection_info in stats['collections'].items():
                print(f"  {collection_type}: {collection_info['count']} documents")
    
    print("="*50)
    
    await mongodb_manager.disconnect()

async def main():
    """Main function to handle command line arguments and execute operations."""
    parser = argparse.ArgumentParser(description="MongoDB Document Store Setup")
    parser.add_argument("--setup", action="store_true", help="Setup database and create indexes")
    parser.add_argument("--populate", action="store_true", help="Populate database with synthetic data")
    parser.add_argument("--status", action="store_true", help="Show database status")
    parser.add_argument("--clear", action="store_true", help="Clear existing data before populating")
    
    # Data generation parameters
    parser.add_argument("--products", type=int, default=100, help="Number of products to generate")
    parser.add_argument("--reviews", type=int, default=500, help="Number of reviews to generate")
    parser.add_argument("--tickets", type=int, default=200, help="Number of support tickets to generate")
    parser.add_argument("--campaigns", type=int, default=50, help="Number of marketing campaigns to generate")
    parser.add_argument("--articles", type=int, default=100, help="Number of knowledge base articles to generate")
    
    args = parser.parse_args()
    
    try:
        if args.status:
            await get_database_status()
        
        if args.setup:
            await setup_database()
        
        if args.populate:
            if not await mongodb_manager.connect():
                logger.error("Failed to connect to MongoDB")
                sys.exit(1)
            
            await populate_database(
                num_products=args.products,
                num_reviews=args.reviews,
                num_tickets=args.tickets,
                num_campaigns=args.campaigns,
                num_kb_articles=args.articles,
                clear_existing=args.clear
            )
            
            await mongodb_manager.disconnect()
        
        if not any([args.setup, args.populate, args.status]):
            # Default: setup and populate
            await setup_database()
            await populate_database(clear_existing=True)
            await get_database_status()
            await mongodb_manager.disconnect()
    
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        await mongodb_manager.disconnect()
    except Exception as e:
        logger.error(f"Error: {e}")
        await mongodb_manager.disconnect()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())