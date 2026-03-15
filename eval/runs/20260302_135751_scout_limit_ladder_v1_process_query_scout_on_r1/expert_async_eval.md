# Async Expert Evaluation (20260302_135751_scout_limit_ladder_v1_process_query_scout_on_r1)

- Reference SQL: `eval/datasets/northwind_queries_scout_limit_ladder_v1.reference_sql.json`
- Total queries: `15`
- Strict equal: `1`
- Same-column set equal: `1`
- Positional set equal: `2`
- Common-column set equal: `0`
- Required table coverage: `4`
- SQL execution errors: `4`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| LT1_CL10 | False | None | None | None | None | No candidate SQL in /process_query response |
| LT1_CL2 | False | False | False | True | None | None |
| LT1_CL6 | True | False | False | False | None | None |
| LT2_CL10 | False | None | None | None | None | PostgreSQL query failed: column c.customer_segment does not exist |
| LT2_CL2 | False | False | False | False | None | None |
| LT2_CL6 | True | False | False | False | None | None |
| LT3_CL10 | True | True | True | True | None | None |
| LT3_CL2 | False | False | False | False | None | None |
| LT3_CL6 | False | None | None | None | None | No candidate SQL in /process_query response |
| LT4_CL10 | False | False | False | False | None | None |
| LT4_CL2 | False | False | False | False | None | None |
| LT4_CL6 | False | None | None | None | None | No candidate SQL in /process_query response |
| LT5_CL10 | False | False | False | False | None | None |
| LT5_CL2 | False | False | False | False | None | None |
| LT5_CL6 | True | False | False | False | None | None |
