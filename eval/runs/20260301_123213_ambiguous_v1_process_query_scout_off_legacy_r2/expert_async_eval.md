# Async Expert Evaluation (20260301_123213_ambiguous_v1_process_query_scout_off_legacy_r2)

- Reference SQL: `eval/datasets/northwind_queries_ambiguous_v1.reference_sql.json`
- Total queries: `10`
- Strict equal: `0`
- Same-column set equal: `0`
- Positional set equal: `1`
- Common-column set equal: `2`
- Required table coverage: `8`
- SQL execution errors: `0`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| NW1 | True | False | False | False | False | None |
| NW10 | True | False | False | False | False | None |
| NW2 | True | False | False | False | False | None |
| NW3 | False | False | False | False | False | None |
| NW4 | False | False | False | False | None | None |
| NW5 | True | False | False | False | False | None |
| NW6 | True | False | False | False | True | None |
| NW7 | True | False | False | False | None | None |
| NW8 | True | False | False | False | True | None |
| NW9 | True | False | False | True | None | None |
