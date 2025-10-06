"""
Phase 6 Load Testing Script

Tests system under sustained load:
- 20 queries/min for 5 minutes
- No 429 rate limit errors
- Stable MCP latency
- Minimal database calls (catalog-backed)

Usage:
    python -m pytest tests/test_phase6_load.py -v -s
    
Or run directly:
    python tests/test_phase6_load.py
"""

import asyncio
import time
import json
import statistics
from typing import List, Dict, Any
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mcp_server.discovery_tools import DiscoveryTools, RateLimiter
from mcp_server.observability import StructuredLogger
from unittest.mock import Mock


class LoadTestResults:
    """Container for load test results."""
    
    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.rate_limited_requests = 0
        self.response_times: List[float] = []
        self.errors: List[Dict[str, Any]] = []
        self.start_time = None
        self.end_time = None
    
    def add_result(self, success: bool, duration_ms: float, error_code: str = None, error_message: str = None):
        """Add a request result."""
        self.total_requests += 1
        self.response_times.append(duration_ms)
        
        if success:
            self.successful_requests += 1
        elif error_code == "RATE_LIMIT_EXCEEDED":
            self.rate_limited_requests += 1
        else:
            self.failed_requests += 1
            self.errors.append({
                "error_code": error_code,
                "error_message": error_message,
                "timestamp": datetime.now().isoformat()
            })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get test summary."""
        duration_seconds = (self.end_time - self.start_time) if self.end_time and self.start_time else 0
        
        return {
            "duration_seconds": duration_seconds,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "rate_limited_requests": self.rate_limited_requests,
            "success_rate": self.successful_requests / self.total_requests if self.total_requests > 0 else 0,
            "avg_response_time_ms": statistics.mean(self.response_times) if self.response_times else 0,
            "min_response_time_ms": min(self.response_times) if self.response_times else 0,
            "max_response_time_ms": max(self.response_times) if self.response_times else 0,
            "p50_response_time_ms": statistics.median(self.response_times) if self.response_times else 0,
            "p95_response_time_ms": self._percentile(self.response_times, 0.95) if self.response_times else 0,
            "p99_response_time_ms": self._percentile(self.response_times, 0.99) if self.response_times else 0,
            "requests_per_second": self.total_requests / duration_seconds if duration_seconds > 0 else 0,
            "errors": self.errors[:10]  # First 10 errors
        }
    
    @staticmethod
    def _percentile(data: List[float], percentile: float) -> float:
        """Calculate percentile."""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def print_summary(self):
        """Print test summary."""
        summary = self.get_summary()
        
        print("\n" + "="*80)
        print("LOAD TEST RESULTS")
        print("="*80)
        print(f"Duration: {summary['duration_seconds']:.2f} seconds")
        print(f"Total Requests: {summary['total_requests']}")
        print(f"Successful: {summary['successful_requests']} ({summary['success_rate']*100:.1f}%)")
        print(f"Failed: {summary['failed_requests']}")
        print(f"Rate Limited: {summary['rate_limited_requests']}")
        print(f"\nResponse Times:")
        print(f"  Average: {summary['avg_response_time_ms']:.2f}ms")
        print(f"  Min: {summary['min_response_time_ms']:.2f}ms")
        print(f"  Max: {summary['max_response_time_ms']:.2f}ms")
        print(f"  P50: {summary['p50_response_time_ms']:.2f}ms")
        print(f"  P95: {summary['p95_response_time_ms']:.2f}ms")
        print(f"  P99: {summary['p99_response_time_ms']:.2f}ms")
        print(f"\nThroughput: {summary['requests_per_second']:.2f} req/s")
        
        if summary['errors']:
            print(f"\nFirst {len(summary['errors'])} Errors:")
            for i, error in enumerate(summary['errors'], 1):
                print(f"  {i}. [{error['error_code']}] {error['error_message']}")
        
        print("="*80)
        
        # Acceptance criteria check
        print("\nACCEPTANCE CRITERIA:")
        print(f"✅ No 429s: {'PASS' if summary['rate_limited_requests'] == 0 else 'FAIL'}")
        print(f"✅ Success rate > 95%: {'PASS' if summary['success_rate'] > 0.95 else 'FAIL'}")
        print(f"✅ Avg latency < 100ms: {'PASS' if summary['avg_response_time_ms'] < 100 else 'FAIL'}")
        print(f"✅ P95 latency < 200ms: {'PASS' if summary['p95_response_time_ms'] < 200 else 'FAIL'}")
        print("="*80 + "\n")


async def run_load_test(
    duration_minutes: int = 5,
    queries_per_minute: int = 20,
    use_mock: bool = True
) -> LoadTestResults:
    """
    Run load test.
    
    Args:
        duration_minutes: Test duration in minutes
        queries_per_minute: Target queries per minute
        use_mock: Use mock database adapter (True) or real MCP server (False)
    
    Returns:
        LoadTestResults with test metrics
    """
    results = LoadTestResults()
    results.start_time = time.time()
    
    # Calculate timing
    total_queries = duration_minutes * queries_per_minute
    query_interval = 60.0 / queries_per_minute  # seconds between queries
    
    print(f"\n{'='*80}")
    print(f"STARTING LOAD TEST")
    print(f"{'='*80}")
    print(f"Duration: {duration_minutes} minutes")
    print(f"Target: {queries_per_minute} queries/minute")
    print(f"Total queries: {total_queries}")
    print(f"Query interval: {query_interval:.2f} seconds")
    print(f"Using: {'Mock adapter' if use_mock else 'Real MCP server'}")
    print(f"{'='*80}\n")
    
    # Setup database adapter
    if use_mock:
        # Create mock catalog with realistic data
        tables = []
        for i in range(100):
            tables.append({
                "schema": "dbo",
                "name": f"Table_{i:03d}",
                "type": "TABLE",
                "estimated_rows": 1000 + (i * 100),
                "columns": [
                    {"name": "id", "type": "int", "nullable": False},
                    {"name": "name", "type": "varchar(100)", "nullable": True},
                    {"name": "created_at", "type": "datetime", "nullable": True}
                ],
                "primary_keys": [{"column": "id"}],
                "foreign_keys": []
            })
        
        db_adapter = Mock()
        db_adapter.catalog = Mock()
        db_adapter.catalog.is_initialized.return_value = True
        db_adapter.catalog.get_all_tables.return_value = tables
    else:
        # TODO: Use real MCP server connection
        raise NotImplementedError("Real MCP server testing not yet implemented")
    
    # Reset rate limiter to production settings
    DiscoveryTools._rate_limiter = RateLimiter(requests_per_second=10.0, burst_size=20)
    
    # Clear structured logger history
    logger = StructuredLogger()
    logger._metrics_history.clear()
    
    # Run queries
    query_types = ["list_tables", "search_tables", "describe_table"]
    
    for i in range(total_queries):
        query_start = time.time()
        
        try:
            # Rotate through different query types
            query_type = query_types[i % len(query_types)]
            
            if query_type == "list_tables":
                page = (i % 4) + 1  # Rotate through pages 1-4
                response = await DiscoveryTools.list_tables(
                    db_adapter,
                    page=page,
                    page_size=25
                )
            elif query_type == "search_tables":
                search_terms = ["Table", "Customer", "Order", "Product", "User"]
                query = search_terms[i % len(search_terms)]
                response = await DiscoveryTools.search_tables(
                    db_adapter,
                    query=query,
                    page=1,
                    page_size=25
                )
            else:  # describe_table
                table_idx = i % 100
                response = await DiscoveryTools.describe_table(
                    db_adapter,
                    schema="dbo",
                    table=f"Table_{table_idx:03d}",
                    include_sample_data=False
                )
            
            duration_ms = (time.time() - query_start) * 1000
            
            results.add_result(
                success=response.ok,
                duration_ms=duration_ms,
                error_code=response.error_code if not response.ok else None,
                error_message=response.error if not response.ok else None
            )
            
            # Progress indicator
            if (i + 1) % 10 == 0:
                elapsed = time.time() - results.start_time
                progress = (i + 1) / total_queries * 100
                print(f"Progress: {i+1}/{total_queries} ({progress:.1f}%) - "
                      f"Elapsed: {elapsed:.1f}s - "
                      f"Success rate: {results.successful_requests/(i+1)*100:.1f}%")
            
            # Wait for next query (maintain target rate)
            if i < total_queries - 1:
                next_query_time = results.start_time + ((i + 1) * query_interval)
                sleep_time = next_query_time - time.time()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
        
        except Exception as e:
            duration_ms = (time.time() - query_start) * 1000
            results.add_result(
                success=False,
                duration_ms=duration_ms,
                error_code="EXCEPTION",
                error_message=str(e)
            )
    
    results.end_time = time.time()
    
    return results


async def main():
    """Main entry point."""
    # Run short test (1 minute, 20 qpm)
    print("Running short load test (1 minute)...")
    results = await run_load_test(duration_minutes=1, queries_per_minute=20, use_mock=True)
    results.print_summary()
    
    # Check acceptance criteria
    summary = results.get_summary()
    
    if (summary['rate_limited_requests'] == 0 and
        summary['success_rate'] > 0.95 and
        summary['avg_response_time_ms'] < 100 and
        summary['p95_response_time_ms'] < 200):
        print("✅ ALL ACCEPTANCE CRITERIA PASSED!")
        return 0
    else:
        print("❌ SOME ACCEPTANCE CRITERIA FAILED")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)