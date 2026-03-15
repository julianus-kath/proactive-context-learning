# Northwind Consistency Analysis (10 repeated runs)

## Cohorts
- pre_patch: r1-r5 (old semantic behavior)
- post_patch: r6-r10 (semantic skip on no SQL)

## All runs
- runs: 10
- total queries: 100
- quota error share: 100.0%
- `success_rate_pct`: mean=0.0, stddev=0.0, min=0.0, max=0.0, n=10
- `semantic_strict_accuracy_pct`: mean=0.0, stddev=0.0, min=0.0, max=0.0, n=5
- `semantic_acceptable_accuracy_pct`: mean=0.0, stddev=0.0, min=0.0, max=0.0, n=5
- `catalog_table_coverage_pct`: mean=100.0, stddev=0.0, min=100.0, max=100.0, n=10
- `catalog_column_coverage_pct`: mean=100.0, stddev=0.0, min=100.0, max=100.0, n=10
- `retrieval_avg_recall_at_5`: mean=0.0, stddev=0.0, min=0.0, max=0.0, n=5
- `avg_total_llm_calls`: mean=0.0, stddev=0.0, min=0.0, max=0.0, n=10
- `queries_with_contracts`: mean=5.0, stddev=5.0, min=0, max=10, n=10
- `reference_checked_queries`: mean=0.0, stddev=0.0, min=0, max=0, n=10

## Pre-patch only
- runs: 5
- total queries: 50
- quota error share: 100.0%
- `success_rate_pct`: mean=0.0, stddev=0.0, min=0.0, max=0.0, n=5
- `semantic_strict_accuracy_pct`: mean=0.0, stddev=0.0, min=0.0, max=0.0, n=5
- `semantic_acceptable_accuracy_pct`: mean=0.0, stddev=0.0, min=0.0, max=0.0, n=5
- `catalog_table_coverage_pct`: mean=100.0, stddev=0.0, min=100.0, max=100.0, n=5
- `catalog_column_coverage_pct`: mean=100.0, stddev=0.0, min=100.0, max=100.0, n=5
- `retrieval_avg_recall_at_5`: mean=0.0, stddev=0.0, min=0.0, max=0.0, n=5
- `avg_total_llm_calls`: mean=0.0, stddev=0.0, min=0.0, max=0.0, n=5
- `queries_with_contracts`: mean=10.0, stddev=0.0, min=10, max=10, n=5
- `reference_checked_queries`: mean=0.0, stddev=0.0, min=0, max=0, n=5

## Post-patch only
- runs: 5
- total queries: 50
- quota error share: 100.0%
- `success_rate_pct`: mean=0.0, stddev=0.0, min=0.0, max=0.0, n=5
- `semantic_strict_accuracy_pct`: mean=None, stddev=None, min=None, max=None, n=0
- `semantic_acceptable_accuracy_pct`: mean=None, stddev=None, min=None, max=None, n=0
- `catalog_table_coverage_pct`: mean=100.0, stddev=0.0, min=100.0, max=100.0, n=5
- `catalog_column_coverage_pct`: mean=100.0, stddev=0.0, min=100.0, max=100.0, n=5
- `retrieval_avg_recall_at_5`: mean=None, stddev=None, min=None, max=None, n=0
- `avg_total_llm_calls`: mean=0.0, stddev=0.0, min=0.0, max=0.0, n=5
- `queries_with_contracts`: mean=0.0, stddev=0.0, min=0, max=0, n=5
- `reference_checked_queries`: mean=0.0, stddev=0.0, min=0, max=0, n=5

## Failure reason frequencies (all runs)
- `missing_results`: 100
- `missing_sql`: 100
- `missing_tables`: 100

## Interpretation
- Repetition confirms deterministic failure mode under outage conditions: all runs fail before SQL generation.
- H1 catalog completeness remains stable and fully measured (100% table/column).
- H2a semantic quality cannot be compared from this repetition batch because there is no generated SQL to score.
- Use `20260214_103753_northwind_hypothesis_eval_v2` as the last valid semantic baseline until API quota is restored.
