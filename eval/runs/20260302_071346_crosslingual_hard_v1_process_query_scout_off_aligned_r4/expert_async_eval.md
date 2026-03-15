# Async Expert Evaluation (20260302_071346_crosslingual_hard_v1_process_query_scout_off_aligned_r4)

- Reference SQL: `eval/datasets/northwind_queries_crosslingual_hard_v1.reference_sql.json`
- Total queries: `12`
- Strict equal: `2`
- Same-column set equal: `2`
- Positional set equal: `2`
- Common-column set equal: `1`
- Required table coverage: `5`
- SQL execution errors: `3`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| CL1 | True | False | False | False | False | None |
| CL10 | True | True | True | True | None | None |
| CL11 | False | None | None | None | None | No candidate SQL in /process_query response |
| CL12 | True | False | False | False | False | None |
| CL2 | False | False | False | False | None | None |
| CL3 | False | None | None | None | None | No candidate SQL in /process_query response |
| CL4 | False | False | False | False | False | None |
| CL5 | True | False | False | False | True | None |
| CL6 | False | None | None | None | None | No candidate SQL in /process_query response |
| CL7 | False | False | False | False | None | None |
| CL8 | False | False | False | False | False | None |
| CL9 | True | True | True | True | None | None |
