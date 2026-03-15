# Async Expert Evaluation (20260302_140259_scout_limit_ladder_v1_process_query_scout_off_aligned_r2)

- Reference SQL: `eval/datasets/northwind_queries_scout_limit_ladder_v1.reference_sql.json`
- Total queries: `15`
- Strict equal: `2`
- Same-column set equal: `2`
- Positional set equal: `3`
- Common-column set equal: `1`
- Required table coverage: `3`
- SQL execution errors: `6`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| LT1_CL10 | False | True | True | True | None | None |
| LT1_CL2 | False | False | False | True | True | None |
| LT1_CL6 | True | False | False | False | None | None |
| LT2_CL10 | False | None | None | None | None | No candidate SQL in /process_query response |
| LT2_CL2 | False | False | False | False | None | None |
| LT2_CL6 | False | None | None | None | None | No candidate SQL in /process_query response |
| LT3_CL10 | True | True | True | True | None | None |
| LT3_CL2 | False | None | None | None | None | No candidate SQL in /process_query response |
| LT3_CL6 | True | False | False | False | None | None |
| LT4_CL10 | False | None | None | None | None | No candidate SQL in /process_query response |
| LT4_CL2 | False | False | False | False | None | None |
| LT4_CL6 | False | None | None | None | None | No candidate SQL in /process_query response |
| LT5_CL10 | False | False | False | False | None | None |
| LT5_CL2 | False | False | False | False | None | None |
| LT5_CL6 | False | None | None | None | None | No candidate SQL in /process_query response |
