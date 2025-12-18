import json
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from langgraph_integration.mcp_client import MCPDatabaseTool


@pytest.mark.asyncio
async def test_get_catalog_parses_response(monkeypatch):
    tool = MCPDatabaseTool()

    async def fake_call(tool_name, arguments):
        assert tool_name == "scout_catalog_get"
        assert arguments["include_tables"] is True
        payload = {
            "ok": True,
            "catalog": {
                "tables": {"dbo.Test": {"columns": []}},
                "views": {}
            }
        }
        return [{"type": "text", "text": json.dumps(payload)}]

    monkeypatch.setattr(tool, "call_tool", fake_call)

    catalog = await tool.get_catalog()
    assert isinstance(catalog, dict)
    assert "dbo.Test" in catalog.get("tables", {})


@pytest.mark.asyncio
async def test_build_catalog_forwards_wait_flag(monkeypatch):
    tool = MCPDatabaseTool()
    captured = {}

    async def fake_call(tool_name, arguments):
        captured["tool"] = tool_name
        captured["arguments"] = arguments
        return [{"type": "text", "text": json.dumps({"ok": True, "message": "done"})}]

    monkeypatch.setattr(tool, "call_tool", fake_call)

    result = await tool.build_catalog(wait_for_completion=False)
    assert captured["tool"] == "scout_catalog_refresh"
    assert captured["arguments"]["wait_for_completion"] is False
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_catalog_status_parses_summary(monkeypatch):
    tool = MCPDatabaseTool()

    async def fake_call(tool_name, arguments):
        assert tool_name == "scout_catalog_diagnostics"
        return [{"type": "text", "text": json.dumps({"ok": True, "overview": {"tables": 10}})}]

    monkeypatch.setattr(tool, "call_tool", fake_call)

    status = await tool.catalog_status()
    assert status.get("overview", {}).get("tables") == 10
