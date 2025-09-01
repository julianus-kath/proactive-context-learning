"""
Comprehensive data generator for MongoDB document store.
"""

import asyncio
import json
import logging
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from faker import Faker
from tqdm import tqdm

from models import (
    ProductDocument, CustomerReview, SupportTicket, MarketingCampaign,
    KnowledgeBaseArticle, UserInteraction, SentimentType, TicketStatus,
    TicketPriority, CampaignStatus
)
from connection import mongodb_manager
from config import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MongoDocumentGenerator:
    """Generates comprehensive synthetic documents for MongoDB."""
    
    def __init__(self, seed: Optional[int] = None):
        """Initialize the generator with optional seed for reproducibility."""
        self.seed = seed or config.DEFAULT_SEED
        self.faker = Faker()
        self.faker.seed_instance(self.seed)
        random.seed(self.seed)
        
        # Product categories and subcategories
        self.categories = {
            "Electronics": ["Smartphones", "Laptops", "Tablets", "Headphones", "Cameras", "Smart Watches"],
            "Home & Garden": ["Furniture", "Kitchen Appliances", "Garden Tools", "Home Decor", "Lighting"],
            "Clothing": ["Men's Clothing", "Women's Clothing", "Shoes", "Accessories", "Sportswear"],
            "Books": ["Fiction", "Non-Fiction", "Educational", "Children's Books", "Comics"],
            "Sports": ["Fitness Equipment", "Outdoor Gear", "Team Sports", "Water Sports", "Winter Sports"],
            "Health & Beauty": ["Skincare", "Makeup", "Health Supplements", "Personal Care", "Fragrances"]
        }
        
        # Brands for different categories
        self.brands = {
            "Electronics": ["TechCorp", "InnovateTech", "DigitalPro", "SmartDevices", "FutureTech"],
            "Home & Garden": ["HomeComfort", "GardenMaster", "LivingSpace", "CozyHome", "GreenThumb"],
            "Clothing": ["StyleMax", "FashionForward", "TrendSetter", "ClassicWear", "UrbanStyle"],
            "Books": ["BookWorld", "ReadMore", "KnowledgePress", "StoryTime", "LearnFast"],
            "Sports": ["ActiveLife", "SportsPro", "FitnessMaster", "OutdoorAdventure", "GameChanger"],
            "Health & Beauty": ["BeautyPlus", "HealthFirst", "GlowUp", "WellnessWorks", "PureCare"]
        }
        
        # Review aspects for aspect-based sentiment analysis
        self.review_aspects = ["quality", "price", "delivery", "customer_service", "design", "functionality", "durability"]
        
        # Support ticket categories
        self.ticket_categories = {
            "Technical Issue": ["Software Bug", "Hardware Problem", "Connectivity Issue", "Performance Issue"],
            "Billing": ["Payment Problem", "Refund Request", "Billing Inquiry", "Subscription Issue"],
            "Product": ["Product Question", "Compatibility", "Usage Help", "Feature Request"],
            "Order": ["Order Status", "Shipping Issue", "Return Request", "Exchange Request"],
            "Account": ["Login Problem", "Account Settings", "Profile Update", "Security Issue"]
        }
        
    async def generate_product_documents(self, num_products: int, existing_product_ids: List[int]) -> List[Dict[str, Any]]:
        """Generate enhanced product documents."""
        logger.info(f"Generating {num_products} product documents...")
        
        documents = []
        
        # Use existing product IDs if available, otherwise generate new ones
        if existing_product_ids and len(existing_product_ids) >= num_products:
            product_ids = random.sample(existing_product_ids, num_products)
        else:
            product_ids = existing_product_ids + list(range(max(existing_product_ids) + 1 if existing_product_ids else 1, 
                                                          max(existing_product_ids) + 1 + num_products - len(existing_product_ids) if existing_product_ids else num_products + 1))
        
        for product_id in tqdm(product_ids, desc="Generating products"):
            category = random.choice(list(self.categories.keys()))
            subcategory = random.choice(self.categories[category])
            brand = random.choice(self.brands[category])
            
            # Generate specifications based on category
            specifications = self._generate_product_specifications(category, subcategory)
            
            # Generate features and benefits
            features = [self.faker.sentence() for _ in range(random.randint(3, 8))]
            benefits = [self.faker.sentence() for _ in range(random.randint(2, 5))]
            
            # Generate pricing
            base_price = random.uniform(10, 2000)
            cost = base_price * random.uniform(0.3, 0.7)
            
            # Generate availability info
            availability = {
                "in_stock": random.choice([True, False, True, True]),  # Bias toward in stock
                "stock_quantity": random.randint(0, 1000) if random.random() > 0.1 else 0,
                "backorder_allowed": random.choice([True, False]),
                "estimated_restock": (datetime.now() + timedelta(days=random.randint(1, 30))).isoformat() if random.random() < 0.3 else None
            }
            
            # Generate media assets
            num_images = random.randint(3, 10)
            images = [f"product_{product_id}_image_{i}.jpg" for i in range(1, num_images + 1)]
            videos = [f"product_{product_id}_video_{i}.mp4" for i in range(1, random.randint(1, 4))]
            documents_list = [f"product_{product_id}_manual.pdf", f"product_{product_id}_warranty.pdf"]
            
            # Generate SEO and marketing data
            seo_keywords = [self.faker.word() for _ in range(random.randint(5, 15))]
            marketing_tags = random.sample(["bestseller", "new", "sale", "premium", "eco-friendly", "limited-edition"], 
                                         random.randint(0, 3))
            
            # Generate related products
            other_products = [pid for pid in product_ids if pid != product_id]
            related_products = random.sample(other_products, min(random.randint(0, 5), len(other_products)))
            compatible_products = random.sample(other_products, min(random.randint(0, 3), len(other_products)))
            
            product = ProductDocument(
                product_id=product_id,
                name=f"{brand} {self.faker.word().capitalize()} {subcategory.rstrip('s')}",
                description=self.faker.paragraph(nb_sentences=2),
                detailed_description=self.faker.paragraph(nb_sentences=5),
                category=category,
                subcategory=subcategory,
                brand=brand,
                model=f"{brand[:3].upper()}-{random.randint(1000, 9999)}",
                sku=f"SKU-{product_id:06d}",
                specifications=specifications,
                features=features,
                benefits=benefits,
                price=round(base_price, 2),
                cost=round(cost, 2),
                currency="USD",
                availability=availability,
                images=images,
                videos=videos,
                documents=documents_list,
                seo_keywords=seo_keywords,
                marketing_tags=marketing_tags,
                related_products=related_products,
                compatible_products=compatible_products,
                created_at=self.faker.date_time_between(start_date="-2y", end_date="-6m"),
                updated_at=self.faker.date_time_between(start_date="-6m", end_date="now"),
                created_by=self.faker.email(),
                version=f"{random.randint(1, 5)}.{random.randint(0, 9)}"
            )
            
            documents.append(product.to_dict())
        
        logger.info(f"Generated {len(documents)} product documents")
        return documents
    
    def _generate_product_specifications(self, category: str, subcategory: str) -> Dict[str, Any]:
        """Generate category-specific product specifications."""
        specs = {}
        
        if category == "Electronics":
            if "Smartphone" in subcategory:
                specs = {
                    "display": {
                        "size": f"{random.uniform(5.0, 7.0):.1f} inches",
                        "resolution": random.choice(["1080x2400", "1440x3200", "1170x2532"]),
                        "type": random.choice(["OLED", "LCD", "AMOLED"])
                    },
                    "processor": f"{random.choice(['Snapdragon', 'A-series', 'Exynos'])} {random.randint(700, 900)}",
                    "memory": {
                        "ram": f"{random.choice([4, 6, 8, 12])}GB",
                        "storage": f"{random.choice([64, 128, 256, 512])}GB"
                    },
                    "camera": {
                        "main": f"{random.randint(12, 108)}MP",
                        "front": f"{random.randint(8, 32)}MP"
                    },
                    "battery": f"{random.randint(3000, 5000)}mAh",
                    "os": random.choice(["Android 13", "iOS 16", "Android 14"])
                }
            elif "Laptop" in subcategory:
                specs = {
                    "processor": f"Intel {random.choice(['i5', 'i7', 'i9'])}-{random.randint(10000, 13000)}",
                    "memory": f"{random.choice([8, 16, 32])}GB DDR4",
                    "storage": f"{random.choice([256, 512, 1000])}GB SSD",
                    "display": f"{random.uniform(13.0, 17.0):.1f} inch {random.choice(['Full HD', '4K', 'QHD'])}",
                    "graphics": random.choice(["Integrated", "NVIDIA GTX 1650", "NVIDIA RTX 3060"]),
                    "os": random.choice(["Windows 11", "macOS", "Linux"])
                }
        elif category == "Home & Garden":
            specs = {
                "dimensions": {
                    "length": f"{random.uniform(10, 200):.1f}cm",
                    "width": f"{random.uniform(10, 150):.1f}cm",
                    "height": f"{random.uniform(5, 100):.1f}cm"
                },
                "weight": f"{random.uniform(0.5, 50):.1f}kg",
                "material": random.choice(["Wood", "Metal", "Plastic", "Glass", "Ceramic"]),
                "color": self.faker.color_name()
            }
        elif category == "Clothing":
            specs = {
                "sizes": random.sample(["XS", "S", "M", "L", "XL", "XXL"], random.randint(3, 6)),
                "material": random.choice(["Cotton", "Polyester", "Wool", "Silk", "Denim", "Leather"]),
                "colors": [self.faker.color_name() for _ in range(random.randint(2, 5))],
                "care_instructions": "Machine wash cold, tumble dry low"
            }
        
        # Add common specifications
        specs.update({
            "warranty": f"{random.choice([1, 2, 3, 5])} year(s)",
            "country_of_origin": self.faker.country(),
            "certifications": random.sample(["CE", "FCC", "RoHS", "Energy Star", "ISO 9001"], random.randint(0, 3))
        })
        
        return specs
    
    async def generate_customer_reviews(self, num_reviews: int, product_ids: List[int], 
                                      customer_ids: List[int]) -> List[Dict[str, Any]]:
        """Generate realistic customer reviews."""
        logger.info(f"Generating {num_reviews} customer reviews...")
        
        documents = []
        
        for _ in tqdm(range(num_reviews), desc="Generating reviews"):
            # Determine sentiment and rating
            sentiment = random.choices(
                [SentimentType.POSITIVE, SentimentType.NEUTRAL, SentimentType.NEGATIVE],
                weights=[0.6, 0.25, 0.15]  # Bias toward positive reviews
            )[0]
            
            if sentiment == SentimentType.POSITIVE:
                rating = random.choices([4, 5], weights=[0.3, 0.7])[0]
            elif sentiment == SentimentType.NEUTRAL:
                rating = random.choices([2, 3, 4], weights=[0.2, 0.6, 0.2])[0]
            else:  # NEGATIVE
                rating = random.choices([1, 2], weights=[0.6, 0.4])[0]
            
            # Generate review dates
            review_date = self.faker.date_time_between(start_date="-1y", end_date="now")
            purchase_date = review_date - timedelta(days=random.randint(1, 90)) if random.random() < 0.8 else None
            
            # Generate aspect-based ratings
            aspects = {}
            for aspect in random.sample(self.review_aspects, random.randint(3, 6)):
                # Aspect ratings tend to correlate with overall rating but have some variance
                aspect_rating = max(1, min(5, rating + random.randint(-1, 1)))
                aspects[aspect] = aspect_rating
            
            # Generate engagement metrics
            helpful_votes = random.randint(0, 50) if random.random() < 0.7 else random.randint(50, 200)
            total_votes = helpful_votes + random.randint(0, helpful_votes // 2)
            
            # Generate company response (30% chance)
            company_response = None
            if random.random() < 0.3:
                response_date = review_date + timedelta(days=random.randint(1, 14))
                company_response = {
                    "response_date": response_date.isoformat(),
                    "responder_name": self.faker.name(),
                    "responder_title": random.choice(["Customer Service Rep", "Product Manager", "Support Specialist"]),
                    "response_content": self.faker.paragraph(nb_sentences=2)
                }
            
            # Generate review content based on sentiment
            title, content = self._generate_review_content(sentiment, rating)
            
            review = CustomerReview(
                review_id=str(uuid.uuid4()),
                product_id=random.choice(product_ids),
                customer_id=random.choice(customer_ids),
                title=title,
                content=content,
                rating=rating,
                sentiment=sentiment,
                review_date=review_date,
                purchase_verified=random.choice([True, False, True, True]),  # Bias toward verified
                purchase_date=purchase_date,
                helpful_votes=helpful_votes,
                total_votes=total_votes,
                images=[f"review_image_{i}.jpg" for i in range(random.randint(0, 3))],
                videos=[f"review_video_{i}.mp4" for i in range(random.randint(0, 1))],
                tags=random.sample(["quality", "price", "fast-delivery", "great-service", "recommend"], 
                                 random.randint(0, 3)),
                aspects=aspects,
                company_response=company_response,
                source=random.choice(["website", "mobile_app", "email"]),
                device_type=random.choice(["desktop", "mobile", "tablet"]),
                location=self.faker.city() if random.random() < 0.6 else None
            )
            
            documents.append(review.to_dict())
        
        logger.info(f"Generated {len(documents)} customer reviews")
        return documents
    
    def _generate_review_content(self, sentiment: SentimentType, rating: int) -> Tuple[str, str]:
        """Generate realistic review title and content based on sentiment."""
        if sentiment == SentimentType.POSITIVE:
            titles = [
                "Excellent product, highly recommend!",
                "Great quality and fast delivery",
                "Perfect for my needs",
                "Outstanding value for money",
                "Exceeded my expectations"
            ]
            contents = [
                "This product has been fantastic. The quality is excellent and it arrived quickly. I would definitely buy again and recommend to others.",
                "Really impressed with this purchase. Great build quality, works exactly as described, and the customer service was helpful.",
                "Perfect product for the price. Good quality materials and it does exactly what I needed. Very satisfied with this purchase."
            ]
        elif sentiment == SentimentType.NEUTRAL:
            titles = [
                "Decent product, does the job",
                "Good but not great",
                "Average quality for the price",
                "It's okay, nothing special",
                "Mixed feelings about this product"
            ]
            contents = [
                "The product is okay. It works as expected but nothing particularly impressive. For the price, it's reasonable.",
                "It's a decent product that does what it's supposed to do. Quality is average and delivery was on time.",
                "Not bad, not great. It serves its purpose but I've seen better quality elsewhere for similar prices."
            ]
        else:  # NEGATIVE
            titles = [
                "Disappointed with this purchase",
                "Poor quality, not worth the money",
                "Had issues from day one",
                "Would not recommend",
                "Waste of money"
            ]
            contents = [
                "Really disappointed with this product. The quality is poor and it didn't work as expected. Would not recommend.",
                "Had problems with this from the start. Poor build quality and customer service wasn't helpful when I tried to resolve the issues.",
                "Not worth the money. Cheap materials and it broke after just a few uses. Looking for a refund."
            ]
        
        title = random.choice(titles)
        content = random.choice(contents)
        
        return title, content
    
    async def generate_support_tickets(self, num_tickets: int, customer_ids: List[int], 
                                     product_ids: List[int]) -> List[Dict[str, Any]]:
        """Generate support ticket documents."""
        logger.info(f"Generating {num_tickets} support tickets...")
        
        documents = []
        
        for i in tqdm(range(num_tickets), desc="Generating tickets"):
            # Select category and subcategory
            category = random.choice(list(self.ticket_categories.keys()))
            subcategory = random.choice(self.ticket_categories[category])
            
            # Generate ticket dates
            created_date = self.faker.date_time_between(start_date="-1y", end_date="now")
            updated_date = created_date + timedelta(hours=random.randint(1, 24 * 30))
            
            # Determine status and resolution
            status = random.choices(
                list(TicketStatus),
                weights=[0.1, 0.2, 0.1, 0.05, 0.3, 0.25]  # Bias toward resolved/closed
            )[0]
            
            resolved_date = None
            closed_date = None
            resolution = None
            satisfaction_rating = None
            satisfaction_feedback = None
            
            if status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
                resolved_date = updated_date + timedelta(hours=random.randint(1, 72))
                if status == TicketStatus.CLOSED:
                    closed_date = resolved_date + timedelta(hours=random.randint(1, 24))
                
                resolution = {
                    "resolution_type": random.choice(["fixed", "workaround", "not_reproducible", "by_design"]),
                    "resolution_note": self.faker.paragraph(nb_sentences=2),
                    "resolved_by": self.faker.name()
                }
                
                # Customer satisfaction (80% provide feedback)
                if random.random() < 0.8:
                    satisfaction_rating = random.choices([1, 2, 3, 4, 5], weights=[0.1, 0.1, 0.2, 0.3, 0.3])[0]
                    if satisfaction_rating <= 3:
                        satisfaction_feedback = "Could have been resolved faster"
                    else:
                        satisfaction_feedback = "Great support, thank you!"
            
            # Generate priority based on category
            if category == "Technical Issue":
                priority = random.choices(list(TicketPriority), weights=[0.2, 0.4, 0.3, 0.1])[0]
            elif category == "Billing":
                priority = random.choices(list(TicketPriority), weights=[0.1, 0.3, 0.5, 0.1])[0]
            else:
                priority = random.choices(list(TicketPriority), weights=[0.4, 0.4, 0.15, 0.05])[0]
            
            # Generate messages (conversation history)
            messages = []
            num_messages = random.randint(1, 8)
            
            for msg_idx in range(num_messages):
                msg_date = created_date + timedelta(hours=msg_idx * random.randint(1, 24))
                is_customer = msg_idx % 2 == 0  # Alternate between customer and support
                
                message = {
                    "message_id": str(uuid.uuid4()),
                    "timestamp": msg_date.isoformat(),
                    "sender_type": "customer" if is_customer else "support",
                    "sender_name": self.faker.name(),
                    "content": self.faker.paragraph(nb_sentences=random.randint(1, 3)),
                    "attachments": [f"attachment_{msg_idx}_{j}.jpg" for j in range(random.randint(0, 2))]
                }
                messages.append(message)
            
            # Calculate SLA metrics
            response_time_hours = random.uniform(0.5, 48) if len(messages) > 1 else None
            resolution_time_hours = (resolved_date - created_date).total_seconds() / 3600 if resolved_date else None
            sla_breach = (response_time_hours and response_time_hours > 24) or (resolution_time_hours and resolution_time_hours > 72)
            
            ticket = SupportTicket(
                ticket_id=f"TICKET-{i+1:06d}",
                customer_id=random.choice(customer_ids),
                product_id=random.choice(product_ids) if random.random() < 0.7 else None,
                subject=f"{subcategory}: {self.faker.sentence()}",
                description=self.faker.paragraph(nb_sentences=3),
                category=category,
                subcategory=subcategory,
                status=status,
                priority=priority,
                created_date=created_date,
                updated_date=updated_date,
                resolved_date=resolved_date,
                closed_date=closed_date,
                assigned_to=self.faker.name() if random.random() < 0.8 else None,
                department=random.choice(["Technical Support", "Customer Service", "Billing", "Product Support"]),
                resolution=resolution,
                satisfaction_rating=satisfaction_rating,
                satisfaction_feedback=satisfaction_feedback,
                messages=messages,
                attachments=[f"ticket_attachment_{j}.pdf" for j in range(random.randint(0, 3))],
                tags=random.sample(["urgent", "escalated", "vip_customer", "product_defect", "billing_issue"], 
                                 random.randint(0, 2)),
                sla_breach=sla_breach,
                response_time_hours=response_time_hours,
                resolution_time_hours=resolution_time_hours
            )
            
            documents.append(ticket.to_dict())
        
        logger.info(f"Generated {len(documents)} support tickets")
        return documents
    
    async def insert_documents_batch(self, collection_name: str, documents: List[Dict[str, Any]]):
        """Insert documents in batches to MongoDB."""
        if not documents:
            return
        
        collection = mongodb_manager.get_collection(collection_name)
        
        # Insert in batches
        batch_size = config.BATCH_SIZE
        for i in tqdm(range(0, len(documents), batch_size), desc=f"Inserting {collection_name}"):
            batch = documents[i:i + batch_size]
            try:
                await collection.insert_many(batch, ordered=False)
            except Exception as e:
                logger.error(f"Error inserting batch to {collection_name}: {e}")
                # Try inserting one by one to identify problematic documents
                for doc in batch:
                    try:
                        await collection.insert_one(doc)
                    except Exception as doc_error:
                        logger.error(f"Error inserting document: {doc_error}")
        
        logger.info(f"✅ Inserted {len(documents)} documents to {collection_name}")

# Global generator instance
document_generator = MongoDocumentGenerator()