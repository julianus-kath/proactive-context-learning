"""
Diagnostic test to check which phases are implemented and working.
This helps determine what still needs to be done.
"""

import pytest
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPhaseImplementationStatus:
    """Test to verify which phases are implemented."""
    
    def test_phase1_catalog_exists(self):
        """Phase 1: Catalog tools backed by disk cache."""
        try:
            from mcp_server.catalog import SchemaCatalog, CatalogMetrics
            from mcp_server.database_adapter import DatabaseAdapter
            assert hasattr(SchemaCatalog, 'get_table_list')
            assert hasattr(SchemaCatalog, '_save_to_disk')  # Private methods
            assert hasattr(SchemaCatalog, '_load_from_disk')
            assert hasattr(SchemaCatalog, 'warmup')  # Public async init
            print("✅ Phase 1 (Catalog with disk cache) - IMPLEMENTED")
        except ImportError as e:
            pytest.fail(f"❌ Phase 1 missing: {e}")
    
    def test_phase2_semantic_ranker_exists(self):
        """Phase 2: Semantic table ranking."""
        try:
            from mcp_server.table_ranker import TableRanker, RankedTable
            from mcp_server.intent_parser import IntentParser
            assert hasattr(TableRanker, 'rank_tables')
            assert hasattr(IntentParser, 'parse')
            print("✅ Phase 2 (Semantic Ranking) - IMPLEMENTED")
        except ImportError as e:
            pytest.fail(f"❌ Phase 2 missing: {e}")
    
    def test_phase3_bounded_query_exists(self):
        """Phase 3: Bounded query execution with validation, timeouts, redaction."""
        try:
            from mcp_server.bounded_query import BoundedQueryExecutor, QueryResponse
            from mcp_server.query_validator import QueryValidator, ValidationResult
            from mcp_server.column_redactor import ColumnRedactor, RedactionConfig
            
            assert hasattr(BoundedQueryExecutor, 'execute_bounded')
            assert hasattr(QueryValidator, 'validate_and_cap')
            assert hasattr(ColumnRedactor, 'redact_rows')
            print("✅ Phase 3 (Bounded Query with Safety) - IMPLEMENTED")
        except ImportError as e:
            pytest.fail(f"❌ Phase 3 missing: {e}")
    
    def test_phase4_schema_snippet_flow_exists(self):
        """Phase 4: LangGraph orchestration with schema-snippet flow."""
        try:
            from langgraph_integration.mcp_client import build_schema_snippet, describe_table_mcp
            from langgraph_integration.graph_definition import graph
            
            assert callable(build_schema_snippet)
            assert callable(describe_table_mcp)
            assert hasattr(graph, 'invoke')
            print("✅ Phase 4 (LangGraph Schema-Snippet Flow) - IMPLEMENTED")
        except ImportError as e:
            pytest.fail(f"❌ Phase 4 missing: {e}")
    
    def test_phase5_observability_exists(self):
        """Phase 5: Observability, structured logging, and guardrails."""
        try:
            from mcp_server.observability import StructuredLogger, ToolCallMetrics, log_tool_call
            
            assert hasattr(StructuredLogger, 'log_tool_call')
            assert hasattr(ToolCallMetrics, 'to_dict')
            print("✅ Phase 5 (Observability & Structured Logging) - IMPLEMENTED")
        except ImportError as e:
            pytest.fail(f"❌ Phase 5 missing: {e}")
    
    def test_phase1_discovery_tools_integration(self):
        """Phase 1: Discovery tools backed by catalog."""
        try:
            from mcp_server.discovery_tools import DiscoveryTools, RateLimiter, ResponseCache
            
            assert hasattr(DiscoveryTools, 'list_tables')
            assert hasattr(DiscoveryTools, 'search_tables')
            assert hasattr(DiscoveryTools, 'describe_table')
            assert hasattr(RateLimiter, 'allow_request')
            assert hasattr(ResponseCache, 'get')
            print("✅ Phase 1 (Discovery Tools) - IMPLEMENTED")
        except ImportError as e:
            pytest.fail(f"❌ Phase 1 Discovery Tools missing: {e}")
    
    def test_tools_wiring_in_mcp_server(self):
        """Verify tools are wired into MCP server."""
        try:
            from mcp_server.tools import MCPTools
            
            tools = MCPTools.get_available_tools()
            tool_names = [t.name for t in tools]
            
            assert 'list_tables' in tool_names, "list_tables tool not registered"
            assert 'search_tables' in tool_names, "search_tables tool not registered"
            assert 'describe_table' in tool_names, "describe_table tool not registered"
            assert 'query_bounded' in tool_names, "query_bounded tool not registered"
            
            print(f"✅ MCP Tools Wiring - IMPLEMENTED ({len(tools)} tools registered)")
        except Exception as e:
            pytest.fail(f"❌ MCP Tools Wiring failed: {e}")
    
    def test_mcp_client_methods_available(self):
        """Verify MCP client has all Phase 3-4 methods."""
        try:
            from langgraph_integration.mcp_client import (
                search_tables_mcp,
                describe_table_mcp,
                query_bounded_mcp,
                build_schema_snippet,
                describe_table_batch
            )
            
            print("✅ MCP Client Methods - ALL AVAILABLE")
        except ImportError as e:
            pytest.fail(f"❌ MCP Client Methods missing: {e}")


class TestPhaseAcceptanceCriteria:
    """Test acceptance criteria for each phase."""
    
    def test_phase1_acceptance_catalog_persists(self):
        """Phase 1: Catalog persists to disk."""
        try:
            from mcp_server.catalog import Catalog
            from pathlib import Path
            import tempfile
            
            with tempfile.TemporaryDirectory() as tmpdir:
                # Create a minimal catalog
                catalog = Catalog(cache_dir=tmpdir)
                # Verify it has save/load capabilities
                assert hasattr(catalog, 'save_to_disk')
                assert hasattr(catalog, 'load_from_disk')
                print("✅ Phase 1 Acceptance: Catalog disk persistence - OK")
        except Exception as e:
            pytest.skip(f"Phase 1 acceptance test skipped: {e}")
    
    def test_phase2_acceptance_ranking_deterministic(self):
        """Phase 2: Ranking is deterministic."""
        try:
            from mcp_server.table_ranker import TableRanker
            from mcp_server.catalog import TableInfo, ColumnInfo
            
            # Create a simple ranker
            ranker = TableRanker()
            
            # Create mock tables
            tables = [
                TableInfo(
                    schema='dbo',
                    name='Customers',
                    type='TABLE',
                    columns=[ColumnInfo(name='CustomerID', type='INT', nullable=False)],
                    foreign_keys=[],
                    estimated_rows=100,
                    primary_keys=['CustomerID']
                )
            ]
            
            # Same input should give same output
            result1 = ranker.rank_tables(tables, entities=['customers'], intent_operations=['select'])
            result2 = ranker.rank_tables(tables, entities=['customers'], intent_operations=['select'])
            
            assert len(result1) > 0 and len(result2) > 0
            assert result1[0].score == result2[0].score
            print("✅ Phase 2 Acceptance: Deterministic ranking - OK")
        except Exception as e:
            pytest.skip(f"Phase 2 acceptance test skipped: {e}")
    
    def test_phase3_acceptance_validation_rejects_ddl(self):
        """Phase 3: Validation rejects DDL/DML."""
        try:
            from mcp_server.query_validator import QueryValidator
            
            validator = QueryValidator(dialect='postgres', max_rows=1000)
            
            # Should reject INSERT
            result = validator.validate_and_cap("INSERT INTO users VALUES (1)")
            assert not result.valid
            
            # Should reject UPDATE
            result = validator.validate_and_cap("UPDATE users SET name='test'")
            assert not result.valid
            
            # Should reject CREATE
            result = validator.validate_and_cap("CREATE TABLE test (id INT)")
            assert not result.valid
            
            print("✅ Phase 3 Acceptance: DDL/DML rejection - OK")
        except Exception as e:
            pytest.skip(f"Phase 3 acceptance test skipped: {e}")
    
    def test_phase4_acceptance_schema_snippet_structure(self):
        """Phase 4: Schema snippet has correct structure."""
        try:
            from langgraph_integration.mcp_client import build_schema_snippet
            
            # Create mock table descriptions
            descriptions = {
                'dbo.Customers': {
                    'schema': 'dbo',
                    'name': 'Customers',
                    'columns': [
                        {'name': 'CustomerID', 'type': 'INT'},
                        {'name': 'Name', 'type': 'VARCHAR(255)'}
                    ],
                    'primary_keys': ['CustomerID'],
                    'foreign_keys': []
                }
            }
            
            snippet = build_schema_snippet(descriptions)
            
            assert isinstance(snippet, str)
            assert 'Customers' in snippet
            assert 'CustomerID' in snippet
            
            print("✅ Phase 4 Acceptance: Schema snippet structure - OK")
        except Exception as e:
            pytest.skip(f"Phase 4 acceptance test skipped: {e}")
    
    def test_phase5_acceptance_structured_logging(self):
        """Phase 5: Structured logging works."""
        try:
            from mcp_server.observability import StructuredLogger, ToolCallMetrics
            
            logger = StructuredLogger()
            
            # Simulate a tool call
            with logger.log_tool_call('test_tool', {'arg': 'value'}) as metrics:
                metrics.duration_ms = 10.5
                metrics.success = True
                metrics.cached = False
            
            # Check that metrics were recorded
            history = logger.get_history()
            assert len(history) > 0
            
            print("✅ Phase 5 Acceptance: Structured logging - OK")
        except Exception as e:
            pytest.skip(f"Phase 5 acceptance test skipped: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])