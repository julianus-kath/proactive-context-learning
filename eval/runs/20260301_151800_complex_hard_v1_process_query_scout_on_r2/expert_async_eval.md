# Async Expert Evaluation (20260301_151800_complex_hard_v1_process_query_scout_on_r2)

- Reference SQL: `eval/datasets/northwind_queries_complex_hard_v1.reference_sql.json`
- Total queries: `15`
- Strict equal: `2`
- Same-column set equal: `2`
- Positional set equal: `2`
- Common-column set equal: `0`
- Required table coverage: `5`
- SQL execution errors: `3`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| HX1 | False | False | False | False | False | None |
| HX10 | True | True | True | True | None | None |
| HX11 | False | False | False | False | False | None |
| HX12 | True | False | False | False | False | None |
| HX13 | False | False | False | False | False | None |
| HX14 | True | False | False | False | False | None |
| HX15 | False | None | None | None | None | No candidate SQL in /process_query response |
| HX2 | False | False | False | False | None | None |
| HX3 | False | None | None | None | None | No candidate SQL in /process_query response |
| HX4 | False | True | True | True | None | None |
| HX5 | True | False | False | False | False | None |
| HX6 | False | False | False | False | False | None |
| HX7 | False | False | False | False | False | None |
| HX8 | False | None | None | None | None | No candidate SQL in /process_query response |
| HX9 | True | False | False | False | None | None |
