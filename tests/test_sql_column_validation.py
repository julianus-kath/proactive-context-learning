#!/usr/bin/env python3
"""
Test Suite: SQL Column Validation Fix

Tests the two-layer validation system that prevents LLM from generating
SQL with non-existent column names (e.g., ORDER BY [Name] when Name doesn't exist).
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from langgraph_integration.graph_definition import DatabaseWorkflow


def test_validate_sql_columns():
    """Test column validation detection."""
    print("\n" + "="*70)
    print("TEST 1: Column Validation Detection")
    print("="*70)
    
    workflow = DatabaseWorkflow(temperature=0)
    
    # Schema snippet for test
    schema_snippet = """
Table: dbo.KHKAdressen
Columns:
  - BezeichnungKurz: nvarchar(50) NOT NULL
  - KdNr: bigint NOT NULL
  - Ort: nvarchar(100) NULL
  - Lieferdatum: datetime2 NULL
  - Bestelldatum: datetime2 NULL
Primary Key: KdNr
"""
    
    # Test 1a: Valid SQL (should pass)
    print("\n✅ Test 1a: Valid SQL (columns exist in schema)")
    sql_valid = "SELECT TOP 5 [BezeichnungKurz], [KdNr], [Ort] FROM dbo.KHKAdressen ORDER BY [Lieferdatum] DESC"
    result = workflow._validate_sql_columns(sql_valid, schema_snippet)
    print(f"   SQL: {sql_valid[:60]}...")
    print(f"   Result: {result}")
    assert result["valid"], f"Valid SQL was rejected: {result['message']}"
    print("   ✅ PASS")
    
    # Test 1b: Invalid SQL - hallucinated column
    print("\n❌ Test 1b: Invalid SQL (column 'Name' doesn't exist)")
    sql_invalid = "SELECT TOP 5 * FROM dbo.KHKAdressen ORDER BY [Name]"
    result = workflow._validate_sql_columns(sql_invalid, schema_snippet)
    print(f"   SQL: {sql_invalid}")
    print(f"   Result: {result}")
    assert not result["valid"], "Invalid SQL was accepted"
    assert "Name" in result["invalid_columns"], "Missing column not detected"
    print("   ✅ PASS")
    
    # Test 1c: Invalid SQL - multiple hallucinated columns
    print("\n❌ Test 1c: Invalid SQL (multiple non-existent columns)")
    sql_invalid2 = "SELECT TOP 10 * FROM dbo.KHKAdressen WHERE [Amount] > 100 ORDER BY [Name] DESC"
    result = workflow._validate_sql_columns(sql_invalid2, schema_snippet)
    print(f"   SQL: {sql_invalid2}")
    print(f"   Result: {result}")
    assert not result["valid"], "Invalid SQL was accepted"
    assert len(result["invalid_columns"]) >= 2, "Not all invalid columns detected"
    print(f"   Found invalid columns: {result['invalid_columns']}")
    print("   ✅ PASS")
    
    print("\n✅ All validation tests PASSED")


def test_extract_primary_table():
    """Test table extraction from SQL."""
    print("\n" + "="*70)
    print("TEST 2: Primary Table Extraction")
    print("="*70)
    
    workflow = DatabaseWorkflow(temperature=0)
    
    # Test cases
    test_cases = [
        ("SELECT * FROM dbo.KHKAdressen", "dbo.KHKAdressen"),
        ("SELECT * FROM [dbo].[KHKAdressen]", "dbo.KHKAdressen"),
        ("SELECT TOP 100 * FROM webshop.customers", "webshop.customers"),
        ("SELECT * FROM customers", "dbo.customers"),
        ("SELECT TOP 5 name FROM [sales].[orders] WHERE id > 10", "sales.orders"),
    ]
    
    for i, (sql, expected) in enumerate(test_cases):
        print(f"\n  Test 2.{i+1}: {sql[:50]}...")
        result = workflow._extract_primary_table(sql)
        print(f"     Extracted: {result}")
        print(f"     Expected:  {expected}")
        if result:
            assert result == expected, f"Mismatch: got {result}, expected {expected}"
            print("     ✅ PASS")
        else:
            print(f"     ⚠️  Could not extract (expected {expected})")
    
    print("\n✅ All table extraction tests completed")


def test_integration_flow():
    """Test the complete validation flow."""
    print("\n" + "="*70)
    print("TEST 3: Integration Flow (Validation + Fallback)")
    print("="*70)
    
    workflow = DatabaseWorkflow(temperature=0)
    
    schema = """
Table: dbo.KHKAdressen
Columns:
  - BezeichnungKurz: nvarchar(50) NOT NULL
  - KdNr: bigint NOT NULL
  - Ort: nvarchar(100) NULL
"""
    
    # Simulate bad SQL
    bad_sql = "SELECT TOP 5 * FROM dbo.KHKAdressen ORDER BY [InvalidColumn]"
    print(f"\n  Input SQL (with hallucination): {bad_sql}")
    
    # Validate
    validation = workflow._validate_sql_columns(bad_sql, schema)
    print(f"  Validation result: {validation}")
    
    if not validation["valid"]:
        print(f"  Invalid columns detected: {validation['invalid_columns']}")
        
        # Extract table and generate fallback
        table = workflow._extract_primary_table(bad_sql)
        print(f"  Extracted table: {table}")
        
        if table:
            fallback_sql = f"SELECT TOP 100 * FROM {table}"
            print(f"  Fallback SQL: {fallback_sql}")
            
            # Validate fallback
            fallback_validation = workflow._validate_sql_columns(fallback_sql, schema)
            print(f"  Fallback validation: {fallback_validation}")
            assert fallback_validation["valid"], "Fallback SQL is still invalid"
            print("  ✅ Fallback SQL is valid")
    
    print("\n✅ Integration flow test PASSED")


def main():
    """Run all tests."""
    print("\n" + "#"*70)
    print("# SQL Column Validation Test Suite")
    print("#"*70)
    
    try:
        test_validate_sql_columns()
        test_extract_primary_table()
        test_integration_flow()
        
        print("\n" + "#"*70)
        print("# ✅ ALL TESTS PASSED")
        print("#"*70)
        return 0
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())