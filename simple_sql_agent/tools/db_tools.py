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
            return await client.search_tables(query, limit=20)
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
def get_column_index(table_names: List[str]) -> str:
    """
    Get exact column names for specific tables.

    CRITICAL: Always use this tool BEFORE writing SQL queries to ensure you
    use valid column names. This prevents errors from guessing column names.

    Args:
        table_names: List of table names (e.g., ["dbo.Customers", "dbo.Orders"])

    Returns:
        Formatted list of columns for each table with their data types.
        Use these EXACT column names in your SQL queries.
    """
    async def _get_columns(names: List[str]):
        client = get_mcp_client()
        try:
            return await client.get_column_index(names)
        finally:
            await client.close()

    try:
        result = _run_async(_get_columns(table_names))

        # Handle list response format from MCP server
        # MCP returns [{"type": "text", "text": "...JSON..."}]
        if isinstance(result, list):
            texts = []
            for item in result:
                if isinstance(item, dict) and "text" in item:
                    texts.append(item.get("text", ""))
            text = "\n".join(texts)
            if text:
                try:
                    import json
                    parsed = json.loads(text)
                    # Only use parsed result if it's a dict (expected format)
                    if isinstance(parsed, dict):
                        result = parsed
                    else:
                        # If JSON parsed to a list or other type, return as text
                        return f"Column index data:\n{text}"
                except json.JSONDecodeError:
                    # If not JSON, return the text directly
                    return f"Column index data:\n{text}"
            else:
                # Empty text from list - format list items directly
                return f"Column index data:\n{str(result)}"

        # Handle error response (result is now guaranteed to be dict if we reach here)
        if isinstance(result, dict) and not result.get("ok", True):
            error = result.get("error", "Unknown error")
            return f"Error getting column index: {error}"

        # Handle text response (fallback)
        if isinstance(result, dict) and "text" in result:
            return result["text"]

        # Format structured response
        if isinstance(result, dict) and "data" in result:
            data = result["data"]
            lines = ["Column Index for requested tables:\n"]

            for table_name, table_info in data.items():
                lines.append(f"\n## {table_name}")

                # Get columns list
                columns = table_info.get("columns", [])
                column_details = table_info.get("column_details", [])

                if column_details:
                    # Detailed format with types
                    for col in column_details[:30]:  # Limit to 30 columns
                        col_name = col.get("name", "?")
                        col_type = col.get("type", "?")
                        nullable = "NULL" if col.get("nullable", True) else "NOT NULL"
                        pk = " [PK]" if col.get("is_primary_key") else ""
                        fk = " [FK]" if col.get("is_foreign_key") else ""
                        lines.append(f"  - {col_name} ({col_type}) {nullable}{pk}{fk}")
                    if len(column_details) > 30:
                        lines.append(f"  ... and {len(column_details) - 30} more columns")
                elif columns:
                    # Simple list format
                    lines.append(f"  Columns: {', '.join(columns[:30])}")
                    if len(columns) > 30:
                        lines.append(f"  ... and {len(columns) - 30} more columns")
                else:
                    lines.append("  No columns found")

            return "\n".join(lines)

        # Fallback for unexpected format
        return str(result) if result else "No column information available."

    except Exception as e:
        logger.error(f"get_column_index failed: {e}")
        return f"Error getting column index: {str(e)}"


@tool
def discover_tables(query: str, include_join_paths: bool = True) -> str:
    """
    Comprehensive table discovery for query planning.

    This tool combines search, schema, and relationship information
    in a single call. Use this FIRST when starting a new query.

    Args:
        query: Search term or concept (e.g., "customer orders", "inventory")
        include_join_paths: Whether to include FK join paths between results

    Returns:
        Consolidated discovery results including:
        - Top 5 matching tables with relevance scores
        - Column names for each table
        - Foreign key relationships between tables
    """
    async def _discover():
        client = get_mcp_client()
        try:
            import json

            # Step 1: Search for relevant tables
            search_results = await client.search_tables(query, limit=5)

            # Fallback: If search returns empty or no results, try list_tables
            if not search_results or (isinstance(search_results, str) and "no tables found" in search_results.lower()):
                logger.info(f"search_tables returned no results for '{query}', falling back to list_tables")
                list_result = await client.list_tables(page=1, page_size=20)
                if list_result:
                    return {
                        "ok": True,
                        "text": f"Search for '{query}' found no direct matches. Here are all available tables:\n\n{list_result}",
                        "tables": [],
                        "fallback_used": True,
                    }
                return {"ok": False, "error": f"No tables found for '{query}' and list_tables also returned empty"}

            # Parse search results - MCP returns text and often appends a JSON payload
            tables = []
            if isinstance(search_results, str):
                # Try direct JSON parse first
                try:
                    parsed = json.loads(search_results)
                    if isinstance(parsed, dict) and "data" in parsed:
                        tables = parsed["data"].get("results", [])[:5]
                    elif isinstance(parsed, list):
                        tables = parsed[:5]
                except json.JSONDecodeError:
                    # Fallback: extract embedded JSON block from the response text.
                    marker = "Full response (JSON):"
                    json_candidates = []
                    if marker in search_results:
                        json_candidates.append(search_results.split(marker, 1)[-1].strip())
                    first_brace = search_results.find("{")
                    last_brace = search_results.rfind("}")
                    if first_brace >= 0 and last_brace > first_brace:
                        json_candidates.append(search_results[first_brace:last_brace + 1].strip())

                    for candidate in json_candidates:
                        try:
                            parsed = json.loads(candidate)
                            if isinstance(parsed, dict) and "data" in parsed:
                                tables = parsed["data"].get("results", [])[:5]
                                break
                            if isinstance(parsed, list):
                                tables = parsed[:5]
                                break
                        except json.JSONDecodeError:
                            continue

                    if not tables:
                        # Not parseable JSON - return text for LLM fallback behavior.
                        return {"ok": True, "text": search_results, "tables": []}

            if not tables:
                return {"ok": True, "text": str(search_results), "tables": []}

            table_names = []
            for t in tables:
                if isinstance(t, dict):
                    name = t.get("full_name") or f"{t.get('schema', 'dbo')}.{t.get('name', '')}"
                    table_names.append(name)
                elif isinstance(t, str):
                    table_names.append(t)

            # Step 2: Get column index for all tables at once (with detailed FK info)
            columns_result = await client.get_column_index(table_names)
            columns = {}
            column_details = {}  # Store detailed column info including FK flags
            if isinstance(columns_result, dict) and "data" in columns_result:
                for tname, tdata in columns_result["data"].items():
                    if isinstance(tdata, dict):
                        columns[tname] = tdata.get("columns", [])
                        column_details[tname] = tdata.get("column_details", [])
                    elif isinstance(tdata, list):
                        columns[tname] = tdata
                        column_details[tname] = []

            # Step 3: Get relationships for join paths with FK column details
            relationships = {}
            relationship_details = {}  # Store detailed FK info
            if include_join_paths:
                for table_name in table_names[:3]:  # Limit to top 3
                    try:
                        rels = await client.list_relations(table_name)
                        if isinstance(rels, dict):
                            neighbors = rels.get("neighbors", [])
                            relationships[table_name] = neighbors
                            # Try to get FK column details from the response
                            fk_details = rels.get("foreign_keys", [])
                            if fk_details:
                                relationship_details[table_name] = fk_details
                    except Exception:
                        pass

            # Build consolidated response
            result = {
                "ok": True,
                "query": query,
                "tables": [],
                "join_paths": [],
            }

            for table in tables:
                if isinstance(table, dict):
                    table_name = table.get("full_name") or f"{table.get('schema', 'dbo')}.{table.get('name', '')}"
                    result["tables"].append({
                        "name": table_name,
                        "relevance": table.get("relevance_score", 0),
                        "columns": columns.get(table_name, []),
                        "row_count": table.get("estimated_rows", 0),
                    })

            # Extract join paths from relationships with FK column names
            for table_name, neighbors in relationships.items():
                for neighbor in neighbors:
                    if neighbor in table_names:
                        # Try to find the actual FK column names
                        from_column = None
                        to_column = None

                        # Method 1: Check if we have detailed FK info from list_relations
                        fk_details = relationship_details.get(table_name, [])
                        for fk in fk_details:
                            if isinstance(fk, dict):
                                ref_table = fk.get("referenced_table") or fk.get("to_table")
                                if ref_table == neighbor:
                                    from_column = fk.get("column") or fk.get("from_column")
                                    to_column = fk.get("referenced_column") or fk.get("to_column")
                                    break

                        # Method 2: Infer from column details (FK columns often match PK names)
                        if not from_column:
                            from_cols = column_details.get(table_name, [])
                            to_cols = column_details.get(neighbor, [])

                            # Find FK columns in the "from" table
                            for col in from_cols:
                                if isinstance(col, dict) and col.get("is_foreign_key"):
                                    col_name = col.get("name", "")
                                    # Check if this FK column name exists in the target table (likely PK)
                                    to_col_names = [c.get("name") for c in to_cols if isinstance(c, dict)]
                                    if col_name in to_col_names:
                                        from_column = col_name
                                        to_column = col_name
                                        break
                                    # Also check common patterns like TableNameID -> ID
                                    neighbor_short = neighbor.split(".")[-1] if "." in neighbor else neighbor
                                    if col_name.lower().startswith(neighbor_short.lower().rstrip("s")):
                                        from_column = col_name
                                        # Find likely PK in target
                                        for to_col in to_cols:
                                            if isinstance(to_col, dict) and to_col.get("is_primary_key"):
                                                to_column = to_col.get("name")
                                                break
                                        if not to_column:
                                            to_column = col_name  # Assume same name
                                        break

                        join_path = {
                            "from": table_name,
                            "to": neighbor,
                            "type": "FK"
                        }
                        if from_column:
                            join_path["from_column"] = from_column
                        if to_column:
                            join_path["to_column"] = to_column

                        result["join_paths"].append(join_path)

            return result

        finally:
            await client.close()

    try:
        result = _run_async(_discover())

        # Handle text-only response (search returned unstructured text)
        if isinstance(result, dict) and "text" in result and not result.get("tables"):
            return f"Search results for '{query}':\n{result['text']}"

        # Handle error response
        if isinstance(result, dict) and not result.get("ok", True):
            return result.get("error", "Discovery failed")

        # Format as readable text for the agent
        if not isinstance(result, dict):
            return str(result)

        lines = [f"## Discovery Results for '{result.get('query', query)}'\n"]

        for table in result.get("tables", []):
            relevance = table.get("relevance", 0)
            row_count = table.get("row_count", 0)
            name = table.get("name", "unknown")

            if isinstance(relevance, (int, float)):
                lines.append(f"### {name} (relevance: {relevance:.2f}, ~{row_count} rows)")
            else:
                lines.append(f"### {name} (~{row_count} rows)")

            cols = table.get("columns", [])
            if cols:
                display_cols = cols[:15]  # Limit columns shown
                lines.append(f"Columns: {', '.join(str(c) for c in display_cols)}")
                if len(cols) > 15:
                    lines.append(f"... and {len(cols) - 15} more columns")
            lines.append("")

        join_paths = result.get("join_paths", [])
        if join_paths:
            lines.append("### Join Paths")
            for path in join_paths:
                from_tbl = path.get('from', '?')
                to_tbl = path.get('to', '?')
                from_col = path.get('from_column')
                to_col = path.get('to_column')

                if from_col and to_col:
                    lines.append(f"- {from_tbl}.{from_col} -> {to_tbl}.{to_col} (FK)")
                elif from_col:
                    lines.append(f"- {from_tbl}.{from_col} -> {to_tbl} (FK)")
                else:
                    lines.append(f"- {from_tbl} -> {to_tbl} ({path.get('type', 'FK')})")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"discover_tables failed: {e}")
        return f"Discovery error: {str(e)}"


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
