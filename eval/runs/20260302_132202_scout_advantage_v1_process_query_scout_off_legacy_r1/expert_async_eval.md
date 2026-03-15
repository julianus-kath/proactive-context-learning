# Async Expert Evaluation (20260302_132202_scout_advantage_v1_process_query_scout_off_legacy_r1)

- Reference SQL: `eval/datasets/northwind_queries_scout_advantage_v1.reference_sql.json`
- Total queries: `9`
- Strict equal: `2`
- Same-column set equal: `2`
- Positional set equal: `2`
- Common-column set equal: `0`
- Required table coverage: `5`
- SQL execution errors: `0`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| SA1 | True | False | False | False | False | None |
| SA2 | True | False | False | False | False | None |
| SA3 | False | False | False | False | False | None |
| SA4 | True | False | False | False | None | None |
| SA5 | True | False | False | False | False | None |
| SA6 | True | False | False | False | False | None |
| SA7 | False | True | True | True | None | None |
| SA8 | False | True | True | True | None | None |
| SA9 | False | False | False | False | None | None |
