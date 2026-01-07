#!/usr/bin/env python3
"""
Run benchmark queries against the Simple SQL Agent.
"""

import sys
import asyncio
import json
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from simple_sql_agent.agent import create_sql_agent


async def run_benchmark(max_queries: int = 12):
    """Run benchmark queries and report results."""

    # Load benchmark queries
    queries = []
    queries_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'eval', 'datasets', 'cockpit_queries.jsonl'
    )

    with open(queries_file, 'r') as f:
        for line in f:
            if line.strip():
                queries.append(json.loads(line))

    # Create agent
    agent = create_sql_agent()

    results = []

    print("=" * 70)
    print("BENCHMARK: Simple SQL Agent")
    print("=" * 70)
    print(f"Running {min(max_queries, len(queries))} queries...")
    print()

    for q in queries[:max_queries]:
        qid = q['id']
        question = q['question']

        print(f"[{qid}] {question[:65]}...")

        start = time.time()
        try:
            result = await agent.arun(question)
            elapsed = time.time() - start

            success = result.get('success', False)
            has_sql = bool(result.get('sql_query'))
            sql = result.get('sql_query', '')
            answer = result.get('answer', '')[:300]

            # Determine if answer looks useful (not an error message)
            is_useful = (
                success and
                'cannot' not in answer.lower() and
                'error' not in answer.lower() and
                'unable' not in answer.lower() and
                'not available' not in answer.lower()
            )

            status = "PASS" if is_useful else "PARTIAL" if has_sql else "FAIL"

            print(f"  Status: {status} | SQL: {'Yes' if has_sql else 'No'} | Time: {elapsed:.1f}s")
            if has_sql:
                print(f"  SQL: {sql[:100]}...")
            print(f"  Answer: {answer[:150]}...")
            print()

            results.append({
                'id': qid,
                'status': status,
                'success': success,
                'has_sql': has_sql,
                'is_useful': is_useful,
                'elapsed_s': elapsed,
                'sql': sql,
                'answer': answer
            })

        except Exception as e:
            elapsed = time.time() - start
            print(f"  Status: ERROR | {str(e)[:100]}")
            print()
            results.append({
                'id': qid,
                'status': 'ERROR',
                'success': False,
                'has_sql': False,
                'is_useful': False,
                'elapsed_s': elapsed,
                'error': str(e)
            })

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total = len(results)
    passed = sum(1 for r in results if r['status'] == 'PASS')
    partial = sum(1 for r in results if r['status'] == 'PARTIAL')
    failed = sum(1 for r in results if r['status'] in ('FAIL', 'ERROR'))
    with_sql = sum(1 for r in results if r.get('has_sql'))
    avg_time = sum(r['elapsed_s'] for r in results) / total if total else 0

    print(f"Total queries:    {total}")
    print(f"PASS (useful):    {passed}/{total} ({100*passed/total:.0f}%)")
    print(f"PARTIAL (has SQL):{partial}/{total} ({100*partial/total:.0f}%)")
    print(f"FAIL/ERROR:       {failed}/{total} ({100*failed/total:.0f}%)")
    print(f"Generated SQL:    {with_sql}/{total} ({100*with_sql/total:.0f}%)")
    print(f"Avg time/query:   {avg_time:.1f}s")

    print()
    print("Note: These benchmark queries expect Northwind schema (Customers, Orders, etc.)")
    print("      The production database has different table names (German ERP).")

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--max', type=int, default=5, help='Max queries to run')
    args = parser.parse_args()

    asyncio.run(run_benchmark(args.max))
