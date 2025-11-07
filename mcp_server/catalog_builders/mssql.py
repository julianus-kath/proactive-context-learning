"""
MSSQL Catalog Builder for Scout Mode
Phase 1: Schema crawling for tables, columns, PK/FK, views + dependencies.

Crawls MSSQL schema to build comprehensive catalog metadata:
- Tables with row counts, column details
- Views with definitions and dependencies
- Foreign key relationships
- Primary key information
- Column types and constraints
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class MSSQLCatalogBuilder:
    """
    Builds catalog metadata by crawling MSSQL schema.

    Extracts:
    - Table metadata (name, schema, row counts, FK counts)
    - Column details (name, type, nullable, PK/FK flags)
    - View definitions and dependencies
    - Relationship graphs for join planning
    """

    def __init__(self, db_adapter):
        """
        Initialize MSSQL catalog builder.

        Args:
            db_adapter: Database adapter with query execution capability
        """
        self.db_adapter = db_adapter

    async def build_catalog(self) -> Dict[str, Any]:
        """
        Build complete schema catalog.

        Returns:
            Catalog dictionary with tables, views, relationships
        """
        logger.info("🏗️ Building MSSQL catalog...")

        try:
            # Build catalog components (with error handling for permission issues)
            try:
                tables_dict = await self._build_table_catalog()
                logger.info(f"✅ Built {len(tables_dict)} tables")
            except Exception as e:
                logger.error(f"❌ Failed to build table catalog: {e}")
                raise

            try:
                views_dict = await self._build_view_catalog()
                logger.info(f"✅ Built {len(views_dict)} views")
            except Exception as e:
                logger.warning(f"⚠️ Could not build view catalog due to permissions: {e}")
                views_dict = {}

            # Try to build relationships (may fail due to insufficient permissions)
            try:
                relationships = await self._build_relationship_catalog()
                logger.info(f"✅ Built {len(relationships)} relationships")
            except Exception as e:
                logger.warning(f"⚠️ Could not build relationships due to permissions: {e}")
                relationships = []

            # Convert dicts to lists for search API compatibility
            tables = list(tables_dict.values())
            views = list(views_dict.values())

            # Combine into final catalog
            catalog = {
                "metadata": {
                    "database_type": "mssql",
                    "build_timestamp": datetime.utcnow().isoformat(),
                    "tables_count": len(tables),
                    "views_count": len(views),
                    "relationships_count": len(relationships)
                },
                "tables": tables,
                "views": views,
                "relationships": relationships
            }

            logger.info(
                f"✅ Catalog built: {len(tables)} tables, {len(views)} views, "
                f"{len(relationships)} relationships"
            )

            return catalog

        except Exception as e:
            logger.error(f"❌ Catalog build failed: {e}")
            raise

    async def _build_table_catalog(self) -> Dict[str, Dict[str, Any]]:
        """
        Build table catalog with metadata.

        Returns:
            Dict of table_name -> table_metadata
        """
        logger.info("📊 Building table catalog...")

        # Query for table metadata - simplified version without VIEW DATABASE STATE permission
        # Uses basic table info without row count statistics (requires special permissions)
        table_query = """
        SELECT
            s.name AS TABLE_SCHEMA,
            t.name AS TABLE_NAME,
            'BASE TABLE' AS TABLE_TYPE,
            0 AS estimated_rows  -- Placeholder: accurate counts require VIEW DATABASE STATE permission
        FROM sys.tables t
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        ORDER BY s.name, t.name
        """

        table_rows = await self.db_adapter.fetch(table_query)
        tables = {}

        for row in table_rows:
            schema_name = row["TABLE_SCHEMA"]
            table_name = row["TABLE_NAME"]
            full_name = f"{schema_name}.{table_name}"

            # Get column details
            columns = await self._get_table_columns(schema_name, table_name)

            # Get relationship counts
            fk_count = await self._get_foreign_key_count(schema_name, table_name)

            table_metadata = {
                "schema": schema_name,
                "name": table_name,
                "full_name": full_name,
                "type": "table",
                "estimated_rows": row.get("estimated_rows", 0),
                "column_count": len(columns),
                "fk_count": fk_count,
                "columns": columns,
                "last_updated": datetime.utcnow().isoformat()
            }

            tables[full_name] = table_metadata

        logger.info(f"📊 Found {len(tables)} tables")
        return tables

    async def _build_view_catalog(self) -> Dict[str, Dict[str, Any]]:
        """
        Build comprehensive view catalog with definitions, dependencies, and business logic analysis.

        Returns:
            Dict of view_name -> view_metadata
        """
        logger.info("👁️ Building comprehensive view catalog...")

        # Simplified view query without VIEW DATABASE STATE permission requirement
        view_query = """
        SELECT
            v.TABLE_SCHEMA,
            v.TABLE_NAME,
            m.definition AS view_definition,
            0 AS estimated_rows,  -- Placeholder: accurate counts require VIEW DATABASE STATE permission
            sv.create_date,
            sv.modify_date,
            CASE WHEN sv.is_replicated = 1 THEN 1 ELSE 0 END AS is_replicated,
            CASE WHEN sv.has_opaque_metadata = 1 THEN 1 ELSE 0 END AS has_opaque_metadata,
            sv.object_id AS view_object_id
        FROM INFORMATION_SCHEMA.VIEWS v
        LEFT JOIN sys.views sv ON v.TABLE_NAME = sv.name
        LEFT JOIN sys.schemas ss ON v.TABLE_SCHEMA = ss.name AND sv.schema_id = ss.schema_id
        LEFT JOIN sys.sql_modules m ON sv.object_id = m.object_id
        ORDER BY v.TABLE_SCHEMA, v.TABLE_NAME
        """

        view_rows = await self.db_adapter.fetch(view_query)
        views = {}

        for row in view_rows:
            schema_name = row["TABLE_SCHEMA"]
            view_name = row["TABLE_NAME"]
            full_name = f"{schema_name}.{view_name}"

            # Get comprehensive column details
            columns = await self._get_table_columns(schema_name, view_name)

            # Get detailed dependencies with types
            dependencies = await self._get_view_dependencies_detailed(schema_name, view_name)

            # Analyze view definition for business logic
            definition = row.get("view_definition", "")
            business_analysis = self._analyze_view_business_logic(definition, columns, dependencies)

            # Classify view purpose with enhanced logic
            role_coverage = self._classify_view_role_advanced(business_analysis, dependencies, columns)

            # Calculate view complexity metrics
            complexity = self._calculate_view_complexity(definition, dependencies, columns)

            # Determine has_rows with fallback micro-probe for non-indexed views
            est_rows = int(row.get("estimated_rows") or 0)
            has_rows_flag = est_rows > 0

            if not has_rows_flag:
                # Best-effort micro-probe using NOEXPAND to force view evaluation; tolerate errors
                try:
                    probe_sql = f"SELECT TOP 1 1 FROM [{schema_name}].[{view_name}] WITH (NOEXPAND)"
                    # Use adapter's default timeout; we only fetch 1 row
                    cols, probe_rows = await self.db_adapter.query(probe_sql, limit=1)
                    has_rows_flag = bool(probe_rows)
                except Exception:
                    # Ignore probe errors; leave has_rows_flag as False
                    pass

            view_metadata = {
                "schema": schema_name,
                "name": view_name,
                "full_name": full_name,
                "type": "view",
                "definition": definition,
                "estimated_rows": est_rows,
                "column_count": len(columns),
                "columns": columns,
                "dependencies": dependencies,
                "role_coverage": role_coverage,
                "business_analysis": business_analysis,
                "complexity": complexity,
                "has_rows": has_rows_flag,
                "is_replicated": bool(row.get("is_replicated", 0)),
                "has_opaque_metadata": bool(row.get("has_opaque_metadata", 0)),
                "create_date": row.get("create_date").isoformat() if row.get("create_date") and hasattr(row.get("create_date"), 'isoformat') else row.get("create_date"),
                "modify_date": row.get("modify_date").isoformat() if row.get("modify_date") and hasattr(row.get("modify_date"), 'isoformat') else row.get("modify_date"),
                "last_updated": datetime.utcnow().isoformat()
            }

            views[full_name] = view_metadata

        logger.info(f"👁️ Found {len(views)} views with comprehensive metadata")
        return views

    async def _build_relationship_catalog(self) -> List[Dict[str, Any]]:
        """
        Build foreign key relationship catalog.

        Returns:
            List of relationship dictionaries
        """
        logger.info("🔗 Building relationship catalog...")

        # Query for foreign key relationships
        fk_query = """
        SELECT
            fk.name as constraint_name,
            s1.name as schema_name,
            t1.name as table_name,
            c1.name as column_name,
            s2.name as referenced_schema,
            t2.name as referenced_table,
            c2.name as referenced_column
        FROM sys.foreign_keys fk
        INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
        INNER JOIN sys.tables t1 ON fk.parent_object_id = t1.object_id
        INNER JOIN sys.schemas s1 ON t1.schema_id = s1.schema_id
        INNER JOIN sys.columns c1 ON fkc.parent_object_id = c1.object_id AND fkc.parent_column_id = c1.column_id
        INNER JOIN sys.tables t2 ON fk.referenced_object_id = t2.object_id
        INNER JOIN sys.schemas s2 ON t2.schema_id = s2.schema_id
        INNER JOIN sys.columns c2 ON fkc.referenced_object_id = c2.object_id AND fkc.referenced_column_id = c2.column_id
        ORDER BY s1.name, t1.name, fk.name
        """

        fk_rows = await self.db_adapter.fetch(fk_query)
        relationships = []

        for row in fk_rows:
            relationship = {
                "constraint_name": row["constraint_name"],
                "from_table": f"{row['schema_name']}.{row['table_name']}",
                "from_column": row["column_name"],
                "to_table": f"{row['referenced_schema']}.{row['referenced_table']}",
                "to_column": row["referenced_column"],
                "type": "foreign_key"
            }
            relationships.append(relationship)

        logger.info(f"🔗 Found {len(relationships)} foreign key relationships")
        return relationships

    async def _get_table_columns(self, schema: str, table: str) -> List[Dict[str, Any]]:
        """
        Get detailed column information for a table/view.

        Args:
            schema: Schema name
            table: Table/view name

        Returns:
            List of column dictionaries
        """
        column_query = """
        SELECT
            c.COLUMN_NAME,
            c.DATA_TYPE,
            c.CHARACTER_MAXIMUM_LENGTH,
            c.NUMERIC_PRECISION,
            c.NUMERIC_SCALE,
            c.IS_NULLABLE,
            CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END as is_primary_key,
            CASE WHEN fk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END as is_foreign_key
        FROM INFORMATION_SCHEMA.COLUMNS c
        LEFT JOIN (
            SELECT ku.COLUMN_NAME
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            INNER JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
            WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                AND tc.TABLE_SCHEMA = ? AND tc.TABLE_NAME = ?
        ) pk ON c.COLUMN_NAME = pk.COLUMN_NAME
        LEFT JOIN (
            SELECT ku.COLUMN_NAME
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            INNER JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
            WHERE tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
                AND tc.TABLE_SCHEMA = ? AND tc.TABLE_NAME = ?
        ) fk ON c.COLUMN_NAME = fk.COLUMN_NAME
        WHERE c.TABLE_SCHEMA = ? AND c.TABLE_NAME = ?
        ORDER BY c.ORDINAL_POSITION
        """

        # For parameterized queries, we'll inline the parameters since the catalog builder
        # is a special case that needs to run during startup
        formatted_query = column_query.replace("?", "'{}'").format(schema, table, schema, table, schema, table)
        columns = await self.db_adapter.fetch(formatted_query)

        return [{
            "name": col["COLUMN_NAME"],
            "data_type": col["DATA_TYPE"],
            "max_length": col.get("CHARACTER_MAXIMUM_LENGTH"),
            "precision": col.get("NUMERIC_PRECISION"),
            "scale": col.get("NUMERIC_SCALE"),
            "nullable": col["IS_NULLABLE"] == "YES",
            "is_primary_key": bool(col.get("is_primary_key", 0)),
            "is_foreign_key": bool(col.get("is_foreign_key", 0))
        } for col in columns]

    async def _get_foreign_key_count(self, schema: str, table: str) -> int:
        """
        Get count of foreign keys for a table.

        Args:
            schema: Schema name
            table: Table name

        Returns:
            Number of foreign key constraints
        """
        fk_count_query = """
        SELECT COUNT(*) as fk_count
        FROM sys.foreign_keys fk
        INNER JOIN sys.tables t ON fk.parent_object_id = t.object_id
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        WHERE s.name = ? AND t.name = ?
        """

        formatted_query = fk_count_query.replace("?", "'{}'").format(schema, table)
        result = await self.db_adapter.fetch(formatted_query)
        return result[0]["fk_count"] if result else 0

    async def _get_view_dependencies_detailed(self, schema: str, view: str) -> List[Dict[str, Any]]:
        """
        Get detailed dependency information for a view.

        Args:
            schema: Schema name
            view: View name

        Returns:
            List of dependency dictionaries with types and metadata
        """
        dep_query = """
        SELECT
            referenced_schema_name as schema_name,
            referenced_entity_name as entity_name,
            referenced_class_desc as object_type,
            is_caller_dependent as is_caller_dependent
        FROM sys.sql_expression_dependencies
        WHERE referencing_id = OBJECT_ID(? + '.' + ?)
        ORDER BY referenced_class_desc, referenced_schema_name, referenced_entity_name
        """

        formatted_query = dep_query.replace("?", "'{}'").format(schema, view)
        deps = await self.db_adapter.fetch(formatted_query)

        dependencies = []
        for row in deps:
            dep = {
                "schema": row["schema_name"],
                "name": row["entity_name"],
                "full_name": f"{row['schema_name']}.{row['entity_name']}",
                "type": row["object_type"],
                "is_caller_dependent": bool(row.get("is_caller_dependent", 0))
            }
            dependencies.append(dep)

        return dependencies

    async def _get_view_dependencies(self, schema: str, view: str) -> List[str]:
        """
        Get objects that a view depends on (legacy method for compatibility).

        Args:
            schema: Schema name
            view: View name

        Returns:
            List of dependent object names
        """
        detailed_deps = await self._get_view_dependencies_detailed(schema, view)
        return [dep["full_name"] for dep in detailed_deps]

    def _analyze_view_business_logic(self, definition: str, columns: List[Dict[str, Any]], dependencies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze view definition for business logic patterns.

        Args:
            definition: View SQL definition
            columns: View column metadata
            dependencies: View dependencies

        Returns:
            Business analysis dictionary
        """
        analysis = {
            "has_aggregates": False,
            "has_joins": False,
            "join_count": 0,
            "has_group_by": False,
            "has_order_by": False,
            "has_where_clause": False,
            "has_subqueries": False,
            "estimated_complexity": "simple",
            "business_indicators": [],
            "data_transformation_type": "direct"
        }

        if not definition:
            return analysis

        definition_upper = definition.upper()

        # Check for SQL constructs
        analysis["has_aggregates"] = any(func in definition_upper for func in ["SUM(", "COUNT(", "AVG(", "MIN(", "MAX("])
        analysis["has_group_by"] = "GROUP BY" in definition_upper
        analysis["has_order_by"] = "ORDER BY" in definition_upper
        analysis["has_where_clause"] = "WHERE" in definition_upper
        analysis["has_subqueries"] = "(SELECT" in definition_upper

        # Count joins
        join_keywords = ["INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN", "JOIN"]
        analysis["join_count"] = sum(definition_upper.count(keyword) for keyword in join_keywords)
        analysis["has_joins"] = analysis["join_count"] > 0

        # Determine data transformation type
        if analysis["has_aggregates"] and analysis["has_group_by"]:
            analysis["data_transformation_type"] = "aggregated"
        elif analysis["has_joins"]:
            analysis["data_transformation_type"] = "joined"
        elif analysis["has_where_clause"]:
            analysis["data_transformation_type"] = "filtered"

        # Business indicators
        business_keywords = {
            "sales": ["SALES", "REVENUE", "ORDER", "TRANSACTION", "INVOICE"],
            "customer": ["CUSTOMER", "CLIENT", "USER", "ACCOUNT"],
            "product": ["PRODUCT", "ITEM", "ARTICLE", "GOODS"],
            "financial": ["AMOUNT", "PRICE", "COST", "PROFIT", "MARGIN"],
            "time": ["DATE", "TIME", "PERIOD", "MONTH", "YEAR"]
        }

        for category, keywords in business_keywords.items():
            if any(kw in definition_upper for kw in keywords):
                analysis["business_indicators"].append(category)

        # Estimate complexity
        complexity_score = 0
        complexity_score += analysis["join_count"] * 2
        complexity_score += 3 if analysis["has_aggregates"] else 0
        complexity_score += 2 if analysis["has_subqueries"] else 0
        complexity_score += 1 if analysis["has_group_by"] else 0
        complexity_score += len(dependencies) * 0.5

        if complexity_score >= 8:
            analysis["estimated_complexity"] = "high"
        elif complexity_score >= 4:
            analysis["estimated_complexity"] = "medium"
        else:
            analysis["estimated_complexity"] = "low"

        return analysis

    def _classify_view_role_advanced(self, business_analysis: Dict[str, Any], dependencies: List[Dict[str, Any]], columns: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Advanced view role classification based on comprehensive analysis.

        Args:
            business_analysis: Business logic analysis
            dependencies: View dependencies
            columns: View columns

        Returns:
            Role coverage scores for different business roles
        """
        roles = {
            "reporting": 0.0,      # Business intelligence and reporting views
            "operational": 0.0,    # Day-to-day operational data
            "analytical": 0.0,     # Complex analytical aggregations
            "integration": 0.0,    # Data integration and consolidation
            "security": 0.0        # Access control and security views
        }

        # Reporting role indicators
        if business_analysis["data_transformation_type"] in ["aggregated", "joined"]:
            roles["reporting"] += 0.6
        if "sales" in business_analysis["business_indicators"] or "financial" in business_analysis["business_indicators"]:
            roles["reporting"] += 0.4

        # Analytical role indicators
        if business_analysis["has_aggregates"] and business_analysis["estimated_complexity"] in ["medium", "high"]:
            roles["analytical"] += 0.7
        if business_analysis["join_count"] >= 3:
            roles["analytical"] += 0.3

        # Operational role indicators
        if business_analysis["data_transformation_type"] == "filtered" and business_analysis["estimated_complexity"] == "low":
            roles["operational"] += 0.5
        if len(dependencies) <= 2 and business_analysis["join_count"] <= 1:
            roles["operational"] += 0.3

        # Integration role indicators
        if business_analysis["join_count"] >= 2 and len(dependencies) >= 3:
            roles["integration"] += 0.6
        if business_analysis["data_transformation_type"] == "joined":
            roles["integration"] += 0.4

        # Security role indicators (lower priority, harder to detect)
        if "security" in business_analysis.get("business_indicators", []):
            roles["security"] += 0.4

        return roles

    def _calculate_view_complexity(self, definition: str, dependencies: List[Dict[str, Any]], columns: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate view complexity metrics.

        Args:
            definition: View SQL definition
            dependencies: View dependencies
            columns: View columns

        Returns:
            Complexity metrics dictionary
        """
        complexity = {
            "dependency_count": len(dependencies),
            "column_count": len(columns),
            "definition_length": len(definition) if definition else 0,
            "table_dependency_count": len([d for d in dependencies if d.get("type") == "OBJECT_OR_COLUMN"]),
            "view_dependency_count": len([d for d in dependencies if d.get("type") == "VIEW"]),
            "function_dependency_count": len([d for d in dependencies if d.get("type") == "SCALAR_FUNCTION"]),
            "estimated_maintenance_cost": "low"
        }

        # Estimate maintenance cost
        maintenance_score = complexity["dependency_count"] + complexity["column_count"] // 10
        if definition:
            maintenance_score += len(definition) // 1000  # Longer definitions are harder to maintain

        if maintenance_score >= 10:
            complexity["estimated_maintenance_cost"] = "high"
        elif maintenance_score >= 5:
            complexity["estimated_maintenance_cost"] = "medium"

        return complexity

    def _classify_view_role(self, definition: str, dependencies: List[str]) -> float:
        """
        Legacy view role classification (for backward compatibility).

        Args:
            definition: View SQL definition
            dependencies: List of dependent objects

        Returns:
            Role coverage score (0.0-1.0)
        """
        # Convert detailed dependencies to simple list for legacy method
        if isinstance(dependencies[0], dict):
            simple_deps = [dep["full_name"] for dep in dependencies]
        else:
            simple_deps = dependencies

        business_analysis = self._analyze_view_business_logic(definition, [], [])
        role_scores = self._classify_view_role_advanced(business_analysis, [], [])

        # Return the highest role score as a single float
        return max(role_scores.values()) if role_scores else 0.0
