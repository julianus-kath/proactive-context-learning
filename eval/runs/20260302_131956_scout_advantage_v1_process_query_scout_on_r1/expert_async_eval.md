# Async Expert Evaluation (20260302_131956_scout_advantage_v1_process_query_scout_on_r1)

- Reference SQL: `eval/datasets/northwind_queries_scout_advantage_v1.reference_sql.json`
- Total queries: `9`
- Strict equal: `1`
- Same-column set equal: `1`
- Positional set equal: `1`
- Common-column set equal: `0`
- Required table coverage: `3`
- SQL execution errors: `4`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| SA1 | False | None | None | None | None | No candidate SQL in /process_query response |
| SA2 | True | False | False | False | False | None |
| SA3 | False | False | False | False | False | None |
| SA4 | False | None | None | None | None | No candidate SQL in /process_query response |
| SA5 | True | False | False | False | False | None |
| SA6 | False | None | None | None | None | No candidate SQL in /process_query response |
| SA7 | False | None | None | None | None | No candidate SQL in /process_query response |
| SA8 | True | True | True | True | None | None |
| SA9 | False | False | False | False | None | None |
