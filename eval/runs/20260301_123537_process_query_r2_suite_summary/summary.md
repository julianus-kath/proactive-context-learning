# Process Query R2 Suite Summary

| Label | Run ID | Success% | Avg ms | P95 ms | Strict | SameCols | Positional | CommonCols | ReqTablesOK | SQL Exec Err | Quota Hits |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| on_ambiguous | `20260301_122640_ambiguous_v1_process_query_scout_on_r2` | 100.0 | 4674.1 | 9357.0 | 0 | 0 | 0 | 3 | 10 | 0 | 0 |
| off_aligned_ambiguous | `20260301_122935_ambiguous_v1_process_query_scout_off_aligned_r2` | 100.0 | 3358.1 | 4609.0 | 0 | 0 | 0 | 3 | 10 | 0 | 0 |
| off_legacy_ambiguous | `20260301_123213_ambiguous_v1_process_query_scout_off_legacy_r2` | 100.0 | 4570.5 | 8589.0 | 0 | 0 | 1 | 2 | 8 | 0 | 0 |
| on_nonlexical | `20260301_122737_nonlexical_v1_process_query_scout_on_r2` | 100.0 | 4344.2 | 6341.0 | 1 | 1 | 1 | 1 | 9 | 4 | 0 |
| off_aligned_nonlexical | `20260301_123020_nonlexical_v1_process_query_scout_off_aligned_r2` | 100.0 | 4372.8 | 6513.0 | 1 | 1 | 1 | 4 | 9 | 4 | 0 |
| off_legacy_nonlexical | `20260301_123314_nonlexical_v1_process_query_scout_off_legacy_r2` | 100.0 | 4930.4 | 7675.0 | 2 | 2 | 2 | 2 | 13 | 0 | 0 |

## Query-Level Example Counts

| Pair | ON better count | OFF better count |
|---|---:|---:|
| ambiguous_on_vs_off_aligned | 0 | 0 |
| nonlexical_on_vs_off_aligned | 3 | 5 |
| ambiguous_on_vs_off_legacy | 2 | 1 |
| nonlexical_on_vs_off_legacy | 1 | 10 |
