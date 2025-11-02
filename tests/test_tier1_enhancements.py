"""
Phase 9 Tier 1 Enhancements - Validation Tests

Quick tests to verify that:
1. New MCP tools are registered
2. Tier1Enricher can be imported
3. New dataclasses are accessible
"""

import asyncio
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_imports():
    """Test that all new modules can be imported."""
    logger.info("🔍 Testing imports...")
    
    try:
        from mcp_server.tier1_enrichment import (
            ViewDependencyAnalyzer,
            FKCardinalityAnalyzer,
            DomainClusterer,
            Tier1Enricher,
        )
        logger.info("✅ tier1_enrichment module imports successful")
    except Exception as e:
        logger.error(f"❌ Failed to import tier1_enrichment: {e}")
        return False
    
    try:
        from mcp_server.catalog import (
            ForeignKeyCardinality,
            ViewDependency,
            DomainMetadata,
        )
        logger.info("✅ New catalog dataclasses import successful")
    except Exception as e:
        logger.error(f"❌ Failed to import new dataclasses: {e}")
        return False
    
    return True


def test_tools_registered():
    """Test that new tools are registered in MCPTools."""
    logger.info("🔍 Testing tool registration...")
    
    try:
        from mcp_server.tools import MCPTools
        
        tools = MCPTools.get_available_tools()
        tool_names = [tool.name for tool in tools]
        
        required_tools = [
            "get_view_dependencies",
            "get_fk_cardinality",
            "get_domain_clusters",
        ]
        
        for tool_name in required_tools:
            if tool_name in tool_names:
                logger.info(f"   ✅ {tool_name} registered")
            else:
                logger.error(f"   ❌ {tool_name} NOT registered")
                return False
        
        logger.info(f"✅ All {len(required_tools)} Tier 1 tools registered")
        return True
    
    except Exception as e:
        logger.error(f"❌ Failed to check tool registration: {e}")
        return False


def test_dataclass_fields():
    """Test that TableInfo has new fields."""
    logger.info("🔍 Testing TableInfo extensions...")
    
    try:
        from mcp_server.catalog import TableInfo, ColumnInfo
        from dataclasses import fields
        
        table_fields = {f.name for f in fields(TableInfo)}
        
        required_fields = [
            "fk_cardinality",
            "view_dependencies",
            "domain_metadata",
            "is_materialized_view",
            "view_materialization_strategy",
        ]
        
        for field_name in required_fields:
            if field_name in table_fields:
                logger.info(f"   ✅ TableInfo.{field_name} exists")
            else:
                logger.error(f"   ❌ TableInfo.{field_name} missing")
                return False
        
        logger.info(f"✅ All {len(required_fields)} new TableInfo fields present")
        return True
    
    except Exception as e:
        logger.error(f"❌ Failed to check TableInfo fields: {e}")
        return False


def test_enricher_instantiation():
    """Test that Tier1Enricher can be instantiated."""
    logger.info("🔍 Testing Tier1Enricher instantiation...")
    
    try:
        from mcp_server.tier1_enrichment import Tier1Enricher
        from mcp_server.catalog import TableInfo, ColumnInfo, ForeignKeyInfo
        
        # Create a mock catalog
        mock_catalog = {
            "dbo.Orders": TableInfo(
                schema="dbo",
                name="Orders",
                type="BASE TABLE",
                columns=[
                    ColumnInfo(name="OrderID", type="int", nullable=False, is_primary_key=True),
                    ColumnInfo(name="CustomerID", type="int", nullable=False, is_foreign_key=True),
                ],
                foreign_keys=[
                    ForeignKeyInfo(
                        column="CustomerID",
                        referenced_table="Customers",
                        referenced_schema="dbo",
                        referenced_column="CustomerID",
                    ),
                ],
                estimated_rows=10000,
                primary_keys=["OrderID"],
            ),
            "dbo.Customers": TableInfo(
                schema="dbo",
                name="Customers",
                type="BASE TABLE",
                columns=[
                    ColumnInfo(name="CustomerID", type="int", nullable=False, is_primary_key=True),
                    ColumnInfo(name="Name", type="varchar", nullable=False),
                ],
                foreign_keys=[],
                estimated_rows=1000,
                primary_keys=["CustomerID"],
            ),
        }
        
        # Instantiate enricher
        enricher = Tier1Enricher(mock_catalog)
        logger.info("   ✅ Tier1Enricher instantiated successfully")
        
        # Test format detection
        is_dict = enricher._detect_format()
        logger.info(f"   ✅ Format detection works (detected as: {'dict' if is_dict else 'TableInfo'})")
        
        logger.info("✅ Tier1Enricher instantiation test passed")
        return True
    
    except Exception as e:
        import traceback
        logger.error(f"❌ Failed to instantiate Tier1Enricher: {e}")
        logger.error(f"   Traceback: {traceback.format_exc()}")
        return False


def test_analyzers():
    """Test individual analyzers."""
    logger.info("🔍 Testing individual analyzers...")
    
    try:
        from mcp_server.tier1_enrichment import (
            ViewDependencyAnalyzer,
            FKCardinalityAnalyzer,
            DomainClusterer,
        )
        from mcp_server.catalog import TableInfo, ColumnInfo, ForeignKeyInfo
        
        # Create mock catalog
        mock_catalog = {
            "dbo.OrdersView": TableInfo(
                schema="dbo",
                name="OrdersView",
                type="VIEW",
                columns=[
                    ColumnInfo(name="OrderID", type="int", nullable=False),
                ],
                foreign_keys=[
                    ForeignKeyInfo(
                        column="OrderID",
                        referenced_table="Orders",
                        referenced_schema="dbo",
                        referenced_column="OrderID",
                    ),
                ],
                estimated_rows=10000,
                primary_keys=[],
            ),
            "dbo.Orders": TableInfo(
                schema="dbo",
                name="Orders",
                type="BASE TABLE",
                columns=[
                    ColumnInfo(name="OrderID", type="int", nullable=False, is_primary_key=True),
                    ColumnInfo(name="Amount", type="decimal", nullable=False),
                ],
                foreign_keys=[],
                estimated_rows=10000,
                primary_keys=["OrderID"],
            ),
        }
        
        # Test ViewDependencyAnalyzer
        view_analyzer = ViewDependencyAnalyzer(mock_catalog)
        view_deps = view_analyzer.analyze_all_views()
        logger.info(f"   ✅ ViewDependencyAnalyzer found {len(view_deps)} views")
        
        # Test FKCardinalityAnalyzer
        fk_analyzer = FKCardinalityAnalyzer(mock_catalog)
        fk_cards = fk_analyzer.analyze_all_cardinalities()
        logger.info(f"   ✅ FKCardinalityAnalyzer analyzed {len(fk_cards)} tables")
        
        # Test DomainClusterer
        clusterer = DomainClusterer(mock_catalog)
        domains = clusterer.cluster_all_tables()
        logger.info(f"   ✅ DomainClusterer clustered {len(domains)} tables")
        
        logger.info("✅ All analyzers working correctly")
        return True
    
    except Exception as e:
        import traceback
        logger.error(f"❌ Analyzer test failed: {e}")
        logger.error(f"   Traceback: {traceback.format_exc()}")
        return False


async def main():
    """Run all validation tests."""
    logger.info("=" * 60)
    logger.info("Phase 9 Tier 1 Enhancements - Validation Tests")
    logger.info("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Tool Registration", test_tools_registered()))
    results.append(("DataClass Fields", test_dataclass_fields()))
    results.append(("Enricher Instantiation", test_enricher_instantiation()))
    results.append(("Individual Analyzers", test_analyzers()))
    
    # Summary
    logger.info("=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status:8} | {test_name}")
    
    all_passed = all(result for _, result in results)
    
    logger.info("=" * 60)
    if all_passed:
        logger.info("✅ ALL TESTS PASSED - Tier 1 implementation is ready!")
    else:
        logger.error("❌ SOME TESTS FAILED - Please review errors above")
    logger.info("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)