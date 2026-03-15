# Async Expert Evaluation (20260309_121921_lexical_breakpoint_v1_process_query_scout_on_r1)

- Reference SQL: `eval/datasets/northwind_queries_lexical_breakpoint_v1.reference_sql.json`
- Total queries: `12`
- Strict equal: `1`
- Same-column set equal: `1`
- Positional set equal: `2`
- Common-column set equal: `0`
- Required table coverage: `4`
- SQL execution errors: `7`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| LB_CL10_LX1 | True | True | True | True | None | None |
| LB_CL10_LX2 | False | None | None | None | None | No candidate SQL in /process_query response |
| LB_CL10_LX3 | False | None | None | None | None | No candidate SQL in /process_query response |
| LB_CL2_LX1 | False | False | False | True | None | None |
| LB_CL2_LX2 | True | False | False | False | False | None |
| LB_CL2_LX3 | False | None | None | None | None | No candidate SQL in /process_query response |
| LB_CL3_LX1 | False | None | None | None | None | No candidate SQL in /process_query response |
| LB_CL3_LX2 | False | None | None | None | None | No candidate SQL in /process_query response |
| LB_CL3_LX3 | False | None | None | None | None | No candidate SQL in /process_query response |
| LB_CL6_LX1 | True | False | False | False | False | None |
| LB_CL6_LX2 | True | False | False | False | None | None |
| LB_CL6_LX3 | False | None | None | None | None | No candidate SQL in /process_query response |
