# Async Expert Evaluation (20260309_115854_scout_limit_probe_v2_process_query_scout_off_legacy_r_new)

- Reference SQL: `eval/datasets/northwind_queries_scout_limit_probe_v2.reference_sql.json`
- Total queries: `18`
- Strict equal: `6`
- Same-column set equal: `6`
- Positional set equal: `7`
- Common-column set equal: `2`
- Required table coverage: `12`
- SQL execution errors: `3`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| P_CL10_L1 | False | False | False | False | None | None |
| P_CL10_L2 | True | True | True | True | None | None |
| P_CL10_L3 | True | True | True | True | None | None |
| P_CL10_L4 | True | True | True | True | None | None |
| P_CL10_L5 | True | True | True | True | None | None |
| P_CL10_L6 | True | True | True | True | None | None |
| P_CL2_L1 | True | True | True | True | True | None |
| P_CL2_L2 | True | False | False | True | True | None |
| P_CL2_L3 | True | False | False | False | None | None |
| P_CL2_L4 | False | None | None | None | None | No candidate SQL in /process_query response |
| P_CL2_L5 | False | False | False | False | None | None |
| P_CL2_L6 | False | False | False | False | None | None |
| P_CL6_L1 | True | False | False | False | None | None |
| P_CL6_L2 | True | False | False | False | None | None |
| P_CL6_L3 | True | False | False | False | False | None |
| P_CL6_L4 | False | None | None | None | None | No candidate SQL in /process_query response |
| P_CL6_L5 | False | None | None | None | None | No candidate SQL in /process_query response |
| P_CL6_L6 | True | False | False | False | None | None |
