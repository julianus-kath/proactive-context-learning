# Async Expert Evaluation (20260309_113844_scout_limit_probe_v2_process_query_scout_on_r_new)

- Reference SQL: `eval/datasets/northwind_queries_scout_limit_probe_v2.reference_sql.json`
- Total queries: `18`
- Strict equal: `3`
- Same-column set equal: `3`
- Positional set equal: `4`
- Common-column set equal: `1`
- Required table coverage: `5`
- SQL execution errors: `8`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| P_CL10_L1 | False | None | None | None | None | No candidate SQL in /process_query response |
| P_CL10_L2 | True | True | True | True | None | None |
| P_CL10_L3 | True | True | True | True | None | None |
| P_CL10_L4 | False | None | None | None | None | No candidate SQL in /process_query response |
| P_CL10_L5 | True | True | True | True | None | None |
| P_CL10_L6 | False | False | False | False | None | None |
| P_CL2_L1 | True | False | False | True | True | None |
| P_CL2_L2 | False | False | False | False | None | None |
| P_CL2_L3 | False | False | False | False | None | None |
| P_CL2_L4 | False | False | False | False | None | None |
| P_CL2_L5 | False | False | False | False | None | None |
| P_CL2_L6 | False | None | None | None | None | No candidate SQL in /process_query response |
| P_CL6_L1 | True | False | False | False | False | None |
| P_CL6_L2 | False | None | None | None | None | No candidate SQL in /process_query response |
| P_CL6_L3 | False | None | None | None | None | No candidate SQL in /process_query response |
| P_CL6_L4 | False | None | None | None | None | No candidate SQL in /process_query response |
| P_CL6_L5 | False | None | None | None | None | No candidate SQL in /process_query response |
| P_CL6_L6 | False | None | None | None | None | No candidate SQL in /process_query response |
