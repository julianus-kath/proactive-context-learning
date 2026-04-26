# ADR-0001: Synthetic Data Service Architecture
**Status**: Accepted
**Date**: 2025-04-16
**Author**: Julianus Kath


## Status

Accepted — **Superseded by [ADR-0012](0012-mcp-only-architecture-migration.md) and [ADR-0013](0013-production-database-optimization-vpn-connectivity.md)**. The synthetic data pipeline was retired when the thesis pivoted to querying the real Luisi & Diener / Sage ERP via VPN. See [`README.md`](README.md) for the full narrative.

## Context

As part of my master thesis on "Proactive Context Learning," we need to create a synthetic environment that emulates realistic company data in CRM and ERP style tables. This data will be used to evaluate queries that fuse data across multiple tables and to test hypotheses about autonomous data crawling, fusion, and analysis.

## Decision

We've decided to implement a Python-based synthetic data generation service with the following key architectural decisions:

1. **SQLAlchemy ORM for Database Interaction**
   - Using SQLAlchemy as an ORM layer provides database agnosticism and simplifies the data model definition.
   - This allows for easy switching between SQLite (for development) and production databases like PostgreSQL or MySQL.

2. **Modular Project Structure**
   - Separating concerns into distinct modules (config, db, models, generator) to enhance maintainability.
   - This structure facilitates future extensions for data crawling, fusion, and analysis.

3. **Data Model Design**
   - Implementing a comprehensive data model that includes:
     - Customers, Products, Suppliers (core business entities)
     - Sales (transactions between customers and products)
     - Warehouse Items (inventory management)
     - Employees (organizational structure with hierarchical relationships)
   - Including foreign key relationships to enable cross-table queries and data fusion experiments.

4. **Faker Library for Synthetic Data**
   - Using the Faker library to generate realistic mock data for names, addresses, emails, etc.
   - This ensures the synthetic data closely resembles real-world data patterns.

5. **Configurable Generation Parameters**
   - Implementing command-line arguments to customize the volume and characteristics of generated data.
   - Supporting reproducibility through random seed configuration.

6. **Environment-based Configuration**
   - Using environment variables for database connection settings to facilitate deployment in different environments.

7. **Test-Driven Approach**
   - Including unit tests to verify data generation logic and referential integrity.

## Consequences

### Positive

- The modular architecture will make it easier to extend the service with additional functionality.
- Database agnosticism allows for flexibility in deployment environments.
- The comprehensive data model enables complex cross-table queries and data fusion experiments.
- Configurable generation parameters facilitate testing with different data volumes and characteristics.

### Negative

- The complexity of the data model may increase the learning curve for new contributors.
- The use of SQLAlchemy introduces an additional dependency and abstraction layer.

### Neutral

- The choice of SQLite as the default database is suitable for development but may require configuration changes for production use.

## Future Considerations

1. **Data Crawling Extensions**
   - The service should be extended to implement crawlers that extract data based on specific criteria.

2. **Data Fusion Capabilities**
   - Modules should be added to combine data from multiple tables to derive insights.

3. **Analysis and Visualization**
   - Analytical queries and visualizations should be built on top of the synthetic data.

4. **Performance Optimization**
   - For large data volumes, batch processing and other optimization techniques may be necessary.