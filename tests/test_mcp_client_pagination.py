import json
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import pytest
from langgraph_integration import mcp_client


@pytest.mark.asyncio
async def test_list_tables_uses_top_level_page_info():
    payload = {
        "data": {
            "tables": [
                {"name": "orders", "full_name": "public.orders", "type": "BASE TABLE", "column_count": 5, "estimated_rows": 1000, "has_foreign_keys": True, "has_primary_keys": True}
            ]
        },
        "page_info": {"total_items": 321, "total_pages": 7, "page": 2}
    }
    text = "📊 Full response (JSON):\n" + json.dumps(payload)

    class DummyTool(mcp_client.MCPDatabaseTool):
        async def call_tool(self, tool_name, arguments):
            assert tool_name == "list_tables"
            return [{"type": "text", "text": text}]

    tool = DummyTool()
    result = await tool.list_tables(page=2, page_size=5)

    pagination = result["data"]["pagination"]
    assert pagination["total_items"] == payload["page_info"]["total_items"]
    assert pagination["total_pages"] == payload["page_info"]["total_pages"]
    assert pagination["page"] == 2


@pytest.mark.asyncio
async def test_index_database_uses_top_level_page_info(monkeypatch):
    payload = {
        "data": {
            "tables": [
                {"name": "customers", "columns": [{"name": "id"}], "row_count": 10}
            ]
        },
        "page_info": {"total_items": 400, "total_pages": 16, "page": 1}
    }
    text = "📊 Full response (JSON):\n" + json.dumps(payload)

    class FakeTool:
        async def get_schema(self):
            return [{"type": "text", "text": text}]

    monkeypatch.setattr(mcp_client, "MCPDatabaseTool", lambda: FakeTool())

    result = await mcp_client.index_database()
    assert result["total_tables"] == payload["page_info"]["total_items"]
    assert result["page_info"]["total_pages"] == payload["page_info"]["total_pages"]
