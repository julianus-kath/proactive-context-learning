import asyncio
import concurrent.futures
from typing import Any, Dict, List, Optional

from langgraph_integration.mcp_client import MCPDatabaseTool


def run_async(coro):
    """Run an async coroutine from sync code, safely handling existing loops."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


class SyncMCPClient:
    """
    Synchronous facade over the async MCPDatabaseTool.
    Use in legacy sync contexts while keeping a single async implementation.
    """

    def __init__(self, mcp_url: Optional[str] = None, api_key: Optional[str] = None) -> None:
        self._tool = MCPDatabaseTool(mcp_url=mcp_url, api_key=api_key)

    def health_check(self) -> bool:
        return run_async(self._tool.health_check())

    def search_tables(self, keyword: str, page: int = 1, page_size: int = 25) -> List[Dict[str, Any]]:
        return run_async(self._tool.search_tables(keyword, page, page_size))

    def describe_table(self, table_name: str, include_sample: bool = False) -> List[Dict[str, Any]]:
        return run_async(self._tool.describe_table(table_name, include_sample))

    def list_relations(self, table_name: str) -> List[Dict[str, Any]]:
        return run_async(self._tool.list_relations(table_name))

    def query(self, sql: str, limit: Optional[int] = None) -> tuple[List[str], List[List[Any]]]:
        envelope = run_async(self._tool.query(sql, limit))
        if not isinstance(envelope, dict):
            return [], []
        columns = envelope.get("columns") or []
        data = envelope.get("data") or []
        if not columns and isinstance(data, list) and data and isinstance(data[0], dict):
            columns = list(data[0].keys())
        columns_list = [str(c) for c in columns] if isinstance(columns, list) else []
        rows_output: List[List[Any]] = []
        if isinstance(data, list):
            for row in data:
                if isinstance(row, dict):
                    rows_output.append([row.get(col) for col in columns_list])
                elif isinstance(row, list):
                    rows_output.append(row)
        return columns_list, rows_output

    def query_bounded(
        self,
        sql: str,
        max_rows: Optional[int] = None,
        timeout_ms: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        return run_async(self._tool.query_bounded(sql, max_rows, timeout_ms))


