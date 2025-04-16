# ADR 0003: Extended Data Models - Document Store and Graph Database

## Status

Accepted

## Context

The synthetic data service currently generates relational data that simulates a business environment with customers, products, sales, and other entities. However, modern business systems often employ multiple data models beyond just relational databases. To create a more realistic environment for data fusion experiments, we need to extend our synthetic data to include document-oriented and graph-based data models.

These additional data models would allow us to:

1. Simulate unstructured and semi-structured data that doesn't fit well in a relational model
2. Represent complex relationships between entities that are cumbersome to model and query in a relational database
3. Create a more comprehensive test environment for data fusion algorithms
4. Better reflect the heterogeneous data landscape of real-world business systems

## Decision

We've decided to extend the synthetic data service to include two additional data models:

### 1. Document Store

We will generate JSON documents organized into collections that represent different types of business data:

- **Product Details**: Rich, detailed product information beyond what's in the relational database
- **Customer Feedback**: Reviews and ratings from customers about products
- **Marketing Campaigns**: Information about marketing initiatives, target audiences, and performance
- **Support Tickets**: Customer support interactions with conversation history
- **Knowledge Base**: Internal knowledge articles and documentation

These document collections will reference entities in the relational database (using the same IDs) to maintain consistency and enable data fusion experiments.

### 2. Graph Database

We will generate graph data representing relationships between business entities:

- **Employee Network**: Organizational relationships including management, collaboration, and mentorship
- **Product Network**: Relationships between products such as similarities, accessories, and purchase patterns
- **Customer-Product Network**: Interactions between customers and products beyond just purchases
- **Supply Chain Network**: Flow of products from suppliers through warehouses to distribution centers

The graph data will use nodes that correspond to entities in the relational database and edges that represent relationships between them.

## Implementation Details

### Document Store Implementation

1. **Data Format**: JSON documents stored in files, one file per collection
2. **Generation Approach**: 
   - Use the Faker library to generate realistic content
   - Reference entities from the relational database to maintain consistency
   - Create varied document structures within collections to simulate real-world complexity
3. **Document Collections**:
   - Each collection focuses on a specific business domain
   - Documents within a collection share a common structure but allow for variation
   - Include a mix of structured fields and unstructured text

### Graph Database Implementation

1. **Data Format**: JSON files containing nodes and edges
2. **Generation Approach**:
   - Create nodes that correspond to entities in the relational database
   - Generate edges based on realistic business relationships
   - Include properties on both nodes and edges to provide context
3. **Graph Networks**:
   - Each network represents a specific domain of business relationships
   - Networks can be used independently or combined for more complex analysis
   - Edge properties provide weights, timestamps, and other contextual information

### Integration with Relational Data

1. **Consistent IDs**: Use the same IDs across all data models to enable joining
2. **Referential Integrity**: Ensure that documents and graph nodes reference valid entities in the relational database
3. **Complementary Data**: Design the extended data to complement rather than duplicate the relational data

## Consequences

### Positive

1. **More Realistic Environment**: The multi-model approach better reflects real-world business systems
2. **Rich Data Fusion Opportunities**: The varied data models create numerous opportunities for data fusion experiments
3. **Flexible Query Patterns**: Different data models enable different types of queries and analyses
4. **Comprehensive Testing**: Data fusion algorithms can be tested against a more diverse set of data sources

### Negative

1. **Increased Complexity**: Managing multiple data models adds complexity to the synthetic data service
2. **Storage Requirements**: The extended data requires additional storage space
3. **No Native Query Interface**: Unlike the relational database, the document and graph data are stored as files without a native query interface

### Neutral

1. **JSON Format**: Using JSON for both document and graph data provides consistency but may not perfectly simulate specialized document or graph databases
2. **Generated vs. Real Data**: While the synthetic data aims to be realistic, it still lacks some of the nuances and complexities of real-world data

## Examples of Generated Data

### Document Store Example (Product Details)

```json
{
  "product_id": 12,
  "detailed_description": "This premium office chair combines ergonomic design with luxurious materials...",
  "specifications": {
    "dimensions": {
      "length": 65.42,
      "width": 70.18,
      "height": 110.25,
      "unit": "cm"
    },
    "weight": {
      "value": 15.75,
      "unit": "kg"
    },
    "materials": ["leather", "aluminum", "memory foam", "mesh"],
    "colors": ["black", "brown", "white"]
  },
  "features": [
    "Adjustable lumbar support for all-day comfort.",
    "Five-point base with smooth-rolling casters for stability and mobility.",
    "Breathable mesh back keeps you cool during long work sessions."
  ],
  "warranty_info": {
    "duration": 5,
    "coverage": "Full coverage for manufacturing defects and material failure under normal use.",
    "limitations": "Does not cover damage from misuse or unauthorized modifications."
  }
}
```

### Graph Database Example (Employee Network)

```json
{
  "nodes": [
    {
      "id": "employee-1",
      "labels": ["Employee"],
      "properties": {
        "employee_id": 1,
        "name": "John Smith",
        "department": "Sales",
        "position": "Sales Manager",
        "hire_date": "2020-03-15T00:00:00",
        "email": "john.smith@company.com"
      }
    },
    {
      "id": "employee-2",
      "labels": ["Employee"],
      "properties": {
        "employee_id": 2,
        "name": "Jane Doe",
        "department": "Sales",
        "position": "Sales Representative",
        "hire_date": "2021-06-22T00:00:00",
        "email": "jane.doe@company.com"
      }
    }
  ],
  "edges": [
    {
      "id": "manages-1-2",
      "type": "MANAGES",
      "source": "employee-1",
      "target": "employee-2",
      "properties": {
        "since": "2021-06-22T00:00:00"
      }
    },
    {
      "id": "works_with-2-3",
      "type": "WORKS_WITH",
      "source": "employee-2",
      "target": "employee-3",
      "properties": {
        "collaboration_level": "high",
        "projects_count": 8,
        "last_collaboration": "2023-11-15T14:30:00"
      }
    }
  ]
}
```

## Data Fusion Scenarios

The extended data models enable several data fusion scenarios:

1. **Customer 360 View**: Combining relational customer data with document-based feedback and graph-based product interactions
2. **Product Intelligence**: Merging structured product data with detailed document specifications and graph-based relationships
3. **Sales Analysis**: Integrating relational sales data with marketing campaign documents and customer-product interaction graphs
4. **Supply Chain Optimization**: Combining relational inventory data with supply chain network graphs
5. **Employee Performance Analysis**: Merging relational employee data with organizational network graphs

## Future Considerations

1. **Query Interfaces**: Develop interfaces for querying the document and graph data
2. **Data Fusion Algorithms**: Implement algorithms specifically designed for fusing across these data models
3. **Streaming Data**: Add streaming data components to simulate real-time data sources
4. **Data Quality Issues**: Introduce controlled data quality issues to test robustness of fusion algorithms
5. **Specialized Database Systems**: Consider using actual document and graph database systems instead of file-based storage