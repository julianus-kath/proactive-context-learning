# Async Expert Evaluation (20260309_161530_underspecified_v1_process_query_scout_off_legacy_r3)

- Reference SQL: `eval/datasets/northwind_queries_underspecified_v1.reference_sql.json`
- Total queries: `12`
- Strict equal: `1`
- Same-column set equal: `1`
- Positional set equal: `1`
- Common-column set equal: `0`
- Required table coverage: `3`
- SQL execution errors: `4`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| US_CL10_U1 | True | True | True | True | None | None |
| US_CL10_U2 | False | False | False | False | None | None |
| US_CL10_U3 | False | None | None | None | None | No candidate SQL in /process_query response |
| US_CL2_U1 | False | False | False | False | None | None |
| US_CL2_U2 | True | False | False | False | False | None |
| US_CL2_U3 | False | False | False | False | None | None |
| US_CL3_U1 | False | None | None | None | None | No candidate SQL in /process_query response |
| US_CL3_U2 | False | False | False | False | False | None |
| US_CL3_U3 | False | False | False | False | None | None |
| US_CL6_U1 | True | False | False | False | None | None |
| US_CL6_U2 | False | None | None | None | None | No candidate SQL in /process_query response |
| US_CL6_U3 | False | None | None | None | None | No candidate SQL in /process_query response |
