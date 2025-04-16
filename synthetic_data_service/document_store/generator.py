"""
Generator for synthetic document data.
"""

import json
import logging
import os
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from faker import Faker

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DocumentGenerator:
    """Generator for synthetic document data."""

    def __init__(self, seed: Optional[int] = None):
        """Initialize the document generator.
        
        Args:
            seed: Random seed for reproducibility
        """
        self.seed = seed if seed is not None else random.randint(1, 10000)
        self.faker = Faker()
        self.faker.seed_instance(self.seed)
        random.seed(self.seed)
        
        # Define document collections
        self.collections = [
            "product_details",
            "customer_feedback",
            "marketing_campaigns",
            "support_tickets",
            "knowledge_base"
        ]
        
    def generate_product_details(self, num_products: int, product_ids: List[int]) -> List[Dict[str, Any]]:
        """Generate detailed product documents.
        
        Args:
            num_products: Number of product documents to generate
            product_ids: List of product IDs from the relational database
            
        Returns:
            List of product detail documents
        """
        logger.info(f"Generating {num_products} product detail documents...")
        
        documents = []
        
        # Ensure we don't try to generate more documents than we have product IDs
        num_products = min(num_products, len(product_ids))
        
        # Select random product IDs if we're generating fewer documents than available IDs
        selected_product_ids = random.sample(product_ids, num_products)
        
        for product_id in selected_product_ids:
            # Generate a detailed product document
            document = {
                "product_id": product_id,
                "detailed_description": self.faker.paragraph(nb_sentences=5),
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
                    "materials": [self.faker.word() for _ in range(random.randint(1, 5))],
                    "colors": [self.faker.color_name() for _ in range(random.randint(1, 4))]
                },
                "features": [self.faker.sentence() for _ in range(random.randint(3, 8))],
                "benefits": [self.faker.sentence() for _ in range(random.randint(2, 5))],
                "usage_instructions": self.faker.paragraph(nb_sentences=3),
                "warranty_info": {
                    "duration": random.choice([1, 2, 3, 5, 10]),
                    "coverage": self.faker.paragraph(nb_sentences=2),
                    "limitations": self.faker.paragraph(nb_sentences=1)
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
                    "created_at": self.faker.date_time_between(start_date="-2y", end_date="now").isoformat(),
                    "updated_at": self.faker.date_time_between(start_date="-6m", end_date="now").isoformat(),
                    "created_by": self.faker.email(),
                    "version": f"{random.randint(1, 5)}.{random.randint(0, 9)}"
                }
            }
            
            documents.append(document)
            
        logger.info(f"Generated {len(documents)} product detail documents.")
        return documents
    
    def generate_customer_feedback(self, num_feedback: int, customer_ids: List[int], 
                                  product_ids: List[int]) -> List[Dict[str, Any]]:
        """Generate customer feedback documents.
        
        Args:
            num_feedback: Number of feedback documents to generate
            customer_ids: List of customer IDs from the relational database
            product_ids: List of product IDs from the relational database
            
        Returns:
            List of customer feedback documents
        """
        logger.info(f"Generating {num_feedback} customer feedback documents...")
        
        documents = []
        
        for _ in range(num_feedback):
            # Generate a customer feedback document
            sentiment = random.choice(["positive", "neutral", "negative"])
            rating = random.randint(1, 5) if sentiment == "negative" else \
                     random.randint(3, 4) if sentiment == "neutral" else \
                     random.randint(4, 5)
            
            # Generate feedback date within the last year
            feedback_date = self.faker.date_time_between(start_date="-1y", end_date="now")
            
            document = {
                "feedback_id": self.faker.uuid4(),
                "customer_id": random.choice(customer_ids),
                "product_id": random.choice(product_ids),
                "rating": rating,
                "sentiment": sentiment,
                "title": self.faker.sentence(),
                "content": self.faker.paragraph(nb_sentences=random.randint(2, 8)),
                "feedback_date": feedback_date.isoformat(),
                "purchase_verified": random.choice([True, False, True, True]),  # Bias toward verified
                "helpful_votes": random.randint(0, 100),
                "media": {
                    "images": [f"feedback_image_{i}.jpg" for i in range(random.randint(0, 3))]
                },
                "tags": random.sample(
                    ["quality", "price", "delivery", "service", "durability", "design", "functionality", "ease of use"],
                    random.randint(0, 4)
                ),
                "response": {
                    "has_response": random.choice([True, False]),
                    "response_date": (feedback_date + timedelta(days=random.randint(1, 14))).isoformat() 
                    if random.random() < 0.7 else None,
                    "response_content": self.faker.paragraph(nb_sentences=2) if random.random() < 0.7 else None,
                    "responder": self.faker.name() if random.random() < 0.7 else None
                }
            }
            
            documents.append(document)
            
        logger.info(f"Generated {len(documents)} customer feedback documents.")
        return documents
    
    def generate_marketing_campaigns(self, num_campaigns: int, product_ids: List[int]) -> List[Dict[str, Any]]:
        """Generate marketing campaign documents.
        
        Args:
            num_campaigns: Number of campaign documents to generate
            product_ids: List of product IDs from the relational database
            
        Returns:
            List of marketing campaign documents
        """
        logger.info(f"Generating {num_campaigns} marketing campaign documents...")
        
        documents = []
        campaign_types = ["email", "social_media", "print", "television", "radio", "event", "influencer"]
        channels = ["email", "facebook", "instagram", "twitter", "linkedin", "youtube", "tiktok", "newspaper", "magazine", "tv", "radio"]
        
        for i in range(num_campaigns):
            # Generate campaign start and end dates
            start_date = self.faker.date_time_between(start_date="-2y", end_date="+6m")
            end_date = start_date + timedelta(days=random.randint(7, 90))
            
            # Select target products
            target_products = random.sample(
                product_ids,
                min(random.randint(1, 10), len(product_ids))
            )
            
            # Generate campaign budget
            budget = round(random.uniform(1000, 100000), 2)
            
            # Generate campaign performance metrics if the campaign has ended
            performance = None
            if end_date < datetime.now():
                performance = {
                    "impressions": random.randint(1000, 1000000),
                    "clicks": random.randint(100, 50000),
                    "conversions": random.randint(10, 5000),
                    "revenue": round(random.uniform(budget * 0.5, budget * 10), 2),
                    "roi": round(random.uniform(-0.5, 5.0), 2),
                    "ctr": round(random.uniform(0.001, 0.1), 4),
                    "conversion_rate": round(random.uniform(0.01, 0.2), 4)
                }
            
            campaign_type = random.choice(campaign_types)
            selected_channels = random.sample(
                channels,
                random.randint(1, 5)
            )
            
            document = {
                "campaign_id": f"CAMP-{i+1:04d}",
                "name": f"{self.faker.company()} {self.faker.word().capitalize()} Campaign",
                "description": self.faker.paragraph(nb_sentences=3),
                "type": campaign_type,
                "channels": selected_channels,
                "target_audience": {
                    "demographics": {
                        "age_range": random.choice(["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]),
                        "gender": random.choice(["all", "male", "female"]),
                        "locations": [self.faker.country() for _ in range(random.randint(1, 5))],
                        "income_level": random.choice(["low", "medium", "high", "all"])
                    },
                    "interests": [self.faker.word() for _ in range(random.randint(2, 6))],
                    "behaviors": [self.faker.word() for _ in range(random.randint(1, 4))]
                },
                "budget": budget,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "status": "completed" if end_date < datetime.now() else 
                          "active" if start_date < datetime.now() else "scheduled",
                "target_products": target_products,
                "creative_assets": {
                    "images": [f"campaign_{i+1}_image_{j}.jpg" for j in range(1, random.randint(2, 6))],
                    "videos": [f"campaign_{i+1}_video_{j}.mp4" for j in range(1, random.randint(1, 3))],
                    "copy": [self.faker.paragraph(nb_sentences=1) for _ in range(random.randint(3, 8))]
                },
                "performance": performance,
                "metadata": {
                    "created_by": self.faker.name(),
                    "created_at": (start_date - timedelta(days=random.randint(7, 30))).isoformat(),
                    "updated_at": self.faker.date_time_between(
                        start_date=start_date - timedelta(days=7),
                        end_date="now"
                    ).isoformat(),
                    "version": f"{random.randint(1, 3)}.{random.randint(0, 9)}"
                }
            }
            
            documents.append(document)
            
        logger.info(f"Generated {len(documents)} marketing campaign documents.")
        return documents
    
    def generate_support_tickets(self, num_tickets: int, customer_ids: List[int], 
                                product_ids: List[int]) -> List[Dict[str, Any]]:
        """Generate support ticket documents.
        
        Args:
            num_tickets: Number of ticket documents to generate
            customer_ids: List of customer IDs from the relational database
            product_ids: List of product IDs from the relational database
            
        Returns:
            List of support ticket documents
        """
        logger.info(f"Generating {num_tickets} support ticket documents...")
        
        documents = []
        ticket_types = ["technical_issue", "billing_inquiry", "product_question", "return_request", "complaint"]
        priorities = ["low", "medium", "high", "critical"]
        statuses = ["open", "in_progress", "waiting_on_customer", "waiting_on_third_party", "resolved", "closed"]
        
        for i in range(num_tickets):
            # Generate ticket creation date
            created_date = self.faker.date_time_between(start_date="-1y", end_date="now")
            
            # Determine ticket status and resolution
            status = random.choice(statuses)
            resolution = None
            resolved_date = None
            satisfaction_rating = None
            
            if status in ["resolved", "closed"]:
                resolution = {
                    "resolution_type": random.choice(["fixed", "workaround", "not_reproducible", "by_design", "no_fix_required"]),
                    "resolution_note": self.faker.paragraph(nb_sentences=2)
                }
                resolved_date = (created_date + timedelta(days=random.randint(1, 30))).isoformat()
                satisfaction_rating = random.randint(1, 5) if random.random() < 0.7 else None
            
            # Generate conversation history
            num_messages = random.randint(2, 10)
            conversation = []
            
            current_date = created_date
            for j in range(num_messages):
                is_customer = j == 0 or random.random() < 0.4
                current_date = current_date + timedelta(hours=random.randint(1, 24))
                
                if status in ["resolved", "closed"] and current_date > datetime.fromisoformat(resolved_date):
                    break
                
                message = {
                    "timestamp": current_date.isoformat(),
                    "sender": "customer" if is_customer else "agent",
                    "sender_name": self.faker.name(),
                    "content": self.faker.paragraph(nb_sentences=random.randint(1, 3)),
                    "attachments": [f"ticket_{i+1}_attachment_{j+1}.{random.choice(['pdf', 'jpg', 'png'])}" 
                                   for _ in range(random.randint(0, 2))] if random.random() < 0.3 else []
                }
                conversation.append(message)
            
            document = {
                "ticket_id": f"TICK-{i+1:05d}",
                "customer_id": random.choice(customer_ids),
                "product_id": random.choice(product_ids) if random.random() < 0.8 else None,
                "subject": self.faker.sentence(),
                "description": self.faker.paragraph(nb_sentences=random.randint(2, 5)),
                "type": random.choice(ticket_types),
                "priority": random.choice(priorities),
                "status": status,
                "created_date": created_date.isoformat(),
                "updated_date": (created_date + timedelta(days=random.randint(0, 30))).isoformat(),
                "resolved_date": resolved_date,
                "resolution": resolution,
                "satisfaction_rating": satisfaction_rating,
                "tags": random.sample(
                    ["hardware", "software", "network", "account", "billing", "shipping", "returns", "warranty"],
                    random.randint(0, 3)
                ),
                "conversation": conversation,
                "metadata": {
                    "source": random.choice(["email", "phone", "web", "chat", "social_media"]),
                    "browser": random.choice(["Chrome", "Firefox", "Safari", "Edge", None]),
                    "os": random.choice(["Windows", "MacOS", "Linux", "iOS", "Android", None]),
                    "ip_address": self.faker.ipv4() if random.random() < 0.7 else None
                }
            }
            
            documents.append(document)
            
        logger.info(f"Generated {len(documents)} support ticket documents.")
        return documents
    
    def generate_knowledge_base(self, num_articles: int, product_ids: List[int]) -> List[Dict[str, Any]]:
        """Generate knowledge base article documents.
        
        Args:
            num_articles: Number of knowledge base articles to generate
            product_ids: List of product IDs from the relational database
            
        Returns:
            List of knowledge base article documents
        """
        logger.info(f"Generating {num_articles} knowledge base articles...")
        
        documents = []
        article_types = ["how_to", "troubleshooting", "faq", "reference", "best_practice"]
        
        for i in range(num_articles):
            # Generate article creation and update dates
            created_date = self.faker.date_time_between(start_date="-2y", end_date="-3m")
            updated_date = self.faker.date_time_between(start_date=created_date, end_date="now")
            
            # Determine if article is related to specific products
            related_products = []
            if random.random() < 0.7:
                related_products = random.sample(
                    product_ids,
                    min(random.randint(1, 3), len(product_ids))
                )
            
            # Generate article sections
            num_sections = random.randint(2, 6)
            sections = []
            
            for j in range(num_sections):
                section = {
                    "title": self.faker.sentence(),
                    "content": self.faker.paragraph(nb_sentences=random.randint(3, 8)),
                    "images": [f"kb_{i+1}_section_{j+1}_image_{k}.jpg" 
                              for k in range(1, random.randint(1, 3))] if random.random() < 0.4 else []
                }
                sections.append(section)
            
            document = {
                "article_id": f"KB-{i+1:04d}",
                "title": self.faker.sentence(),
                "summary": self.faker.paragraph(nb_sentences=1),
                "type": random.choice(article_types),
                "sections": sections,
                "related_products": related_products,
                "tags": random.sample(
                    ["installation", "configuration", "troubleshooting", "maintenance", "upgrade", 
                     "security", "performance", "integration", "backup", "recovery"],
                    random.randint(2, 5)
                ),
                "author": {
                    "name": self.faker.name(),
                    "email": self.faker.email(),
                    "department": random.choice(["Support", "Product", "Engineering", "Documentation"])
                },
                "metadata": {
                    "created_date": created_date.isoformat(),
                    "updated_date": updated_date.isoformat(),
                    "version": f"{random.randint(1, 5)}.{random.randint(0, 9)}",
                    "view_count": random.randint(0, 10000),
                    "helpful_rating": round(random.uniform(0, 1), 2),
                    "published": True
                },
                "related_articles": [f"KB-{random.randint(1, num_articles):04d}" 
                                    for _ in range(random.randint(0, 3))]
            }
            
            documents.append(document)
            
        logger.info(f"Generated {len(documents)} knowledge base articles.")
        return documents
    
    def generate_all_documents(self, num_products: int, num_feedback: int, num_campaigns: int,
                              num_tickets: int, num_articles: int, product_ids: List[int],
                              customer_ids: List[int], output_dir: str) -> Dict[str, int]:
        """Generate all document collections and save to JSON files.
        
        Args:
            num_products: Number of product detail documents to generate
            num_feedback: Number of customer feedback documents to generate
            num_campaigns: Number of marketing campaign documents to generate
            num_tickets: Number of support ticket documents to generate
            num_articles: Number of knowledge base articles to generate
            product_ids: List of product IDs from the relational database
            customer_ids: List of customer IDs from the relational database
            output_dir: Directory to save the generated JSON files
            
        Returns:
            Dictionary with collection names and document counts
        """
        logger.info(f"Generating document collections with seed {self.seed}...")
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate and save each collection
        collections = {}
        
        # Product details
        product_details = self.generate_product_details(num_products, product_ids)
        with open(os.path.join(output_dir, "product_details.json"), "w") as f:
            json.dump(product_details, f, indent=2)
        collections["product_details"] = len(product_details)
        
        # Customer feedback
        customer_feedback = self.generate_customer_feedback(num_feedback, customer_ids, product_ids)
        with open(os.path.join(output_dir, "customer_feedback.json"), "w") as f:
            json.dump(customer_feedback, f, indent=2)
        collections["customer_feedback"] = len(customer_feedback)
        
        # Marketing campaigns
        marketing_campaigns = self.generate_marketing_campaigns(num_campaigns, product_ids)
        with open(os.path.join(output_dir, "marketing_campaigns.json"), "w") as f:
            json.dump(marketing_campaigns, f, indent=2)
        collections["marketing_campaigns"] = len(marketing_campaigns)
        
        # Support tickets
        support_tickets = self.generate_support_tickets(num_tickets, customer_ids, product_ids)
        with open(os.path.join(output_dir, "support_tickets.json"), "w") as f:
            json.dump(support_tickets, f, indent=2)
        collections["support_tickets"] = len(support_tickets)
        
        # Knowledge base
        knowledge_base = self.generate_knowledge_base(num_articles, product_ids)
        with open(os.path.join(output_dir, "knowledge_base.json"), "w") as f:
            json.dump(knowledge_base, f, indent=2)
        collections["knowledge_base"] = len(knowledge_base)
        
        logger.info(f"Generated {sum(collections.values())} documents across {len(collections)} collections.")
        
        # Save collection summary
        with open(os.path.join(output_dir, "collections_summary.json"), "w") as f:
            json.dump({
                "total_documents": sum(collections.values()),
                "collections": collections,
                "generation_date": datetime.now().isoformat(),
                "seed": self.seed
            }, f, indent=2)
        
        return collections