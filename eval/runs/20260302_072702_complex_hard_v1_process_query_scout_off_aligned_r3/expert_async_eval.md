# Async Expert Evaluation (20260302_072702_complex_hard_v1_process_query_scout_off_aligned_r3)

- Reference SQL: `eval/datasets/northwind_queries_complex_hard_v1.reference_sql.json`
- Total queries: `15`
- Strict equal: `1`
- Same-column set equal: `1`
- Positional set equal: `1`
- Common-column set equal: `0`
- Required table coverage: `2`
- SQL execution errors: `10`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| HX1 | False | False | False | False | None | None |
| HX10 | False | None | None | None | None | No candidate SQL in /process_query response |
| HX11 | False | None | None | None | None | No candidate SQL in /process_query response |
| HX12 | False | None | None | None | None | No candidate SQL in /process_query response |
| HX13 | False | None | None | None | None | No candidate SQL in /process_query response |
| HX14 | False | None | None | None | None | No candidate SQL in /process_query response |
| HX15 | False | None | None | None | None | No candidate SQL in /process_query response |
| HX2 | False | False | False | False | None | None |
| HX3 | False | None | None | None | None | No candidate SQL in /process_query response |
| HX4 | False | True | True | True | None | None |
| HX5 | True | False | False | False | False | None |
| HX6 | True | False | False | False | False | None |
| HX7 | False | None | None | None | None | No candidate SQL in /process_query response |
| HX8 | False | None | None | None | None | No candidate SQL in /process_query response |
| HX9 | False | None | None | None | None | No candidate SQL in /process_query response |
