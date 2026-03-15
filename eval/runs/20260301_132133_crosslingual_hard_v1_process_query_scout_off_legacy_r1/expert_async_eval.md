# Async Expert Evaluation (20260301_132133_crosslingual_hard_v1_process_query_scout_off_legacy_r1)

- Reference SQL: `eval/datasets/northwind_queries_crosslingual_hard_v1.reference_sql.json`
- Total queries: `12`
- Strict equal: `3`
- Same-column set equal: `3`
- Positional set equal: `3`
- Common-column set equal: `2`
- Required table coverage: `9`
- SQL execution errors: `0`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| CL1 | True | False | False | False | False | None |
| CL10 | True | True | True | True | None | None |
| CL11 | False | False | False | False | False | None |
| CL12 | True | False | False | False | False | None |
| CL2 | True | True | True | True | True | None |
| CL3 | False | False | False | False | None | None |
| CL4 | True | False | False | False | False | None |
| CL5 | True | False | False | False | True | None |
| CL6 | True | False | False | False | None | None |
| CL7 | False | False | False | False | None | None |
| CL8 | True | False | False | False | False | None |
| CL9 | True | True | True | True | None | None |
