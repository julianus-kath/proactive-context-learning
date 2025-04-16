# Extended Synthetic Data: Document Store and Graph Database

This document describes the extended synthetic data components that complement the relational database. These components simulate different types of business data scenarios and provide a more comprehensive synthetic data environment for data fusion experiments.

## Overview

The extended data consists of two main components:

1. **Document Store**: JSON documents organized into collections that represent unstructured or semi-structured business data
2. **Graph Database**: Node and edge data representing relationships between business entities

These components are designed to be used alongside the relational database, providing a multi-model data environment that more closely resembles real-world business systems.

## Document Store

The document store contains the following collections:

### Product Details Collection

Detailed product information that goes beyond the structured data in the relational database:

- Comprehensive product descriptions
- Technical specifications (dimensions, weight, materials)
- Features and benefits
- Warranty information
- Media assets (images, videos, documents)
- Related products

**Business Scenario**: Product information management system or product catalog that stores rich, unstructured product details that don't fit well in a relational model.

### Customer Feedback Collection

Customer reviews and feedback about products:

- Ratings and sentiment
- Detailed feedback content
- Helpful votes
- Media attachments
- Response from company

**Business Scenario**: Customer review system that captures qualitative feedback about products, which is typically stored separately from transactional data.

### Marketing Campaigns Collection

Information about marketing initiatives:

- Campaign details and descriptions
- Target audience demographics
- Budget and timeline
- Creative assets
- Performance metrics
- Channel information

**Business Scenario**: Marketing automation system that tracks campaign details and performance metrics, which often have varying structures based on campaign type.

### Support Tickets Collection

Customer support interactions:

- Ticket details and status
- Conversation history
- Resolution information
- Customer satisfaction ratings
- Attachments

**Business Scenario**: Customer support system that tracks issues, conversations, and resolutions, which typically involve unstructured text and varying metadata.

### Knowledge Base Collection

Internal knowledge articles:

- Article content with sections
- Author information
- Tags and categories
- Related products and articles
- Usage metrics

**Business Scenario**: Internal knowledge management system that stores documentation, troubleshooting guides, and best practices for products and services.

## Graph Database

The graph database contains the following networks:

### Employee Network

Represents relationships between employees:

- **Nodes**: Employees
- **Edges**: 
  - MANAGES (manager to subordinate)
  - WORKS_WITH (collaboration between colleagues)
  - COLLABORATES_WITH (cross-department collaboration)
  - MENTORS (mentorship relationship)

**Business Scenario**: Organizational network analysis to understand collaboration patterns, knowledge flow, and informal organizational structure.

### Product Network

Represents relationships between products and categories:

- **Nodes**: Products, Categories
- **Edges**:
  - BELONGS_TO (product to category)
  - SIMILAR_TO (product to product, same subcategory)
  - RELATED_TO (product to product, same category)
  - FREQUENTLY_BOUGHT_WITH (product to product, purchase pattern)
  - ACCESSORY_FOR (accessory to main product)

**Business Scenario**: Product recommendation system that leverages relationships between products to suggest related or complementary items.

### Customer-Product Network

Represents interactions between customers and products:

- **Nodes**: Customers, Products
- **Edges**:
  - PURCHASED (customer bought product)
  - VIEWED (customer viewed product)
  - ADDED_TO_CART (customer added product to cart)
  - RATED (customer rated product)

**Business Scenario**: Customer behavior analysis and recommendation system that tracks interactions beyond just purchases.

### Supply Chain Network

Represents the flow of products through the supply chain:

- **Nodes**: Suppliers, Products, Warehouses, Distribution Centers
- **Edges**:
  - SUPPLIES (supplier to product, warehouse to distribution center)
  - STORED_IN (product to warehouse)
  - PARTNERS_WITH, COMPETES_WITH, SUBSIDIARY_OF (supplier to supplier)

**Business Scenario**: Supply chain management and analysis to understand product flow, dependencies, and potential bottlenecks.

## Data Generation

The extended data is generated based on the relational database, ensuring consistency across all data models. The generation process:

1. Reads data from the relational database
2. Uses the relational data as a foundation for creating documents and graph relationships
3. Adds additional synthetic data to simulate real-world complexity
4. Maintains referential integrity with the relational database (e.g., using the same product IDs)

## Usage

To generate the extended data:

```bash
python -m synthetic_data_service.extended_data_generator --db-path synthetic_data.db --output-dir extended_data
```

Parameters:
- `--db-path`: Path to the SQLite database file (default: synthetic_data.db)
- `--output-dir`: Directory to save the generated data (default: extended_data)
- `--seed`: Random seed for reproducibility (default: random)

The generated data is saved as JSON files in the specified output directory:

```
extended_data/
├── documents/
│   ├── product_details.json
│   ├── customer_feedback.json
│   ├── marketing_campaigns.json
│   ├── support_tickets.json
│   ├── knowledge_base.json
│   └── collections_summary.json
├── graphs/
│   ├── employee_network.json
│   ├── product_network.json
│   ├── customer_product_network.json
│   ├── supply_chain_network.json
│   └── graphs_summary.json
└── extended_data_summary.json
```

## Data Fusion Opportunities

The extended data provides numerous opportunities for data fusion experiments:

1. **Customer 360 View**: Combine relational customer data with document-based feedback and graph-based product interactions to create a comprehensive customer profile.

2. **Product Intelligence**: Merge structured product data with detailed document specifications and graph-based relationships to build a complete product knowledge base.

3. **Sales Analysis**: Integrate relational sales data with marketing campaign documents and customer-product interaction graphs to analyze sales performance factors.

4. **Supply Chain Optimization**: Combine relational inventory data with supply chain network graphs to identify optimization opportunities.

5. **Employee Performance Analysis**: Merge relational employee data with organizational network graphs to understand performance in the context of collaboration patterns.

These fusion scenarios represent realistic business use cases where data from multiple sources and models must be combined to derive comprehensive insights.