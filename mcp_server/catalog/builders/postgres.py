import logging
from datetime import datetime
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


class PostgresCatalogBuilder:
    def __init__(self, db_adapter):
        self.db_adapter = db_adapter

    async def build_catalog(self) -> Dict[str, Any]:
        tables = await self._build_table_catalog()
        views = await self._build_view_catalog()
        relationships = await self._build_relationship_catalog()
        metadata = {
            "database_type": "postgres",
            "build_timestamp": datetime.utcnow().isoformat(),
            "tables_count": len(tables),
            "views_count": len(views),
            "relationships_count": len(relationships),
        }
        return {
            "metadata": metadata,
            "tables": list(tables.values()),
            "views": list(views.values()),
            "relationships": relationships,
        }

    async def _build_table_catalog(self) -> Dict[str, Dict[str, Any]]:
        table_query = """
        SELECT
            table_schema,
            table_name,
            table_type
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
          AND table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name
        """
        rows = await self.db_adapter.fetch(table_query, limit=None)
        tables: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            schema = row["table_schema"]
            name = row["table_name"]
            full_name = f"{schema}.{name}"
            columns = await self._get_table_columns(schema, name)
            fk_count = await self._get_foreign_key_count(schema, name)
            estimated_rows, has_rows = await self._estimate_table_rows(schema, name)
            tables[full_name] = {
                "schema": schema,
                "name": name,
                "full_name": full_name,
                "type": "table",
                "estimated_rows": estimated_rows,
                "column_count": len(columns),
                "fk_count": fk_count,
                "has_rows": has_rows,
                "columns": columns,
                "last_updated": datetime.utcnow().isoformat(),
            }
        logger.info("📊 Found %s tables", len(tables))
        return tables

    async def _build_view_catalog(self) -> Dict[str, Dict[str, Any]]:
        view_query = """
        SELECT
            table_schema,
            table_name,
            pg_get_viewdef(format('%I.%I', table_schema, table_name)::regclass, true) AS definition
        FROM information_schema.views
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name
        """
        rows = await self.db_adapter.fetch(view_query, limit=None)
        views: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            schema = row["table_schema"]
            name = row["table_name"]
            definition = row.get("definition") or ""
            full_name = f"{schema}.{name}"
            columns = await self._get_table_columns(schema, name)
            views[full_name] = {
                "schema": schema,
                "name": name,
                "full_name": full_name,
                "type": "view",
                "definition": definition,
                "estimated_rows": 0,
                "column_count": len(columns),
                "columns": columns,
                "dependencies": [],
                "has_rows": False,
                "last_updated": datetime.utcnow().isoformat(),
            }
        logger.info("👁️ Found %s views", len(views))
        return views

    async def _build_relationship_catalog(self) -> List[Dict[str, Any]]:
        relationship_query = """
        SELECT
            tc.constraint_name,
            tc.table_schema,
            tc.table_name,
            kcu.column_name,
            ccu.table_schema AS referenced_schema,
            ccu.table_name AS referenced_table,
            ccu.column_name AS referenced_column
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
         AND ccu.constraint_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
        ORDER BY tc.table_schema, tc.table_name, tc.constraint_name
        """
        rows = await self.db_adapter.fetch(relationship_query, limit=None)
        relationships: List[Dict[str, Any]] = []
        for row in rows:
            relationships.append({
                "constraint_name": row["constraint_name"],
                "from_table": f"{row['table_schema']}.{row['table_name']}",
                "from_column": row["column_name"],
                "to_table": f"{row['referenced_schema']}.{row['referenced_table']}",
                "to_column": row["referenced_column"],
                "type": "foreign_key",
            })
        logger.info("🔗 Found %s foreign keys", len(relationships))
        return relationships

    async def _get_table_columns(self, schema: str, table: str) -> List[Dict[str, Any]]:
        safe_schema = self._sanitize(schema)
        safe_table = self._sanitize(table)
        column_query = f"""
        SELECT
            c.column_name,
            c.data_type,
            c.character_maximum_length,
            c.numeric_precision,
            c.numeric_scale,
            c.is_nullable,
            EXISTS (
                SELECT 1
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = '{safe_schema}'
                  AND tc.table_name = '{safe_table}'
                  AND kcu.column_name = c.column_name
            ) AS is_primary_key,
            EXISTS (
                SELECT 1
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = '{safe_schema}'
                  AND tc.table_name = '{safe_table}'
                  AND kcu.column_name = c.column_name
            ) AS is_foreign_key
        FROM information_schema.columns c
        WHERE c.table_schema = '{safe_schema}'
          AND c.table_name = '{safe_table}'
        ORDER BY c.ordinal_position
        """
        rows = await self.db_adapter.fetch(column_query, limit=None)
        columns: List[Dict[str, Any]] = []
        for col in rows:
            columns.append({
                "name": col["column_name"],
                "data_type": col["data_type"],
                "max_length": col.get("character_maximum_length"),
                "precision": col.get("numeric_precision"),
                "scale": col.get("numeric_scale"),
                "nullable": str(col.get("is_nullable", "YES")).upper() == "YES",
                "is_primary_key": bool(col.get("is_primary_key", False)),
                "is_foreign_key": bool(col.get("is_foreign_key", False)),
            })
        return columns

    async def _get_foreign_key_count(self, schema: str, table: str) -> int:
        safe_schema = self._sanitize(schema)
        safe_table = self._sanitize(table)
        fk_query = f"""
        SELECT COUNT(*) AS fk_count
        FROM information_schema.table_constraints AS tc
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = '{safe_schema}'
          AND tc.table_name = '{safe_table}'
        """
        rows = await self.db_adapter.fetch(fk_query, limit=None)
        return rows[0]["fk_count"] if rows else 0

    async def _estimate_table_rows(self, schema: str, table: str) -> Tuple[int, bool]:
        safe_schema = self._sanitize(schema)
        safe_table = self._sanitize(table)
        estimate_query = f"""
        SELECT COALESCE(reltuples::bigint, 0) AS row_estimate
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = '{safe_schema}' AND c.relname = '{safe_table}'
        LIMIT 1
        """
        rows = await self.db_adapter.fetch(estimate_query, limit=None)
        if rows:
            estimate = int(rows[0].get("row_estimate") or 0)
            return estimate, estimate > 0
        return 0, False

    def _sanitize(self, value: str) -> str:
        return value.replace("'", "''")
