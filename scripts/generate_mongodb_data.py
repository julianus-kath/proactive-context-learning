#!/usr/bin/env python
"""
Script to generate MongoDB data and save it to a JSON file.
This only needs to be run once to create the data file.
"""
import asyncio
import json
import logging
import os
import sys
import random
from typing import Dict, List, Any
from datetime import datetime, timedelta

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from synthetic_data_service.document_store.generator import DocumentGenerator
    USE_GENERATOR = True
except ImportError:
    USE_GENERATOR = False
    print("Warning: synthetic_data_service module not found. Using simplified data generation.")
    
    # Import faker if available, otherwise use random
    try:
        from faker import Faker
        FAKER_AVAILABLE = True
    except ImportError:
        FAKER_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Sample product and customer IDs (since we're not connecting to the ERP API)
SAMPLE_PRODUCT_IDS = [f"PROD-{i:04d}" for i in range(1, 101)]
SAMPLE_CUSTOMER_IDS = [f"CUST-{i:04d}" for i in range(1, 51)]

def generate_simple_product_details(num_products: int, product_ids: List[str], seed: int = 42) -> List[Dict[str, Any]]:
    """Generate simple product details without using the DocumentGenerator."""
    random.seed(seed)
    faker = Faker() if FAKER_AVAILABLE else None
    if faker:
        faker.seed_instance(seed)
    
    documents = []
    selected_product_ids = random.sample(product_ids, min(num_products, len(product_ids)))
    
    for product_id in selected_product_ids:
        document = {
            "product_id": product_id,
            "detailed_description": faker.paragraph(nb_sentences=5) if faker else f"Detailed description for product {product_id}",
            "specifications": {
                "dimensions": {
                    "length": round(random.uniform(1, 100), 2),
                    "width": round(random.uniform(1, 100), 2),
                    "height": round(random.uniform(1, 100), 2),
                    "unit": random.choice(["cm", "mm", "inches"])
                },
                "weight": {
                    "value": round(random.uniform(0.1, 50), 2),
                    "unit": random.choice(["kg", "g", "lbs"])
                },
                "materials": [f"Material {i}" for i in range(1, random.randint(2, 6))],
                "colors": [f"Color {i}" for i in range(1, random.randint(2, 5))]
            },
            "features": [f"Feature {i}" for i in range(1, random.randint(4, 9))],
            "benefits": [f"Benefit {i}" for i in range(1, random.randint(3, 6))],
            "usage_instructions": f"Usage instructions for product {product_id}",
            "warranty_info": {
                "duration": random.choice([1, 2, 3, 5, 10]),
                "coverage": f"Warranty coverage for product {product_id}",
                "limitations": f"Warranty limitations for product {product_id}"
            },
            "media": {
                "images": [f"product_{product_id}_image_{i}.jpg" for i in range(1, random.randint(3, 8))],
                "videos": [f"product_{product_id}_video_{i}.mp4" for i in range(1, random.randint(1, 3))],
                "documents": [f"product_{product_id}_doc_{i}.pdf" for i in range(1, random.randint(1, 3))]
            },
            "related_products": random.sample(
                [pid for pid in product_ids if pid != product_id],
                min(random.randint(0, 5), len(product_ids) - 1)
            ),
            "metadata": {
                "created_at": (datetime.now() - timedelta(days=random.randint(0, 730))).isoformat(),
                "updated_at": (datetime.now() - timedelta(days=random.randint(0, 180))).isoformat(),
                "created_by": f"user{random.randint(1, 100)}@example.com",
                "version": f"{random.randint(1, 5)}.{random.randint(0, 9)}"
            }
        }
        documents.append(document)
    
    return documents

def generate_simple_customer_feedback(num_feedback: int, customer_ids: List[str], product_ids: List[str], seed: int = 42) -> List[Dict[str, Any]]:
    """Generate simple customer feedback without using the DocumentGenerator."""
    random.seed(seed)
    faker = Faker() if FAKER_AVAILABLE else None
    if faker:
        faker.seed_instance(seed)
    
    documents = []
    
    for i in range(num_feedback):
        sentiment = random.choice(["positive", "neutral", "negative"])
        rating = random.randint(1, 5) if sentiment == "negative" else \
                 random.randint(3, 4) if sentiment == "neutral" else \
                 random.randint(4, 5)
        
        feedback_date = datetime.now() - timedelta(days=random.randint(0, 365))
        
        document = {
            "feedback_id": f"FEED-{i:04d}",
            "customer_id": random.choice(customer_ids),
            "product_id": random.choice(product_ids),
            "rating": rating,
            "sentiment": sentiment,
            "title": faker.sentence() if faker else f"Feedback title {i}",
            "content": faker.paragraph(nb_sentences=random.randint(2, 8)) if faker else f"Feedback content {i}",
            "feedback_date": feedback_date.isoformat(),
            "purchase_verified": random.choice([True, False, True, True]),
            "helpful_votes": random.randint(0, 100),
            "media": {
                "images": [f"feedback_image_{j}.jpg" for j in range(random.randint(0, 3))]
            },
            "tags": random.sample(
                ["quality", "price", "delivery", "service", "durability", "design", "functionality", "ease of use"],
                random.randint(0, 4)
            ),
            "response": {
                "has_response": random.choice([True, False]),
                "response_date": (feedback_date + timedelta(days=random.randint(1, 14))).isoformat() 
                if random.random() < 0.7 else None,
                "response_content": faker.paragraph(nb_sentences=2) if faker and random.random() < 0.7 else 
                                   f"Response to feedback {i}" if random.random() < 0.7 else None,
                "responder": faker.name() if faker and random.random() < 0.7 else 
                            f"Support Agent {random.randint(1, 10)}" if random.random() < 0.7 else None
            }
        }
        documents.append(document)
    
    return documents

def generate_simple_support_tickets(num_tickets: int, customer_ids: List[str], product_ids: List[str], seed: int = 42) -> List[Dict[str, Any]]:
    """Generate simple support tickets without using the DocumentGenerator."""
    random.seed(seed)
    faker = Faker() if FAKER_AVAILABLE else None
    if faker:
        faker.seed_instance(seed)
    
    documents = []
    ticket_types = ["technical_issue", "billing_inquiry", "product_question", "return_request", "complaint"]
    priorities = ["low", "medium", "high", "critical"]
    statuses = ["open", "in_progress", "waiting_on_customer", "waiting_on_third_party", "resolved", "closed"]
    
    for i in range(num_tickets):
        created_date = datetime.now() - timedelta(days=random.randint(0, 365))
        
        status = random.choice(statuses)
        resolution = None
        resolved_date = None
        satisfaction_rating = None
        
        if status in ["resolved", "closed"]:
            resolution = {
                "resolution_type": random.choice(["fixed", "workaround", "not_reproducible", "by_design", "no_fix_required"]),
                "resolution_note": faker.paragraph(nb_sentences=2) if faker else f"Resolution note for ticket {i}"
            }
            resolved_date = (created_date + timedelta(days=random.randint(1, 30))).isoformat()
            satisfaction_rating = random.randint(1, 5)
        
        document = {
            "ticket_id": f"TCKT-{i:04d}",
            "customer_id": random.choice(customer_ids),
            "product_id": random.choice(product_ids),
            "subject": faker.sentence() if faker else f"Ticket subject {i}",
            "description": faker.paragraph(nb_sentences=3) if faker else f"Ticket description {i}",
            "type": random.choice(ticket_types),
            "priority": random.choice(priorities),
            "status": status,
            "created_at": created_date.isoformat(),
            "updated_at": (created_date + timedelta(days=random.randint(0, 30))).isoformat(),
            "resolution": resolution,
            "resolved_at": resolved_date,
            "satisfaction_rating": satisfaction_rating,
            "attachments": [f"ticket_{i}_attachment_{j}.pdf" for j in range(random.randint(0, 2))],
            "tags": random.sample(
                ["hardware", "software", "billing", "shipping", "returns", "warranty", "damage", "missing_parts"],
                random.randint(0, 3)
            ),
            "notes": [
                {
                    "timestamp": (created_date + timedelta(days=j, hours=random.randint(1, 8))).isoformat(),
                    "author": faker.name() if faker else f"Agent {random.randint(1, 10)}",
                    "content": faker.paragraph(nb_sentences=1) if faker else f"Note {j} for ticket {i}",
                    "internal": random.choice([True, False])
                }
                for j in range(random.randint(0, 5))
            ]
        }
        documents.append(document)
    
    return documents

async def generate_mongodb_data(output_file: str, seed: int = 42):
    """
    Generate MongoDB data and save it to a JSON file.
    
    Args:
        output_file: Path to the output JSON file
        seed: Random seed for reproducibility
    """
    logger.info(f"Generating MongoDB data with seed {seed}...")
    
    # Generate data for each collection
    collections_data = {}
    
    if USE_GENERATOR:
        # Initialize the document generator
        generator = DocumentGenerator(seed=seed)
        
        # Product details
        product_details = generator.generate_product_details(
            num_products=50,
            product_ids=SAMPLE_PRODUCT_IDS
        )
        collections_data["product_details"] = product_details
        
        # Customer feedback
        customer_feedback = generator.generate_customer_feedback(
            num_feedback=100,
            customer_ids=SAMPLE_CUSTOMER_IDS,
            product_ids=SAMPLE_PRODUCT_IDS
        )
        collections_data["customer_feedback"] = customer_feedback
        
        # Marketing campaigns
        marketing_campaigns = generator.generate_marketing_campaigns(
            num_campaigns=20,
            product_ids=SAMPLE_PRODUCT_IDS
        )
        collections_data["marketing_campaigns"] = marketing_campaigns
        
        # Support tickets
        support_tickets = generator.generate_support_tickets(
            num_tickets=100,
            customer_ids=SAMPLE_CUSTOMER_IDS,
            product_ids=SAMPLE_PRODUCT_IDS
        )
        collections_data["support_tickets"] = support_tickets
        
        # Knowledge base articles
        knowledge_base = generator.generate_knowledge_base_articles(
            num_articles=30,
            product_ids=SAMPLE_PRODUCT_IDS
        )
        collections_data["knowledge_base"] = knowledge_base
    else:
        # Use simplified data generation
        logger.info("Using simplified data generation...")
        
        # Product details
        product_details = generate_simple_product_details(
            num_products=50,
            product_ids=SAMPLE_PRODUCT_IDS,
            seed=seed
        )
        collections_data["product_details"] = product_details
        
        # Customer feedback
        customer_feedback = generate_simple_customer_feedback(
            num_feedback=100,
            customer_ids=SAMPLE_CUSTOMER_IDS,
            product_ids=SAMPLE_PRODUCT_IDS,
            seed=seed + 1
        )
        collections_data["customer_feedback"] = customer_feedback
        
        # Support tickets
        support_tickets = generate_simple_support_tickets(
            num_tickets=100,
            customer_ids=SAMPLE_CUSTOMER_IDS,
            product_ids=SAMPLE_PRODUCT_IDS,
            seed=seed + 2
        )
        collections_data["support_tickets"] = support_tickets
    
    # Save the data to a JSON file
    with open(output_file, 'w') as f:
        json.dump(collections_data, f, indent=2)
    
    logger.info(f"MongoDB data saved to {output_file}")
    logger.info(f"Generated {len(collections_data)} collections with a total of {sum(len(docs) for docs in collections_data.values())} documents")

if __name__ == "__main__":
    output_file = "mongodb_data.json"
    if len(sys.argv) > 1:
        output_file = sys.argv[1]
    
    asyncio.run(generate_mongodb_data(output_file))