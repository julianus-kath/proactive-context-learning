# ADR 0003: PostgreSQL Migration and Enhanced Data Generation

## Status

Accepted

## Context

The original synthetic data service used SQLite as the database backend, which was suitable for development and small-scale testing. However, for the master thesis on "Proactive Context Learning" and the planned MCP (Model Context Protocol) server and LangGraph integration, we need:

1. **Production-grade database**: PostgreSQL for better performance, concurrent access, and advanced features
2. **Larger datasets**: Thousands to millions of records for realistic testing scenarios
3. **Enhanced data model**: More comprehensive ERP/CRM data with realistic business relationships
4. **MCP readiness**: Optimized schema and indexing for efficient querying by AI agents
5. **LangGraph integration**: Data structure suitable for multi-agent workflows

## Decision

We've decided to migrate from SQLite to PostgreSQL and significantly enhance the data generation capabilities:

### 1. PostgreSQL Migration
- **Database Engine**: Migrated from SQLite to PostgreSQL 13+
- **Connection Pooling**: Implemented connection pooling for better performance
- **Configuration**: Environment-based configuration with `.env` file support
- **Setup Automation**: Created setup scripts for database initialization

### 2. Enhanced Data Model
- **Customers**: Extended with financial data (credit limits, annual revenue, credit ratings)
- **Products**: Added SKUs, barcodes, detailed specifications, and inventory tracking
- **Suppliers**: Enhanced with payment terms, lead times, and performance metrics
- **Employees**: Added hierarchical relationships, compensation details, and organizational structure
- **Sales**: Comprehensive order lifecycle with payment processing and shipping tracking
- **Warehouse**: Multi-location inventory management with reorder levels

### 3. Realistic Data Generation
- **Volume**: Default generation of 5K customers, 10K products, 50K sales transactions
- **Business Logic**: Industry-specific pricing, company size-based segmentation
- **Relationships**: Proper foreign key relationships with referential integrity
- **Data Quality**: Realistic distributions, seasonal patterns, and business rules

### 4. Performance Optimizations
- **Indexing**: Strategic indexes on frequently queried columns
- **Batch Processing**: Configurable batch sizes for large dataset generation
- **Memory Management**: Efficient memory usage for large-scale data generation
- **Query Optimization**: Optimized for both OLTP and analytical queries

### 5. MCP and LangGraph Readiness
- **Schema Documentation**: Comprehensive table and column descriptions
- **Query Patterns**: Optimized for common AI agent query patterns
- **Cross-table Relationships**: Designed for multi-agent data fusion scenarios
- **Analytical Queries**: Pre-optimized for business intelligence and reporting

## Implementation Details

### Database Configuration
```python
# Default PostgreSQL configuration
db_type: str = "postgresql"
db_name: str = "synthetic_erp_data"
db_host: str = "localhost"
db_port: int = 5432
db_user: str = "postgres"
db_password: str = "postgres"
```

### Enhanced Models
- **Decimal Precision**: Financial data uses `Numeric` types for accuracy
- **Indexes**: Strategic indexing on foreign keys and frequently filtered columns
- **Constraints**: Business rule enforcement through database constraints
- **Relationships**: Comprehensive ORM relationships for efficient joins

### Data Generation Scale
```bash
# Default volumes (suitable for development)
--customers 5000
--products 10000
--suppliers 500
--employees 1000
--sales 50000

# Production scale (for comprehensive testing)
--customers 50000
--products 100000
--suppliers 5000
--employees 10000
--sales 1000000
```

### Performance Features
- **Connection Pooling**: 20 base connections, 30 overflow
- **Batch Processing**: Configurable batch sizes (default: 1000)
- **Memory Optimization**: Lazy loading and efficient object creation
- **Query Optimization**: Proper indexing strategy for common query patterns

## Consequences

### Positive

1. **Production Readiness**: PostgreSQL provides enterprise-grade reliability and performance
2. **Scalability**: Can handle millions of records with proper indexing and optimization
3. **Concurrent Access**: Multiple agents can query the database simultaneously
4. **Advanced Features**: Support for complex queries, window functions, and analytical operations
5. **MCP Integration**: Optimized schema for AI agent query patterns
6. **Data Quality**: More realistic and comprehensive business data
7. **Performance**: Significant performance improvements for large datasets
8. **Extensibility**: Easy to add new tables and relationships for future requirements

### Negative

1. **Complexity**: Increased setup complexity compared to SQLite
2. **Dependencies**: Requires PostgreSQL installation and configuration
3. **Resource Usage**: Higher memory and CPU usage for large datasets
4. **Learning Curve**: Team members need PostgreSQL knowledge

### Neutral

1. **Migration Effort**: One-time migration effort from existing SQLite implementation
2. **Configuration**: Additional environment configuration required
3. **Backup Strategy**: Need to implement proper backup procedures for production use

## Validation and Quality Assurance

### Data Validation Script
Created comprehensive validation script that checks:
- Record counts across all tables
- Referential integrity of foreign key relationships
- Business statistics and data distributions
- Data quality metrics and anomaly detection

### Sample Validation Output
```
📊 TABLE RECORD COUNTS
Customers    : 5,000
Products     : 10,000
Suppliers    : 500
Employees    : 1,000
Sales        : 50,000
Warehouse    : 25,000

🔗 REFERENTIAL INTEGRITY CHECK
✅ All foreign key relationships are valid

📈 BUSINESS STATISTICS
Total Revenue: $12,450,678.90
Average Order Value: $248.50
Active Customers: 3,750 (75.0%)
```

## MCP Server Integration Points

### Query Optimization for AI Agents
1. **Customer Queries**: Indexed on region, industry, company_size
2. **Product Queries**: Indexed on category, brand, active status
3. **Sales Analytics**: Indexed on date ranges, customer, product
4. **Employee Queries**: Indexed on department, position, active status

### Multi-Agent Scenarios
1. **Customer Agent**: Focus on customer demographics and behavior
2. **Product Agent**: Handle inventory, catalog, and supplier relationships
3. **Sales Agent**: Process transactions and performance analytics
4. **Finance Agent**: Handle revenue, costs, and financial metrics

### Cross-Domain Analysis
- Customer-Product relationships for recommendation systems
- Sales-Employee relationships for performance tracking
- Supplier-Product relationships for procurement optimization
- Geographic analysis across customers and warehouses

## LangGraph Integration Readiness

### Agent Specialization
- **Domain-specific tables**: Each agent can focus on related table clusters
- **Efficient joins**: Optimized join paths between related entities
- **Analytical queries**: Pre-optimized for common business intelligence patterns

### Workflow Support
- **Transaction tracking**: Complete order lifecycle from creation to delivery
- **Hierarchical data**: Employee management structures and organizational charts
- **Time-series analysis**: Sales trends, inventory movements, employee performance

## Future Considerations

### Immediate Next Steps (Ready for Implementation)
1. **MCP Server Development**: Create MCP server using this PostgreSQL backend
2. **LangGraph Agent Implementation**: Develop specialized agents for different data domains
3. **Query Optimization**: Fine-tune indexes based on actual agent query patterns

### Medium-term Enhancements
1. **Data Streaming**: Real-time data updates for dynamic scenarios
2. **Advanced Analytics**: Machine learning features and predictive analytics
3. **Multi-tenant Support**: Support for multiple synthetic companies
4. **API Layer**: REST/GraphQL APIs for external integrations

### Long-term Vision
1. **Distributed Architecture**: Scale across multiple PostgreSQL instances
2. **Real-time Processing**: Stream processing for live data scenarios
3. **Advanced AI Features**: Vector embeddings for semantic search
4. **Integration Hub**: Connect with external data sources and APIs

## Migration Guide

### For Existing SQLite Users
1. Install PostgreSQL and create database
2. Update configuration to use PostgreSQL connection string
3. Run migration script to recreate schema and data
4. Validate data integrity and performance

### Setup Commands
```bash
# Quick setup for development
python quick_setup.py

# Full production setup
python setup_postgres.py
python -m synthetic_data_service.main --customers 50000 --products 100000 --sales 1000000

# Validation
python validate_data.py
```

This migration positions the synthetic data service as a robust foundation for advanced AI agent development and multi-agent system testing.