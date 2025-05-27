#!/usr/bin/env python
"""
Script to generate simple MongoDB data and save it to a JSON file.
This only needs to be run once to create the data file.
"""
import json
import logging
import os
import random
import sys
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Sample product and customer IDs
SAMPLE_PRODUCT_IDS = [f"PROD-{i:04d}" for i in range(1, 101)]
SAMPLE_CUSTOMER_IDS = [f"CUST-{i:04d}" for i in range(1, 51)]

def generate_product_details(num_products=50, seed=42):
    """Generate product details."""
    random.seed(seed)
    
    documents = []
    selected_product_ids = random.sample(SAMPLE_PRODUCT_IDS, min(num_products, len(SAMPLE_PRODUCT_IDS)))
    
    for product_id in selected_product_ids:
        document = {
            "product_id": product_id,
            "detailed_description": f"Detailed description for product {product_id}",
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
                [pid for pid in SAMPLE_PRODUCT_IDS if pid != product_id],
                min(random.randint(0, 5), len(SAMPLE_PRODUCT_IDS) - 1)
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

def generate_customer_feedback(num_feedback=100, seed=43):
    """Generate customer feedback."""
    random.seed(seed)
    
    documents = []
    
    for i in range(num_feedback):
        sentiment = random.choice(["positive", "neutral", "negative"])
        rating = random.randint(1, 5) if sentiment == "negative" else \
                 random.randint(3, 4) if sentiment == "neutral" else \
                 random.randint(4, 5)
        
        feedback_date = datetime.now() - timedelta(days=random.randint(0, 365))
        
        document = {
            "feedback_id": f"FEED-{i:04d}",
            "customer_id": random.choice(SAMPLE_CUSTOMER_IDS),
            "product_id": random.choice(SAMPLE_PRODUCT_IDS),
            "rating": rating,
            "sentiment": sentiment,
            "title": f"Feedback title {i}",
            "content": f"Feedback content {i} with {'positive' if rating > 3 else 'negative'} sentiment.",
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
                "response_content": f"Response to feedback {i}" if random.random() < 0.7 else None,
                "responder": f"Support Agent {random.randint(1, 10)}" if random.random() < 0.7 else None
            }
        }
        documents.append(document)
    
    return documents

def generate_support_tickets(num_tickets=100, seed=44):
    """Generate support tickets."""
    random.seed(seed)
    
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
                "resolution_note": f"Resolution note for ticket {i}"
            }
            resolved_date = (created_date + timedelta(days=random.randint(1, 30))).isoformat()
            satisfaction_rating = random.randint(1, 5)
        
        document = {
            "ticket_id": f"TCKT-{i:04d}",
            "customer_id": random.choice(SAMPLE_CUSTOMER_IDS),
            "product_id": random.choice(SAMPLE_PRODUCT_IDS),
            "subject": f"Ticket subject {i}",
            "description": f"Ticket description {i}",
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
                    "author": f"Agent {random.randint(1, 10)}",
                    "content": f"Note {j} for ticket {i}",
                    "internal": random.choice([True, False])
                }
                for j in range(random.randint(0, 5))
            ]
        }
        documents.append(document)
    
    return documents

def generate_knowledge_base(num_articles=30, seed=45):
    """Generate knowledge base articles."""
    random.seed(seed)
    
    documents = []
    categories = ["troubleshooting", "how-to", "faq", "product-info", "policy"]
    
    for i in range(num_articles):
        created_date = datetime.now() - timedelta(days=random.randint(0, 730))
        updated_date = created_date + timedelta(days=random.randint(0, 365))
        
        # Select random products this article applies to
        applicable_products = random.sample(
            SAMPLE_PRODUCT_IDS,
            random.randint(1, 10)
        )
        
        document = {
            "article_id": f"KB-{i:04d}",
            "title": f"Knowledge Base Article {i}",
            "category": random.choice(categories),
            "content": f"Content for knowledge base article {i}. This is a detailed explanation.",
            "applicable_products": applicable_products,
            "tags": random.sample(
                ["setup", "installation", "troubleshooting", "maintenance", "repair", "warranty", "returns", "usage"],
                random.randint(1, 4)
            ),
            "created_at": created_date.isoformat(),
            "updated_at": updated_date.isoformat(),
            "author": f"Author {random.randint(1, 10)}",
            "view_count": random.randint(0, 10000),
            "helpful_rating": round(random.uniform(1, 5), 1),
            "related_articles": [f"KB-{random.randint(1, num_articles):04d}" for _ in range(random.randint(0, 3))]
        }
        documents.append(document)
    
    return documents

def main():
    """Generate MongoDB data and save it to a JSON file."""
    output_file = "mongodb_data.json"
    if len(sys.argv) > 1:
        output_file = sys.argv[1]
    
    logger.info(f"Generating MongoDB data to {output_file}...")
    
    # Generate data for each collection
    collections_data = {
        "product_details": generate_product_details(),
        "customer_feedback": generate_customer_feedback(),
        "support_tickets": generate_support_tickets(),
        "knowledge_base": generate_knowledge_base()
    }
    
    # Save the data to a JSON file
    with open(output_file, 'w') as f:
        json.dump(collections_data, f, indent=2)
    
    logger.info(f"MongoDB data saved to {output_file}")
    logger.info(f"Generated {len(collections_data)} collections with a total of {sum(len(docs) for docs in collections_data.values())} documents")

if __name__ == "__main__":
    main()