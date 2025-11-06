#!/usr/bin/env python3
"""
Comprehensive Test Suite for ERP Assistant

Tests all query patterns and edge cases implemented in the multi-agent system.
Run this after implementing all phases to validate the system works end-to-end.
"""

import asyncio
import logging
import json
from typing import Dict, List, Any
from langgraph_integration.orchestrator import QueryOrchestrator

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ERPAssistantTester:
    """Comprehensive test suite for the ERP Assistant."""

    def __init__(self):
        self.orchestrator = None
        self.test_results = []

    async def setup(self):
        """Initialize the orchestrator."""
        logger.info("🚀 Setting up ERP Assistant for testing...")
        self.orchestrator = QueryOrchestrator(
            llm_model="gpt-4o",
            llm_temp=0.0,
            max_joins=3,
            max_retries=2,
            row_limit=100,
            query_timeout_seconds=30
        )
        logger.info("✅ Setup complete")

    async def run_test(self, query: str, expected_action: str = None, description: str = "") -> Dict[str, Any]:
        """Run a single test query and record results."""
        logger.info(f"🧪 Testing: {query}")
        if description:
            logger.info(f"   {description}")

        try:
            result = await self.orchestrator.process_query(query)

            test_result = {
                "query": query,
                "description": description,
                "expected_action": expected_action,
                "success": True,
                "error": None,
                "has_sql": bool(result.get("sql_query")),
                "has_result": bool(result.get("exec_result")),
                "intent": result.get("intent", {}),
                "sql_query": result.get("sql_query", ""),
                "error_info": result.get("error_info"),
                "final_answer": result.get("final_answer", "")
            }

            # Check if expected action matches
            if expected_action:
                actual_action = test_result["intent"].get("required_action")
                test_result["action_match"] = actual_action == expected_action
                if not test_result["action_match"]:
                    logger.warning(f"❌ Action mismatch: expected '{expected_action}', got '{actual_action}'")

            logger.info(f"✅ Test completed: SQL={'✅' if test_result['has_sql'] else '❌'}, Result={'✅' if test_result['has_result'] else '❌'}")
            return test_result

        except Exception as e:
            logger.error(f"❌ Test failed: {e}")
            return {
                "query": query,
                "description": description,
                "expected_action": expected_action,
                "success": False,
                "error": str(e),
                "has_sql": False,
                "has_result": False,
                "intent": {},
                "sql_query": "",
                "error_info": None,
                "final_answer": ""
            }

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run the complete test suite."""
        logger.info("🧪 Starting comprehensive ERP Assistant test suite...")

        test_cases = [
            # === BASIC COUNT QUERIES ===
            {
                "query": "How many customers do we have?",
                "expected_action": "count",
                "description": "Basic customer count query"
            },
            {
                "query": "Wie viele Kunden haben wir?",
                "expected_action": "count",
                "description": "German customer count query"
            },
            {
                "query": "How many products do we own?",
                "expected_action": "count",
                "description": "Product count query"
            },

            # === REVENUE/AGGREGATE QUERIES ===
            {
                "query": "Wer sind unsere Top 5 Kunden nach Gesamtumsatz?",
                "expected_action": "topk_sum_by_customer",
                "description": "German top customers by revenue"
            },
            {
                "query": "What was our total revenue last month?",
                "expected_action": "sum_by_customer",  # or trend_series
                "description": "Revenue aggregation query"
            },
            {
                "query": "Wie hoch war unser Gesamtumsatz im letzten Monat?",
                "expected_action": "sum_by_customer",
                "description": "German revenue query"
            },

            # === TIME-BASED QUERIES ===
            {
                "query": "How many projects did we have in October?",
                "expected_action": "month_count",
                "description": "Month-filtered count query"
            },
            {
                "query": "How did our project landscape develop over the last three years?",
                "expected_action": "trend_series",
                "description": "Time series trend analysis"
            },

            # === INVENTORY/STATUS QUERIES ===
            {
                "query": "Welche Produkte sind knapp auf Lager?",
                "expected_action": "count",  # or low_stock
                "description": "Low stock inventory query"
            },

            # === STRATEGIC QUERIES (NEW) ===
            {
                "query": "How has our customer base grown over the last 3 years?",
                "expected_action": "growth_analysis",
                "description": "Customer growth analysis"
            },
            {
                "query": "Compare Q1 vs Q2 performance",
                "expected_action": "comparative_analysis",
                "description": "Quarter-over-quarter comparison"
            },
            {
                "query": "How does productivity vary by department?",
                "expected_action": "department_productivity",
                "description": "Department productivity analysis"
            },

            # === INTERPRETATION/FOLLOW-UP ===
            {
                "query": "These results, can you sort them by revenue descending?",
                "expected_action": "interpret_previous",
                "description": "Follow-up interpretation request"
            },

            # === EDGE CASES & CLARIFICATION ===
            {
                "query": "Top customers",
                "expected_action": None,  # Should need clarification
                "description": "Ambiguous query needing clarification"
            },
            {
                "query": "Count and sum customers",
                "expected_action": None,  # Should need clarification
                "description": "Conflicting metrics"
            },
            {
                "query": "How many customers, products, and projects do we have?",
                "expected_action": None,  # Should need clarification
                "description": "Multiple business domains"
            },

            # === HEALTH CHECKS ===
            {
                "query": "Is the system healthy?",
                "expected_action": None,
                "description": "Health check query"
            }
        ]

        results = []
        for test_case in test_cases:
            result = await self.run_test(**test_case)
            results.append(result)

        # Analyze results
        summary = self._analyze_results(results)

        logger.info("🧪 Test suite completed!")
        logger.info(f"📊 Summary: {summary['total_tests']} tests, {summary['passed']} passed, {summary['failed']} failed")

        return {
            "results": results,
            "summary": summary
        }

    def _analyze_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze test results and generate summary."""
        total = len(results)
        passed = sum(1 for r in results if r["success"] and r["has_sql"])
        failed = total - passed

        # Action matching
        action_matches = sum(1 for r in results if r.get("action_match", True))  # Default True for no expectation
        action_total = sum(1 for r in results if r.get("expected_action") is not None)

        # SQL generation success
        sql_generated = sum(1 for r in results if r["has_sql"])

        # Result generation success
        results_generated = sum(1 for r in results if r["has_result"])

        return {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "sql_generation_rate": sql_generated / total if total > 0 else 0,
            "result_generation_rate": results_generated / total if total > 0 else 0,
            "action_matching_rate": action_matches / action_total if action_total > 0 else 0
        }

    def print_report(self, test_output: Dict[str, Any]):
        """Print a detailed test report."""
        results = test_output["results"]
        summary = test_output["summary"]

        print("\n" + "="*80)
        print("🧪 ERP ASSISTANT COMPREHENSIVE TEST REPORT")
        print("="*80)

        print(f"\n📊 OVERALL SUMMARY:")
        print(f"   Total Tests: {summary['total_tests']}")
        print(f"   Passed: {summary['passed']}")
        print(f"   Failed: {summary['failed']}")
        print(".1f")
        print(".1f")
        print(".1f")

        print(f"\n📋 DETAILED RESULTS:")
        for i, result in enumerate(results, 1):
            status = "✅ PASS" if result["success"] and result["has_sql"] else "❌ FAIL"
            action_status = ""
            if result.get("expected_action"):
                action_status = " (action match)" if result.get("action_match", True) else " (action mismatch)"

            print(f"\n{i:2d}. {status}{action_status}")
            print(f"    Query: {result['query']}")
            if result["description"]:
                print(f"    Desc:  {result['description']}")

            if result["has_sql"]:
                sql_preview = result["sql_query"][:100] + "..." if len(result["sql_query"]) > 100 else result["sql_query"]
                print(f"    SQL:   {sql_preview}")
            else:
                print("    SQL:   ❌ No SQL generated")

            if result.get("error"):
                print(f"    Error: {result['error']}")

        # Success criteria check
        print(f"\n🎯 SUCCESS CRITERIA:")
        criteria = [
            ("SQL Generation Rate > 80%", summary["sql_generation_rate"] > 0.8),
            ("Result Generation Rate > 70%", summary["result_generation_rate"] > 0.7),
            ("Action Matching Rate > 80%", summary["action_matching_rate"] > 0.8),
            ("All Basic Queries Pass", all(r["success"] for r in results if "basic" in r.get("description", "").lower())),
        ]

        all_criteria_pass = True
        for criterion, passed in criteria:
            status = "✅" if passed else "❌"
            print(f"   {status} {criterion}")
            if not passed:
                all_criteria_pass = False

        print(f"\n🏆 FINAL RESULT: {'🎉 ALL TESTS PASSED!' if all_criteria_pass else '⚠️  SOME ISSUES DETECTED'}")
        print("="*80)


async def main():
    """Main test runner."""
    tester = ERPAssistantTester()

    try:
        await tester.setup()
        results = await tester.run_all_tests()
        tester.print_report(results)

        # Save results to file
        with open("test_results.json", "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logger.info("💾 Test results saved to test_results.json")

    except Exception as e:
        logger.error(f"❌ Test suite failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
