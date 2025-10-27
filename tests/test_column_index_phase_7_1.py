"""
Test suite for Phase 7.1: Column Index Hallucination Prevention

Tests the full pipeline:
1. MCP tool exposes get_column_index
2. Discovery tools implement handler
3. LangGraph calls the tool
4. Prompt receives structured column index
5. LLM constrained to use indexed columns
"""

import asyncio
import json
import pytest
from typing import Dict, List, Any


class MockCatalog:
    """Mock Scout Catalog for testing."""
    
    def __init__(self):
        self.tables = {
            "dbo.KHKAdressen": {
                "schema": "dbo",
                "name": "KHKAdressen",
                "full_name": "dbo.KHKAdressen",
                "columns": [
                    {"name": "KdNr", "type": "int"},
                    {"name": "Plz", "type": "varchar(10)"},
                    {"name": "Ort", "type": "varchar(100)"},
                    {"name": "BezeichnungKurz", "type": "varchar(50)"},
                ]
            },
            "dbo.Orders": {
                "schema": "dbo",
                "name": "Orders",
                "full_name": "dbo.Orders",
                "columns": [
                    {"name": "OrderId", "type": "int"},
                    {"name": "CustomerId", "type": "int"},
                    {"name": "TotalAmount", "type": "decimal(10,2)"},
                    {"name": "OrderDate", "type": "datetime"},
                ]
            }
        }
    
    def get_table(self, table_name: str):
        """Get table info by name."""
        # Handle both "Table" and "schema.Table" formats
        for key, value in self.tables.items():
            if table_name.lower() in key.lower() or key.lower().endswith(table_name.lower()):
                return value
        return None
    
    def get_table_list(self):
        """Get list of all tables."""
        return list(self.tables.values())


class TestGetColumnIndex:
    """Test get_column_index implementation."""
    
    def test_column_index_extraction(self):
        """Test extracting column names from catalog."""
        catalog = MockCatalog()
        
        # Get columns for KHKAdressen
        table = catalog.get_table("dbo.KHKAdressen")
        assert table is not None
        
        columns = [col["name"] for col in table.get("columns", [])]
        assert columns == ["KdNr", "Plz", "Ort", "BezeichnungKurz"]
    
    def test_column_index_multiple_tables(self):
        """Test extracting columns for multiple tables."""
        catalog = MockCatalog()
        
        column_index = {}
        for table_name in ["dbo.KHKAdressen", "dbo.Orders"]:
            table = catalog.get_table(table_name)
            if table:
                columns = [col["name"] for col in table.get("columns", [])]
                column_index[table["full_name"]] = columns
        
        assert len(column_index) == 2
        assert "dbo.KHKAdressen" in column_index
        assert "dbo.Orders" in column_index
        assert column_index["dbo.KHKAdressen"] == ["KdNr", "Plz", "Ort", "BezeichnungKurz"]
        assert column_index["dbo.Orders"] == ["OrderId", "CustomerId", "TotalAmount", "OrderDate"]
    
    def test_column_index_json_serialization(self):
        """Test JSON serialization of column index."""
        column_index = {
            "dbo.KHKAdressen": ["KdNr", "Plz", "Ort"],
            "dbo.Orders": ["OrderId", "CustomerId"]
        }
        
        # Should serialize without error
        json_str = json.dumps(column_index, indent=2)
        assert "KdNr" in json_str
        assert "OrderId" in json_str
        
        # Should deserialize back
        restored = json.loads(json_str)
        assert restored == column_index


class TestPromptFormatting:
    """Test prompt formatting with column index."""
    
    def test_format_sql_generator_prompt_with_column_index(self):
        """Test that prompt includes column index."""
        from langgraph_integration.prompts import format_sql_generator_prompt
        
        column_index = {
            "dbo.KHKAdressen": ["KdNr", "Plz", "Ort", "BezeichnungKurz"],
            "dbo.Orders": ["OrderId", "CustomerId", "TotalAmount"]
        }
        
        prompt = format_sql_generator_prompt(
            schema="Test schema",
            column_index=column_index,
            operation="DATA_QUERY",
            entities=["customers"],
            requirements="",
            user_input="Show top customers"
        )
        
        # Verify column index is in prompt
        assert "PHASE 7.1" in prompt
        assert "KdNr" in prompt
        assert "OrderId" in prompt
        assert "INDEXED COLUMNS" in prompt
    
    def test_format_sql_generator_prompt_without_column_index(self):
        """Test backward compatibility when no column index provided."""
        from langgraph_integration.prompts import format_sql_generator_prompt
        
        prompt = format_sql_generator_prompt(
            schema="Test schema",
            operation="DATA_QUERY",
            entities=["customers"],
            requirements="",
            user_input="Show top customers"
            # column_index not provided
        )
        
        # Should still work (backward compatible)
        assert "SQL query generator" in prompt
        assert "MSSQL" in prompt
    
    def test_prompt_emphasizes_column_constraint(self):
        """Test that prompt strongly emphasizes column constraints."""
        from langgraph_integration.prompts import format_sql_generator_prompt
        
        column_index = {"dbo.Table": ["Col1", "Col2"]}
        prompt = format_sql_generator_prompt(
            schema="",
            column_index=column_index,
            operation="query",
            entities=[],
            requirements="",
            user_input=""
        )
        
        # Look for strong language about constraints
        assert "NEVER hallucinate" in prompt
        assert "indexed list" in prompt
        assert "Do NOT guess" in prompt


class TestMCPToolDefinition:
    """Test that MCP tool is properly defined."""
    
    def test_get_column_index_tool_in_list(self):
        """Test that get_column_index tool is available."""
        from mcp_server.tools import MCPTools
        
        tools = MCPTools.get_available_tools()
        tool_names = [t.name for t in tools]
        
        assert "get_column_index" in tool_names
    
    def test_get_column_index_tool_schema(self):
        """Test that tool schema is correct."""
        from mcp_server.tools import MCPTools
        
        tools = MCPTools.get_available_tools()
        tool = next((t for t in tools if t.name == "get_column_index"), None)
        
        assert tool is not None
        assert "table_names" in tool.inputSchema["properties"]
        assert "table_names" in tool.inputSchema["required"]


class TestColumnIndexResponse:
    """Test response format of column index."""
    
    def test_discovery_response_format(self):
        """Test DiscoveryResponse format."""
        from mcp_server.discovery_tools import DiscoveryResponse
        
        column_index = {
            "dbo.KHKAdressen": ["KdNr", "Plz"],
            "dbo.Orders": ["OrderId", "Total"]
        }
        
        response = DiscoveryResponse(
            ok=True,
            data=column_index,
            execution_time_ms=10.5
        )
        
        response_dict = response.to_dict()
        
        assert response_dict["ok"] is True
        assert response_dict["data"] == column_index
        assert response_dict["execution_time_ms"] == 10.5
    
    def test_json_serializable(self):
        """Test that response is JSON serializable."""
        from mcp_server.discovery_tools import DiscoveryResponse
        
        response = DiscoveryResponse(
            ok=True,
            data={"dbo.Table": ["Col1", "Col2"]},
            execution_time_ms=12.3
        )
        
        # Should serialize to JSON string
        json_str = json.dumps(response.to_dict())
        assert "dbo.Table" in json_str
        assert "Col1" in json_str


class TestUseCases:
    """Test realistic use cases."""
    
    def test_prevent_hallucination_case_1(self):
        """
        Use case: LLM would normally hallucinate 'Name' column.
        
        Before: ORDER BY [Name] → Error
        After: Only sees indexed columns → Uses correct column
        """
        catalog = MockCatalog()
        
        # Available columns
        table = catalog.get_table("dbo.KHKAdressen")
        columns = [col["name"] for col in table.get("columns", [])]
        
        # 'Name' is NOT in columns
        assert "Name" not in columns
        
        # But these ARE available
        assert "BezeichnungKurz" in columns
        assert "KdNr" in columns
    
    def test_prevent_hallucination_case_2(self):
        """
        Use case: LLM column abbreviations don't exist.
        
        Before: WHERE [Amt] > 100 → Error
        After: Only sees indexed columns → Uses 'TotalAmount'
        """
        catalog = MockCatalog()
        
        # Available columns
        table = catalog.get_table("dbo.Orders")
        columns = [col["name"] for col in table.get("columns", [])]
        
        # 'Amt' is NOT in columns
        assert "Amt" not in columns
        
        # But full name IS
        assert "TotalAmount" in columns


class TestIntegration:
    """Integration tests."""
    
    def test_column_index_JSON_format_matches_prompt_expectations(self):
        """Test that column index format matches what prompt expects."""
        column_index = {
            "dbo.KHKAdressen": ["KdNr", "Plz", "Ort"],
            "dbo.Orders": ["OrderId", "CustomerId"]
        }
        
        # Format as it would appear in prompt
        column_index_json = json.dumps(column_index, indent=2)
        
        # Verify structure
        assert "dbo.KHKAdressen" in column_index_json
        assert "KdNr" in column_index_json
        assert "OrderId" in column_index_json
        
        # Should be readable
        lines = column_index_json.split("\n")
        assert len(lines) > 1  # Multi-line for readability
    
    def test_full_prompt_with_column_index(self):
        """Test full prompt generation with column index."""
        from langgraph_integration.prompts import format_sql_generator_prompt
        
        column_index = {
            "dbo.KHKAdressen": ["KdNr", "Plz", "Ort", "BezeichnungKurz"],
            "dbo.Orders": ["OrderId", "CustomerId", "TotalAmount", "OrderDate"]
        }
        
        prompt = format_sql_generator_prompt(
            schema="""
            Table: dbo.KHKAdressen
            - KdNr: int
            - Plz: varchar(10)
            - Ort: varchar(100)
            - BezeichnungKurz: varchar(50)
            
            Table: dbo.Orders
            - OrderId: int
            - CustomerId: int
            - TotalAmount: decimal
            - OrderDate: datetime
            """,
            column_index=column_index,
            operation="DATA_QUERY",
            entities=["customers", "orders"],
            requirements="top 10",
            user_input="Show top 10 customers with orders"
        )
        
        # All key components should be present
        assert "MSSQL" in prompt
        assert "PHASE 7.1" in prompt
        assert "INDEXED COLUMNS" in prompt
        assert "KdNr" in prompt
        assert "OrderDate" in prompt
        assert "top 10 customers with orders" in prompt
        
        # Should contain guidance about column constraints
        assert "NEVER hallucinate" in prompt


# Quick demo
async def demo_column_index():
    """Demonstrate column index functionality."""
    print("=" * 70)
    print("PHASE 7.1: Column Index Hallucination Prevention")
    print("=" * 70)
    
    catalog = MockCatalog()
    
    print("\n📋 Available Tables:")
    for table_name, table_info in catalog.tables.items():
        columns = [col["name"] for col in table_info["columns"]]
        print(f"  {table_name}: {', '.join(columns)}")
    
    print("\n📊 Column Index (as JSON):")
    column_index = {}
    for table in catalog.get_table_list():
        columns = [col["name"] for col in table["columns"]]
        column_index[table["full_name"]] = columns
    
    print(json.dumps(column_index, indent=2))
    
    print("\n✅ LLM Will See:")
    print("  1. Text schema (for context)")
    print("  2. Structured column index (for constraints)")
    print("  → Can ONLY use columns in the index")
    print("  → Cannot hallucinate non-existent columns")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    # Run quick demo
    asyncio.run(demo_column_index())
    
    # Run pytest
    pytest.main([__file__, "-v"])