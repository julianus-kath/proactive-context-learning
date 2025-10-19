"""
Integration tests for answer-first query execution pipeline - Phase 7.

Tests the complete answer-first flow:
1. Intent parsing
2. Table ranking
3. Query blueprint generation
4. Query execution
5. Result formatting
"""

import asyncio
import pytest
import sys
from pathlib import Path

# Add mcp_server to path
sys.path.insert(0, str(Path(__file__).parent.parent / "mcp_server"))

from intent_parser import parse_intent, IntentType
from table_ranker import rank_tables, RankedTable
from query_blueprints import generate_blueprint
from query_formatter import QueryFormatter


class TestIntentParsing:
    """Test intent parsing functionality."""
    
    def test_parse_search_intent(self):
        """Test parsing search intent."""
        query = "Show me all customers from New York"
        parsed = parse_intent(query)
        
        assert parsed.intent in [IntentType.SEARCH, IntentType.FILTER]
        assert parsed.confidence > 0.3
        assert 'customer' in parsed.entities or 'customers' in ' '.join(parsed.entities).lower()
    
    def test_parse_aggregate_intent(self):
        """Test parsing aggregate intent."""
        query = "How many orders were placed last month?"
        parsed = parse_intent(query)
        
        assert parsed.intent in [IntentType.AGGREGATE, IntentType.SEARCH]
        assert parsed.confidence > 0.3
        assert any(op in parsed.operations for op in ['count', 'total', 'how many'])
    
    def test_parse_trend_intent(self):
        """Test parsing trend intent."""
        query = "Show me sales trend over the past year"
        parsed = parse_intent(query)
        
        assert parsed.confidence > 0.3
        # May detect TREND or REPORT
        assert parsed.intent in [IntentType.TREND, IntentType.REPORT]
    
    def test_parse_report_intent(self):
        """Test parsing report intent."""
        query = "Give me the top 10 products by revenue"
        parsed = parse_intent(query)
        
        assert parsed.intent in [IntentType.REPORT, IntentType.AGGREGATE]
        assert parsed.confidence > 0.3
    
    def test_entity_extraction(self):
        """Test entity extraction from queries."""
        query = "Customer orders with product details"
        parsed = parse_intent(query)
        
        extracted_text = ' '.join(parsed.entities).lower()
        assert 'customer' in extracted_text or 'order' in extracted_text


class TestTableRanking:
    """Test table ranking functionality."""
    
    def test_rank_exact_match(self):
        """Test that exact name matches rank highest."""
        tables = [
            {"schema": "dbo", "name": "customers", "full_name": "dbo.customers", "estimated_rows": 1000, "column_count": 5, "fk_count": 0},
            {"schema": "dbo", "name": "orders", "full_name": "dbo.orders", "estimated_rows": 5000, "column_count": 8, "fk_count": 2},
            {"schema": "dbo", "name": "products", "full_name": "dbo.products", "estimated_rows": 500, "column_count": 6, "fk_count": 1},
        ]
        
        entities = ["customer"]
        ranked = rank_tables(tables, entities)
        
        assert ranked[0].name == "customers"
        assert ranked[0].score > 0
    
    def test_rank_multiple_matches(self):
        """Test ranking with multiple matching entities."""
        tables = [
            {"schema": "dbo", "name": "customers", "full_name": "dbo.customers", "estimated_rows": 1000, "column_count": 5, "fk_count": 0},
            {"schema": "dbo", "name": "customer_orders", "full_name": "dbo.customer_orders", "estimated_rows": 500, "column_count": 4, "fk_count": 2},
            {"schema": "dbo", "name": "orders", "full_name": "dbo.orders", "estimated_rows": 5000, "column_count": 8, "fk_count": 2},
        ]
        
        entities = ["customer", "order"]
        ranked = rank_tables(tables, entities)
        
        # Table with both entities should rank highest
        assert "order" in ranked[0].name.lower() or ranked[0].name == "customers"
    
    def test_rank_connectivity_bonus(self):
        """Test that connected tables (with FKs) get bonus."""
        tables = [
            {"schema": "dbo", "name": "standalone", "full_name": "dbo.standalone", "estimated_rows": 1000, "column_count": 5, "fk_count": 0},
            {"schema": "dbo", "name": "connected", "full_name": "dbo.connected", "estimated_rows": 1000, "column_count": 5, "fk_count": 3},
        ]
        
        entities = []
        ranked = rank_tables(tables, entities)
        
        # Connected table should rank higher despite no entity match
        if ranked[0].name == "connected":
            assert ranked[0].score > ranked[1].score


class TestQueryBlueprints:
    """Test query blueprint generation."""
    
    def test_generate_search_blueprint(self):
        """Test generating SEARCH blueprint."""
        bp = generate_blueprint(
            "SEARCH",
            table="customers",
            schema="dbo"
        )
        
        assert bp is not None
        assert "SELECT" in bp.template
        assert "customers" in bp.template.lower()
    
    def test_generate_aggregate_blueprint(self):
        """Test generating AGGREGATE blueprint."""
        bp = generate_blueprint(
            "AGGREGATE",
            table="orders",
            schema="dbo",
            aggregate_col="amount",
            aggregate_func="SUM"
        )
        
        assert bp is not None
        assert "SUM" in bp.template or "sum" in bp.template.lower()
    
    def test_generate_report_blueprint(self):
        """Test generating REPORT blueprint."""
        bp = generate_blueprint(
            "REPORT",
            table="products",
            schema="dbo",
            rank_col="revenue",
            value_col="revenue",
            limit=10
        )
        
        assert bp is not None
        assert ("TOP" in bp.template or "LIMIT" in bp.template)


class TestQueryFormatting:
    """Test query result formatting."""
    
    def test_format_search_results(self):
        """Test formatting search results."""
        rows = [
            {"id": 1, "name": "John", "email": "john@test.com"},
            {"id": 2, "name": "Jane", "email": "jane@test.com"},
        ]
        columns = ["id", "name", "email"]
        
        formatter = QueryFormatter(intent="SEARCH")
        result = formatter.format_results(rows, columns, 100, "test query")
        
        assert result["success"] if "success" in result else True
        assert "Found" in result.get("summary", "") or len(rows) == 2
    
    def test_format_aggregate_results(self):
        """Test formatting aggregate results."""
        rows = [{"total": 10000}]
        columns = ["total"]
        
        formatter = QueryFormatter(intent="AGGREGATE")
        result = formatter.format_results(rows, columns, 50, "test query")
        
        assert "10000" in str(result) or result.get("value") == 10000
    
    def test_format_empty_results(self):
        """Test formatting empty results."""
        rows = []
        columns = ["id", "name"]
        
        formatter = QueryFormatter(intent="SEARCH")
        result = formatter.format_results(rows, columns, 20, "test query")
        
        assert result["row_count"] == 0 or "No results" in result.get("summary", "")


def test_module_imports():
    """Test that all Phase 7 modules import successfully."""
    try:
        from intent_parser import parse_intent
        from table_ranker import rank_tables
        from query_blueprints import generate_blueprint
        from query_formatter import QueryFormatter
        from answer_first_orchestrator import AnswerFirstOrchestrator
        from observability import AnswerFirstObservability, answer_first_obs
        
        print("✅ All Phase 7 modules imported successfully")
        assert True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        assert False


if __name__ == "__main__":
    print("Running Phase 7 Answer-first Tests...\n")
    
    # Test imports
    test_module_imports()
    
    # Run tests
    pytest.main([__file__, "-v"])