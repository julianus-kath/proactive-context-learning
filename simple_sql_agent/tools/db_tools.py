"""
Database tools for the SQL agent.

These tools wrap the MCP client to provide simple interfaces
for the ReAct agent to use.
"""

import asyncio
import logging
from typing import List, Optional
from langchain_core.tools import tool

from simple_sql_agent.db.mcp_client import get_mcp_client

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async function synchronously."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in an async context, create a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=60)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@tool
def list_tables() -> str:
    """
    List all available tables in the database.

    Use this tool FIRST to understand what data is available before writing queries.
    Returns table names, schemas, and approximate row counts.

    Returns:
        A formatted list of available tables with their details.
    """
    async def _list():
        client = get_mcp_client()
        try:
            return await client.list_tables(page=1, page_size=50)
        finally:
            await client.close()

    try:
        result = _run_async(_list())
        return result if result else "No tables found. The database may be empty or inaccessible."

    except Exception as e:
        logger.error(f"list_tables failed: {e}")
        return f"Error listing tables: {str(e)}"


@tool
def get_schema(table_names: List[str]) -> str:
    """
    Get detailed schema information for specific tables.

    Use this tool to understand the columns, data types, and relationships
    of tables before writing SQL queries.

    Args:
        table_names: List of table names to describe (e.g., ["dbo.Customers", "dbo.Orders"])

    Returns:
        Detailed schema information including columns, types, primary keys, and foreign keys.
    """
    async def _describe_all(names: List[str]):
        client = get_mcp_client()
        try:
            results = []
            for name in names[:5]:  # Limit to 5 tables
                schema_text = await client.describe_table(name)
                results.append(f"\n## {name}\n{schema_text}")
            return results
        finally:
            await client.close()

    try:
        results = _run_async(_describe_all(table_names))
        return "\n".join(results) if results else "No schema information available."

    except Exception as e:
        logger.error(f"get_schema failed: {e}")
        return f"Error getting schema: {str(e)}"


@tool
def search_tables(query: str) -> str:
    """
    Search for tables by keyword or concept.

    Use this tool to find relevant tables when you don't know the exact table names.
    Searches table names, column names, and descriptions.

    Examples:
        - search_tables("inventory") -> finds tables related to stock/inventory
        - search_tables("Bestellung") -> finds order-related tables
        - search_tables("Mitarbeiter") -> finds employee-related tables
        - search_tables("Zeit") -> finds time tracking tables

    Args:
        query: Search term (can be German or English, concept or keyword)

    Returns:
        List of matching tables with relevance scores and descriptions.
    """
    async def _search():
        client = get_mcp_client()
        try:
            return await client.search_tables(query, limit=15)
        finally:
            await client.close()

    try:
        results = _run_async(_search())

        # Handle empty results
        if not results:
            return f"No tables found matching '{query}'. Try different keywords or use list_tables() to see all available tables."

        # Handle string result (MCP may return text directly)
        if isinstance(results, str):
            return results if results else f"No tables found matching '{query}'."

        # Handle list of text items from MCP (format: [{"type": "text", "text": "..."}])
        if isinstance(results, list) and len(results) > 0:
            first = results[0]
            if isinstance(first, dict) and "type" in first and first.get("type") == "text":
                # MCP text response format
                texts = [item.get("text", "") for item in results if isinstance(item, dict)]
                return "\n".join(texts) if texts else f"No tables found matching '{query}'."

        # Handle list of table dicts
        if isinstance(results, list):
            lines = [f"Found {len(results)} tables matching '{query}':\n"]
            for table in results:
                if isinstance(table, dict):
                    name = table.get("name", table.get("table_name", str(table)))
                    score = table.get("score", table.get("relevance", ""))
                    desc = table.get("description", "")
                    row_count = table.get("row_count", "")

                    line = f"- **{name}**"
                    if score:
                        line += f" (relevance: {score:.2f})" if isinstance(score, float) else f" (relevance: {score})"
                    if row_count:
                        line += f" [{row_count} rows]"
                    if desc:
                        line += f"\n  {desc}"
                    lines.append(line)
                elif isinstance(table, str):
                    lines.append(f"- {table}")
                else:
                    lines.append(f"- {str(table)}")
            return "\n".join(lines)

        # Fallback
        return str(results) if results else f"No tables found matching '{query}'."

    except Exception as e:
        logger.error(f"search_tables failed: {e}")
        return f"Error searching tables: {str(e)}. Try using list_tables() instead."


@tool
def execute_query(sql: str) -> str:
    """
    Execute a SQL SELECT query and return the results.

    IMPORTANT MSSQL SYNTAX RULES:
    - Use TOP instead of LIMIT: SELECT TOP 10 * FROM table
    - Always qualify table names: dbo.TableName
    - Use brackets for names with spaces: [Order Details]
    - Date functions: DATEADD, DATEDIFF, GETDATE()

    Args:
        sql: The SQL SELECT query to execute. Must be a SELECT statement.

    Returns:
        Query results formatted as a table, or an error message if execution fails.
    """
    async def _execute():
        client = get_mcp_client()
        try:
            return await client.execute_query(sql, limit=100, timeout=30)
        finally:
            await client.close()

    try:
        result = _run_async(_execute())

        # Check for errors
        if result.get("error"):
            error_msg = result.get("error") or result.get("error_message", "Unknown error")
            return f"Query execution failed: {error_msg}\n\nSQL was:\n{sql}"

        if not result.get("ok", True) and result.get("error_message"):
            return f"Query execution failed: {result['error_message']}\n\nSQL was:\n{sql}"

        # Format successful result
        columns = result.get("columns", [])
        rows = result.get("rows", result.get("data", []))
        row_count = result.get("row_count", len(rows))
        exec_time = result.get("execution_time_ms", "?")
        truncated = result.get("truncated", False)

        # Build output
        lines = [f"Query executed successfully in {exec_time}ms"]
        lines.append(f"Returned {row_count} rows" + (" (truncated)" if truncated else ""))
        lines.append("")

        if not rows:
            lines.append("No results returned.")
            return "\n".join(lines)

        # Format as table (first 20 rows)
        if columns:
            lines.append("| " + " | ".join(str(c) for c in columns) + " |")
            lines.append("|" + "|".join(["---"] * len(columns)) + "|")

        for row in rows[:20]:
            if isinstance(row, dict):
                values = [str(row.get(c, "")) for c in columns]
            else:
                values = [str(v) for v in row]
            lines.append("| " + " | ".join(values) + " |")

        if len(rows) > 20:
            lines.append(f"... and {len(rows) - 20} more rows")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"execute_query failed: {e}")
        return f"Error executing query: {str(e)}\n\nSQL was:\n{sql}"
