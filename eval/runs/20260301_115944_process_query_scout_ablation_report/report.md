# Process Query Scout Ablation Report

## Pairwise Results

| Pair | ON Run | OFF Run | ON Success% | OFF Success% | ON Strict | OFF Strict | ON ReqTablesOK | OFF ReqTablesOK | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| northwind_queries_v1 (historical complete) | `20260223_063000_northwind_process_query_scout_on` | `20260223_063107_northwind_process_query_scout_off` | 100.0 | 100.0 | 2 | 2 | 8 | 8 | ok |
| northwind_more_v1 (historical complete) | `20260223_143212_northwind_more_v1_scout_on` | `20260223_143759_northwind_more_v1_scout_off` | 100.0 | 100.0 | 2 | 2 | 22 | 23 | ok |
| ambiguous_v1 (today, aligned control) | `20260301_115155_ambiguous_v1_process_query_scout_on_r1` | `20260301_115425_ambiguous_v1_process_query_scout_off_aligned_r1` | 100.0 | 100.0 | 0 | 0 | 10 | 10 | ok |
| nonlexical_v1 (today, aligned control) | `20260301_115245_nonlexical_v1_process_query_scout_on_r1` | `20260301_115508_nonlexical_v1_process_query_scout_off_aligned_r1` | 100.0 | 20.0 | 1 | 0 | 10 | 2 | quota_hits_on=0,off=16; invalid_for_quality_claims_due_to_quota |

## Legacy OFF Control (Today)

| Run | Success% | Strict | ReqTablesOK | SQL Exec Errors | Quota Failures |
|---|---:|---:|---:|---:|---:|
| `20260301_115629_ambiguous_v1_process_query_scout_off_legacy_r1` | 0.0 | 0 | 0 | 10 | 10 |
| `20260301_115654_nonlexical_v1_process_query_scout_off_legacy_r1` | 0.0 | 0 | 0 | 20 | 20 |

## Interpretation Guardrails

- Any run with quota failures is invalid for semantic-quality ON/OFF claims.
- Historical complete pairs remain valid evidence for ON/OFF behavior under identical architecture.
- Today's ambiguous aligned pair is valid (both 100% success and zero quota failures).
