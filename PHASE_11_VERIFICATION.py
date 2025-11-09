#!/usr/bin/env python3
"""
Phase 11 Verification: Test that SQL Table Validation Gate works correctly.

This script verifies:
1. Table name extraction from SQL
2. Table name normalization
3. SQL validation against discovered tables
4. Error handling for unknown tables
"""

import asyncio
import sys
from typing import Dict, Any

# Add langgraph_integration to path
sys.path.insert(0, '/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code')

from langgraph_integration.agents.join_sql.agent import JoinPlanAndSQLAgent


def test_table_extraction():
    """Test that table names are correctly extracted from SQL."""
    print("\n" + "="*80)
    print("TEST 1: Table Name Extraction")
    print("="*80)
    
    agent = JoinPlanAndSQLAgent()
    
    test_cases = [
        {
            "sql": "SELECT COUNT(*) FROM dbo.KHKAdressen",
            "expected": ["dbo.KHKAdressen"],
            "name": "Simple FROM"
        },
        {
            "sql": "SELECT * FROM [dbo].[Orders] JOIN dbo.Customers ON Orders.customer_id = Customers.id",
            "expected": ["[dbo].[Orders]", "dbo.Customers"],
            "name": "Multiple with brackets"
        },
        {
            "sql": "SELECT TOP 10 * FROM dbo.KHKAdressen LEFT JOIN dbo.VKBelege ON ...",
            "expected": ["dbo.KHKAdressen", "dbo.VKBelege"],
            "name": "With JOIN types"
        },
    ]
    
    all_passed = True
    for tc in test_cases:
        tables = agent._extract_table_names_from_sql(tc["sql"])
        print(f"\n✓ {tc['name']}")
        print(f"  SQL: {tc['sql'][:60]}...")
        print(f"  Extracted: {tables}")
        print(f"  Expected: {tc['expected']}")
        
        # Check all expected tables are found
        for exp in tc['expected']:
            if exp not in tables:
                print(f"  ❌ MISSING: {exp}")
                all_passed = False
            else:
                print(f"  ✅ Found: {exp}")
    
    return all_passed


def test_table_normalization():
    """Test that table names are correctly normalized."""
    print("\n" + "="*80)
    print("TEST 2: Table Name Normalization")
    print("="*80)
    
    agent = JoinPlanAndSQLAgent()
    
    test_cases = [
        {
            "input": "[dbo].[Orders]",
            "expected": "dbo.orders",
            "name": "Brackets to lowercase"
        },
        {
            "input": "dbo.Orders",
            "expected": "dbo.orders",
            "name": "Simple lowercase"
        },
        {
            "input": "Orders",
            "expected": "orders",
            "name": "Table only"
        },
        {
            "input": "DBO.KHKADRESSEN",
            "expected": "dbo.khkadressen",
            "name": "Uppercase to lowercase"
        },
    ]
    
    all_passed = True
    for tc in test_cases:
        normalized = agent._normalize_table_name(tc["input"])
        passed = normalized == tc["expected"]
        status = "✅" if passed else "❌"
        print(f"\n{status} {tc['name']}")
        print(f"  Input: {tc['input']}")
        print(f"  Result: {normalized}")
        print(f"  Expected: {tc['expected']}")
        
        if not passed:
            all_passed = False
    
    return all_passed


async def test_validation_pass():
    """Test that validation passes when table exists."""
    print("\n" + "="*80)
    print("TEST 3: SQL Validation - PASS Case")
    print("="*80)
    
    agent = JoinPlanAndSQLAgent()
    
    state = {
        "sql_query": "SELECT COUNT(*) FROM dbo.KHKAdressen",
        "relevant_tables": ["dbo.KHKAdressen"],
        "candidate_views": []
    }
    
    print(f"\nValidating SQL: {state['sql_query']}")
    print(f"Discovered tables: {state['relevant_tables']}")
    
    result = await agent._validate_sql_node(state)
    
    if "error_info" in result:
        print(f"❌ VALIDATION FAILED: {result['error_info']['message']}")
        return False
    else:
        print(f"✅ VALIDATION PASSED")
        return True


async def test_validation_fail():
    """Test that validation fails when table doesn't exist."""
    print("\n" + "="*80)
    print("TEST 4: SQL Validation - FAIL Case")
    print("="*80)
    
    agent = JoinPlanAndSQLAgent()
    
    state = {
        "sql_query": "SELECT COUNT(*) FROM dbo.Customer",  # ← Doesn't exist
        "relevant_tables": ["dbo.KHKAdressen"],             # ← Only this exists
        "candidate_views": []
    }
    
    print(f"\nValidating SQL: {state['sql_query']}")
    print(f"Discovered tables: {state['relevant_tables']}")
    
    result = await agent._validate_sql_node(state)
    
    if "error_info" not in result:
        print(f"❌ VALIDATION SHOULD HAVE FAILED but passed")
        return False
    else:
        error_msg = result["error_info"]["message"]
        print(f"✅ VALIDATION CORRECTLY FAILED")
        print(f"Error message: {error_msg[:100]}...")
        
        # Check that error message is helpful
        if "dbo.Customer" in error_msg and "unknown" in error_msg.lower():
            print(f"✅ Error message contains helpful details")
            return True
        else:
            print(f"❌ Error message not helpful enough")
            return False


async def test_validation_with_joins():
    """Test validation with JOIN queries."""
    print("\n" + "="*80)
    print("TEST 5: SQL Validation - With JOINs")
    print("="*80)
    
    agent = JoinPlanAndSQLAgent()
    
    state = {
        "sql_query": """
            SELECT TOP 10 k.name, SUM(v.amount) 
            FROM dbo.KHKAdressen k 
            JOIN dbo.VKBelege v ON k.id = v.customer_id
        """,
        "relevant_tables": ["dbo.KHKAdressen", "dbo.VKBelege"],
        "candidate_views": []
    }
    
    print(f"\nValidating JOIN query")
    print(f"Discovered tables: {state['relevant_tables']}")
    
    result = await agent._validate_sql_node(state)
    
    if "error_info" in result:
        print(f"❌ VALIDATION FAILED: {result['error_info']['message']}")
        return False
    else:
        print(f"✅ VALIDATION PASSED for JOIN query")
        return True


async def test_validation_pass_german_identifiers():
    """Ensure validator accepts queries with German column names."""
    print("\n" + "="*80)
    print("TEST 6: SQL Validation - German Identifiers")
    print("="*80)

    agent = JoinPlanAndSQLAgent()

    state = {
        "sql_query": (
            "SELECT SUM(v.Betrag) AS Gesamtbetrag FROM dbo.VKBelege v "
            "WHERE v.Rechnungsdatum BETWEEN '2024-01-01' AND '2024-12-31'"
        ),
        "relevant_tables": ["dbo.VKBelege"],
        "candidate_views": [],
        "column_index": {"dbo.VKBelege": ["Betrag", "Rechnungsdatum"]},
    }

    result = await agent._validate_sql_node(state)

    validation = result.get("validation_result", {})
    if not validation.get("is_valid"):
        print(f"❌ VALIDATION FAILED: {validation}")
        return False

    print("✅ VALIDATION PASSED for German identifiers")
    return True


async def test_validation_missing_column_hints():
    """Validator should surface actionable hints when a column is missing."""
    print("\n" + "="*80)
    print("TEST 7: SQL Validation - Missing Column Messaging")
    print("="*80)

    agent = JoinPlanAndSQLAgent()

    state = {
        "sql_query": "SELECT v.UnknownSpalte FROM dbo.VKBelege v",
        "relevant_tables": ["dbo.VKBelege"],
        "candidate_views": [],
        "column_index": {"dbo.VKBelege": ["Betrag", "Rechnungsdatum", "Belegnummer"]},
    }

    result = await agent._validate_sql_node(state)

    validation = result.get("validation_result", {})
    if validation.get("is_valid"):
        print("❌ VALIDATION SHOULD HAVE FAILED but passed")
        return False

    error_message = validation.get("error_message", "")
    print(f"Validation error message: {error_message}")
    if "UnknownSpalte" not in error_message:
        print("❌ Error message did not mention the missing column")
        return False

    if not any(hint in error_message for hint in ["Betrag", "Belegnummer", "Rechnungsdatum"]):
        print("❌ Error message did not surface available column hints")
        return False

    print("✅ Missing column error includes actionable hints")
    return True


async def run_all_tests():
    """Run all tests and report summary."""
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*78 + "║")
    print("║" + "PHASE 11 VERIFICATION: SQL TABLE VALIDATION GATE".center(78) + "║")
    print("║" + " "*78 + "║")
    print("╚" + "="*78 + "╝")
    
    results = {}
    
    # Test 1: Table Extraction
    results["Table Extraction"] = test_table_extraction()
    
    # Test 2: Table Normalization
    results["Table Normalization"] = test_table_normalization()
    
    # Test 3: Validation Pass
    results["Validation Pass"] = await test_validation_pass()
    
    # Test 4: Validation Fail
    results["Validation Fail"] = await test_validation_fail()
    
    # Test 5: Validation with JOINs
    results["Validation Joins"] = await test_validation_with_joins()

    # Test 6: German identifiers
    results["Validation German Identifiers"] = await test_validation_pass_german_identifiers()

    # Test 7: Missing column hints
    results["Validation Missing Column"] = await test_validation_missing_column_hints()
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All Phase 11 tests passed! SQL validation gate is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)