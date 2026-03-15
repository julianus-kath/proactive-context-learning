# Async Expert Evaluation (20260301_132904_crosslingual_hard_v1_process_query_scout_off_aligned_r3)

- Reference SQL: `eval/datasets/northwind_queries_crosslingual_hard_v1.reference_sql.json`
- Total queries: `12`
- Strict equal: `1`
- Same-column set equal: `1`
- Positional set equal: `1`
- Common-column set equal: `1`
- Required table coverage: `7`
- SQL execution errors: `3`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| CL1 | True | False | False | False | False | None |
| CL10 | False | None | None | None | None | No candidate SQL in /process_query response |
| CL11 | False | None | None | None | None | No candidate SQL in /process_query response |
| CL12 | True | False | False | False | False | None |
| CL2 | True | False | False | False | False | None |
| CL3 | False | None | None | None | None | No candidate SQL in /process_query response |
| CL4 | False | False | False | False | None | None |
| CL5 | True | False | False | False | True | None |
| CL6 | True | False | False | False | False | None |
| CL7 | False | False | False | False | None | None |
| CL8 | True | False | False | False | None | None |
| CL9 | True | True | True | True | None | None |
