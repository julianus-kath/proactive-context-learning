# Async Expert Evaluation (20260309_161731_underspecified_v1_process_query_scout_on_r4)

- Reference SQL: `eval/datasets/northwind_queries_underspecified_v1.reference_sql.json`
- Total queries: `12`
- Strict equal: `2`
- Same-column set equal: `2`
- Positional set equal: `2`
- Common-column set equal: `0`
- Required table coverage: `1`
- SQL execution errors: `6`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| US_CL10_U1 | True | True | True | True | None | None |
| US_CL10_U2 | False | True | True | True | None | None |
| US_CL10_U3 | False | False | False | False | None | None |
| US_CL2_U1 | False | False | False | False | None | None |
| US_CL2_U2 | False | False | False | False | False | None |
| US_CL2_U3 | False | False | False | False | None | None |
| US_CL3_U1 | False | None | None | None | None | No candidate SQL in /process_query response |
| US_CL3_U2 | False | None | None | None | None | No candidate SQL in /process_query response |
| US_CL3_U3 | False | None | None | None | None | No candidate SQL in /process_query response |
| US_CL6_U1 | False | None | None | None | None | No candidate SQL in /process_query response |
| US_CL6_U2 | False | None | None | None | None | No candidate SQL in /process_query response |
| US_CL6_U3 | False | None | None | None | None | No candidate SQL in /process_query response |
