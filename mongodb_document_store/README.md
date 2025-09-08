# MongoDB Document Store

A comprehensive MongoDB-based document storage system for customer reviews, product information, support tickets, marketing campaigns, and knowledge base articles. This system is designed to integrate with the existing MCP (Model Context Protocol) server for multi-agent data fusion.

## Features

### Document Types
- **Product Catalog**: Enhanced product information with specifications, media, and relationships
- **Customer Reviews**: Detailed reviews with sentiment analysis, aspect ratings, and engagement metrics
- **Support Tickets**: Complete ticket lifecycle with messages, SLA tracking, and resolution data
- **Marketing Campaigns**: Campaign performance tracking with A/B testing and audience targeting
- **Knowledge Base**: Searchable articles with categorization and engagement metrics
- **User Interactions**: Tracking user behavior and interactions (future enhancement)

### Key Capabilities
- **Async MongoDB Operations**: Built with Motor for high-performance async operations
- **Comprehensive Data Generation**: Realistic synthetic data with proper relationships
- **Advanced Querying**: Natural language query interface with aggregation pipelines
- **Schema Analysis**: Automatic schema inference and documentation
- **Performance Optimized**: Proper indexing and batch operations
- **MCP Integration Ready**: Designed to integrate with existing MCP server architecture

## Installation

### Prerequisites
- Python 3.8+
- MongoDB 4.4+ (local installation or MongoDB Atlas)

### Setup

1. **Install Dependencies**
   ```bash
   cd mongodb_document_store
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your MongoDB connection details
   ```

3. **Start MongoDB** (if running locally)
   ```bash
   # macOS with Homebrew
   brew services start mongodb-community
   
   # Linux
   sudo systemctl start mongod
   
   # Windows
   net start MongoDB
   ```

## Usage

### Quick Start
Set up the database and populate with synthetic data:
```bash
python setup_database.py
```

### Advanced Usage

#### Setup Database Only
```bash
python setup_database.py --setup
```

#### Populate with Custom Data Amounts
```bash
python setup_database.py --populate --products 200 --reviews 1000 --tickets 300
```

#### Clear and Repopulate
```bash
python setup_database.py --populate --clear
```

#### Check Database Status
```bash
python setup_database.py --status
```

### Command Line Options
- `--setup`: Initialize database and create indexes
- `--populate`: Generate and insert synthetic data
- `--status`: Display database statistics
- `--clear`: Clear existing data before populating
- `--products N`: Number of products to generate (default: 100)
- `--reviews N`: Number of reviews to generate (default: 500)
- `--tickets N`: Number of support tickets to generate (default: 200)
- `--campaigns N`: Number of marketing campaigns to generate (default: 50)
- `--articles N`: Number of knowledge base articles to generate (default: 100)

## Data Models

### Product Document
```json
{
  "product_id": 1,
  "name": "TechCorp Smart Smartphone",
  "description": "Advanced smartphone with cutting-edge features",
  "detailed_description": "Comprehensive product description...",
  "category": "Electronics",
  "subcategory": "Smartphones",
  "brand": "TechCorp",
  "specifications": {
    "display": {"size": "6.1 inches", "resolution": "1080x2400"},
    "processor": "Snapdragon 888",
    "memory": {"ram": "8GB", "storage": "256GB"}
  },
  "price": 799.99,
  "availability": {"in_stock": true, "stock_quantity": 150},
  "images": ["product_1_image_1.jpg", "product_1_image_2.jpg"],
  "seo_keywords": ["smartphone", "android", "camera"],
  "related_products": [2, 3, 4]
}
```

### Customer Review
```json
{
  "review_id": "uuid-string",
  "product_id": 1,
  "customer_id": 123,
  "title": "Excellent product, highly recommend!",
  "content": "This smartphone exceeded my expectations...",
  "rating": 5,
  "sentiment": "positive",
  "review_date": "2024-01-15T10:30:00",
  "purchase_verified": true,
  "helpful_votes": 15,
  "aspects": {
    "quality": 5,
    "price": 4,
    "delivery": 5
  },
  "company_response": {
    "response_date": "2024-01-16T14:20:00",
    "responder_name": "Customer Service Team",
    "response_content": "Thank you for your feedback!"
  }
}
```

### Support Ticket
```json
{
  "ticket_id": "TICKET-000001",
  "customer_id": 123,
  "product_id": 1,
  "subject": "Technical Issue: App crashes on startup",
  "description": "The mobile app crashes immediately when I try to open it...",
  "category": "Technical Issue",
  "status": "resolved",
  "priority": "high",
  "created_date": "2024-01-10T09:15:00",
  "resolved_date": "2024-01-12T16:30:00",
  "resolution": {
    "resolution_type": "fixed",
    "resolution_note": "Issue resolved with app update v2.1.3"
  },
  "satisfaction_rating": 4,
  "messages": [
    {
      "timestamp": "2024-01-10T09:15:00",
      "sender_type": "customer",
      "content": "I'm experiencing crashes..."
    }
  ]
}
```

## Query Interface

The system provides a comprehensive query interface for accessing document data:

### Product Queries
```python
from query_interface import mongo_query

# Search products
products = await mongo_query.search_products(
    query="smartphone",
    category="Electronics",
    price_min=500,
    price_max=1000,
    in_stock=True
)

# Get product reviews
reviews = await mongo_query.get_product_reviews(
    product_id=1,
    sentiment="positive",
    min_rating=4
)

# Get review analytics
analytics = await mongo_query.get_review_analytics(product_id=1)
```

### Support Ticket Queries
```python
# Search support tickets
tickets = await mongo_query.search_support_tickets(
    customer_id=123,
    status="open",
    priority="high"
)

# Get ticket analytics
ticket_stats = await mongo_query.get_ticket_analytics()
```

### Knowledge Base Queries
```python
# Search knowledge base
articles = await mongo_query.search_knowledge_base(
    query="installation guide",
    category="How-to"
)
```

## Database Schema

### Collections
- `product_catalog`: Enhanced product information
- `customer_reviews`: Customer feedback and ratings
- `support_tickets`: Customer support interactions
- `marketing_campaigns`: Marketing campaign data and performance
- `knowledge_base`: Help articles and documentation
- `user_interactions`: User behavior tracking (future)

### Indexes
The system automatically creates optimized indexes for:
- Product searches (name, category, price)
- Review queries (product_id, customer_id, rating, sentiment)
- Ticket searches (status, priority, customer_id)
- Text searches (full-text indexes on relevant fields)

## Integration with MCP Server

This MongoDB document store is designed to integrate seamlessly with the existing MCP server architecture:

### Integration Points
1. **Query Interface**: The `MongoQueryInterface` class provides methods that can be exposed as MCP tools
2. **Async Operations**: All operations are async-compatible with the existing MCP server
3. **Error Handling**: Consistent error handling that matches MCP patterns
4. **Data Relationships**: Product and customer IDs align with the existing relational database

### Next Steps for MCP Integration
1. Create MCP tools that wrap the query interface methods
2. Add MongoDB query capabilities to the existing MCP server
3. Update the LangGraph workflow to handle document queries
4. Implement hybrid queries that combine relational and document data

## Performance Considerations

### Optimization Features
- **Batch Operations**: All data insertion uses batch processing
- **Proper Indexing**: Comprehensive indexes for common query patterns
- **Connection Pooling**: Efficient connection management
- **Aggregation Pipelines**: Complex analytics using MongoDB's aggregation framework

### Monitoring
- Database statistics and health checks
- Query performance tracking
- Collection size monitoring

## Development and Testing

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest tests/
```

### Development Setup
```bash
# Install development dependencies
pip install -e .

# Run with development settings
export LOG_LEVEL=DEBUG
python setup_database.py --status
```

## Configuration

### Environment Variables
- `MONGODB_URL`: MongoDB connection string
- `MONGODB_DATABASE`: Database name
- `DEFAULT_SEED`: Seed for reproducible data generation
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

### MongoDB Atlas Setup
For cloud deployment, update your `.env` file:
```
MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/
MONGODB_DATABASE=erp_document_store
```

## Troubleshooting

### Common Issues

1. **Connection Failed**
   - Ensure MongoDB is running
   - Check connection string in `.env`
   - Verify network connectivity

2. **Index Creation Failed**
   - Check MongoDB version (4.4+ required)
   - Ensure sufficient permissions
   - Check disk space

3. **Data Generation Slow**
   - Reduce batch size in config
   - Check system resources
   - Consider using MongoDB Atlas for better performance

### Logging
Enable debug logging for detailed information:
```bash
export LOG_LEVEL=DEBUG
python setup_database.py --status
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is part of the Master Thesis multi-agent data fusion system.