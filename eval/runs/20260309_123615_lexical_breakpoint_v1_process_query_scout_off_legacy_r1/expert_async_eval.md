# Async Expert Evaluation (20260309_123615_lexical_breakpoint_v1_process_query_scout_off_legacy_r1)

- Reference SQL: `eval/datasets/northwind_queries_lexical_breakpoint_v1.reference_sql.json`
- Total queries: `12`
- Strict equal: `2`
- Same-column set equal: `2`
- Positional set equal: `3`
- Common-column set equal: `1`
- Required table coverage: `7`
- SQL execution errors: `1`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| LB_CL10_LX1 | True | True | True | True | None | None |
| LB_CL10_LX2 | True | True | True | True | None | None |
| LB_CL10_LX3 | False | False | False | False | None | None |
| LB_CL2_LX1 | True | False | False | True | True | None |
| LB_CL2_LX2 | False | False | False | False | None | None |
| LB_CL2_LX3 | False | False | False | False | None | None |
| LB_CL3_LX1 | False | None | None | None | None | No candidate SQL in /process_query response |
| LB_CL3_LX2 | False | False | False | False | None | None |
| LB_CL3_LX3 | True | False | False | False | False | None |
| LB_CL6_LX1 | True | False | False | False | None | None |
| LB_CL6_LX2 | True | False | False | False | False | None |
| LB_CL6_LX3 | True | False | False | False | False | None |
