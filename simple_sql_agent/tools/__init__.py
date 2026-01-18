"""SQL Agent Tools - database interaction tools for the ReAct agent."""

from simple_sql_agent.tools.db_tools import (
    list_tables,
    get_schema,
    search_tables,
    get_column_index,
    discover_tables,
    execute_query,
)

__all__ = [
    "discover_tables",  # PRIMARY - comprehensive discovery
    "list_tables",
    "get_schema",
    "get_column_index",
    "execute_query",
    "search_tables",  # Keep for backward compatibility
]
