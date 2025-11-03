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
            # Build catalog components
            tables = await self._build_table_catalog()
            views = await self._build_view_catalog()
            relationships = await self._build_relationship_catalog()

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

        # Query for table metadata
        table_query = """
        SELECT
            t.TABLE_SCHEMA,
            t.TABLE_NAME,
            t.TABLE_TYPE,
            p.rows as estimated_rows
        FROM INFORMATION_SCHEMA.TABLES t
        LEFT JOIN sys.tables st ON t.TABLE_NAME = st.name
        LEFT JOIN sys.schemas ss ON t.TABLE_SCHEMA = ss.name AND st.schema_id = ss.schema_id
        LEFT JOIN sys.partitions p ON st.object_id = p.object_id AND p.index_id IN (0,1)
        WHERE t.TABLE_TYPE = 'BASE TABLE'
        ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME
        """

        table_rows = await self.db_adapter.execute_query(table_query)
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
        Build view catalog with definitions and dependencies.

        Returns:
            Dict of view_name -> view_metadata
        """
        logger.info("👁️ Building view catalog...")

        # Query for view metadata
        view_query = """
        SELECT
            v.TABLE_SCHEMA,
            v.TABLE_NAME,
            m.definition as view_definition,
            p.rows as estimated_rows
        FROM INFORMATION_SCHEMA.VIEWS v
        LEFT JOIN sys.views sv ON v.TABLE_NAME = sv.name
        LEFT JOIN sys.schemas ss ON v.TABLE_SCHEMA = ss.name AND sv.schema_id = ss.schema_id
        LEFT JOIN sys.sql_modules m ON sv.object_id = m.object_id
        LEFT JOIN sys.partitions p ON sv.object_id = p.object_id AND p.index_id = 0
        ORDER BY v.TABLE_SCHEMA, v.TABLE_NAME
        """

        view_rows = await self.db_adapter.execute_query(view_query)
        views = {}

        for row in view_rows:
            schema_name = row["TABLE_SCHEMA"]
            view_name = row["TABLE_NAME"]
            full_name = f"{schema_name}.{view_name}"

            # Get column details
            columns = await self._get_table_columns(schema_name, view_name)

            # Get dependencies
            dependencies = await self._get_view_dependencies(schema_name, view_name)

            # Classify view purpose (basic heuristic)
            role_coverage = self._classify_view_role(row.get("view_definition", ""), dependencies)

            view_metadata = {
                "schema": schema_name,
                "name": view_name,
                "full_name": full_name,
                "type": "view",
                "definition": row.get("view_definition", ""),
                "estimated_rows": row.get("estimated_rows", 0),
                "column_count": len(columns),
                "columns": columns,
                "dependencies": dependencies,
                "role_coverage": role_coverage,
                "has_rows": row.get("estimated_rows", 0) > 0,
                "last_updated": datetime.utcnow().isoformat()
            }

            views[full_name] = view_metadata

        logger.info(f"👁️ Found {len(views)} views")
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

        fk_rows = await self.db_adapter.execute_query(fk_query)
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

        columns = await self.db_adapter.execute_query(
            column_query,
            (schema, table, schema, table, schema, table)
        )

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

        result = await self.db_adapter.execute_query(fk_count_query, (schema, table))
        return result[0]["fk_count"] if result else 0

    async def _get_view_dependencies(self, schema: str, view: str) -> List[str]:
        """
        Get objects that a view depends on.

        Args:
            schema: Schema name
            view: View name

        Returns:
            List of dependent object names
        """
        dep_query = """
        SELECT DISTINCT
            referenced_schema + '.' + referenced_entity as dependency
        FROM sys.sql_expression_dependencies
        WHERE referencing_id = OBJECT_ID(? + '.' + ?)
            AND referenced_class = 1  -- object
        """

        deps = await self.db_adapter.execute_query(dep_query, (schema, view))
        return [row["dependency"] for row in deps]

    def _classify_view_role(self, definition: str, dependencies: List[str]) -> float:
        """
        Classify view's business role based on definition and dependencies.

        Args:
            definition: View SQL definition
            dependencies: List of dependent objects

        Returns:
            Role coverage score (0.0-1.0)
        """
        if not definition:
            return 0.0

        definition_lower = definition.lower()
        score = 0.0

        # Business intelligence indicators
        bi_keywords = ["sum", "count", "avg", "group by", "join", "sales", "revenue", "customer"]
        if any(kw in definition_lower for kw in bi_keywords):
            score += 0.4

        # Multiple table joins indicate complex business logic
        join_count = definition_lower.count("join")
        if join_count > 1:
            score += min(join_count * 0.2, 0.4)

        # Dependencies on multiple tables
        if len(dependencies) > 2:
            score += 0.2

        return min(score, 1.0)
