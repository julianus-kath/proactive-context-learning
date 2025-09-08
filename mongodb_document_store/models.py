"""
Data models for MongoDB documents.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum

class SentimentType(str, Enum):
    """Sentiment types for reviews and feedback."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"

class TicketStatus(str, Enum):
    """Support ticket status types."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_CUSTOMER = "waiting_on_customer"
    WAITING_THIRD_PARTY = "waiting_on_third_party"
    RESOLVED = "resolved"
    CLOSED = "closed"

class TicketPriority(str, Enum):
    """Support ticket priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class CampaignStatus(str, Enum):
    """Marketing campaign status types."""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

@dataclass
class ProductDocument:
    """Enhanced product document with detailed information."""
    product_id: int
    name: str
    description: str
    detailed_description: str
    category: str
    subcategory: str
    brand: str
    model: str
    sku: str
    
    # Specifications
    specifications: Dict[str, Any]
    features: List[str]
    benefits: List[str]
    
    # Pricing and availability
    price: float
    cost: float
    currency: str
    availability: Dict[str, Any]
    
    # Media and assets
    images: List[str]
    videos: List[str]
    documents: List[str]
    
    # SEO and marketing
    seo_keywords: List[str]
    marketing_tags: List[str]
    
    # Relationships
    related_products: List[int]
    compatible_products: List[int]
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    created_by: str
    version: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data

@dataclass
class CustomerReview:
    """Customer review document."""
    review_id: str
    product_id: int
    customer_id: int
    
    # Review content
    title: str
    content: str
    rating: int  # 1-5 stars
    sentiment: SentimentType
    
    # Review metadata
    review_date: datetime
    purchase_verified: bool
    purchase_date: Optional[datetime]
    
    # Engagement metrics
    helpful_votes: int
    total_votes: int
    
    # Media attachments
    images: List[str]
    videos: List[str]
    
    # Categorization
    tags: List[str]
    aspects: Dict[str, int]  # Aspect-based ratings (quality, price, service, etc.)
    
    # Response from company
    company_response: Optional[Dict[str, Any]]
    
    # Metadata
    source: str  # website, app, email, etc.
    device_type: str
    location: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage."""
        data = asdict(self)
        data['review_date'] = self.review_date.isoformat()
        if self.purchase_date:
            data['purchase_date'] = self.purchase_date.isoformat()
        data['sentiment'] = self.sentiment.value
        return data

@dataclass
class SupportTicket:
    """Support ticket document."""
    ticket_id: str
    customer_id: int
    product_id: Optional[int]
    
    # Ticket details
    subject: str
    description: str
    category: str
    subcategory: str
    
    # Status and priority
    status: TicketStatus
    priority: TicketPriority
    
    # Dates
    created_date: datetime
    updated_date: datetime
    resolved_date: Optional[datetime]
    closed_date: Optional[datetime]
    
    # Assignment
    assigned_to: Optional[str]
    department: str
    
    # Resolution
    resolution: Optional[Dict[str, Any]]
    satisfaction_rating: Optional[int]
    satisfaction_feedback: Optional[str]
    
    # Communication history
    messages: List[Dict[str, Any]]
    
    # Attachments
    attachments: List[str]
    
    # Tags and categorization
    tags: List[str]
    
    # SLA tracking
    sla_breach: bool
    response_time_hours: Optional[float]
    resolution_time_hours: Optional[float]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage."""
        data = asdict(self)
        data['created_date'] = self.created_date.isoformat()
        data['updated_date'] = self.updated_date.isoformat()
        if self.resolved_date:
            data['resolved_date'] = self.resolved_date.isoformat()
        if self.closed_date:
            data['closed_date'] = self.closed_date.isoformat()
        data['status'] = self.status.value
        data['priority'] = self.priority.value
        return data

@dataclass
class MarketingCampaign:
    """Marketing campaign document."""
    campaign_id: str
    name: str
    description: str
    
    # Campaign details
    type: str  # email, social_media, print, etc.
    channels: List[str]
    
    # Targeting
    target_audience: Dict[str, Any]
    target_products: List[int]
    target_segments: List[str]
    
    # Budget and timeline
    budget: float
    currency: str
    start_date: datetime
    end_date: datetime
    
    # Status
    status: CampaignStatus
    
    # Creative assets
    creative_assets: Dict[str, List[str]]
    
    # Performance metrics
    performance: Optional[Dict[str, Any]]
    
    # A/B testing
    ab_test_variants: Optional[List[Dict[str, Any]]]
    
    # Metadata
    created_by: str
    created_at: datetime
    updated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage."""
        data = asdict(self)
        data['start_date'] = self.start_date.isoformat()
        data['end_date'] = self.end_date.isoformat()
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        data['status'] = self.status.value
        return data

@dataclass
class KnowledgeBaseArticle:
    """Knowledge base article document."""
    article_id: str
    title: str
    content: str
    summary: str
    
    # Categorization
    category: str
    subcategory: str
    tags: List[str]
    
    # Content metadata
    content_type: str  # faq, tutorial, troubleshooting, etc.
    difficulty_level: str  # beginner, intermediate, advanced
    estimated_read_time: int  # in minutes
    
    # Related information
    related_products: List[int]
    related_articles: List[str]
    
    # Engagement metrics
    views: int
    helpful_votes: int
    unhelpful_votes: int
    
    # Content management
    author: str
    reviewer: Optional[str]
    published_date: datetime
    last_updated: datetime
    version: str
    
    # SEO
    seo_keywords: List[str]
    meta_description: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage."""
        data = asdict(self)
        data['published_date'] = self.published_date.isoformat()
        data['last_updated'] = self.last_updated.isoformat()
        return data

@dataclass
class UserInteraction:
    """User interaction tracking document."""
    interaction_id: str
    user_id: Optional[int]  # Can be None for anonymous users
    session_id: str
    
    # Interaction details
    interaction_type: str  # search, view, click, purchase, etc.
    page_url: str
    referrer: Optional[str]
    
    # Product interactions
    product_id: Optional[int]
    search_query: Optional[str]
    search_results: Optional[List[int]]
    
    # Timing
    timestamp: datetime
    duration_seconds: Optional[float]
    
    # Device and location
    device_type: str
    browser: str
    os: str
    location: Optional[Dict[str, str]]
    
    # Additional context
    context: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data