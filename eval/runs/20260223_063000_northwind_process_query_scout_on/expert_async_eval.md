# Async Expert Evaluation (20260223_063000_northwind_process_query_scout_on)

- Reference SQL: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/datasets/northwind_queries.reference_sql.json`
- Total queries: `10`
- Strict equal: `2`
- Same-column set equal: `2`
- Positional set equal: `4`
- Common-column set equal: `8`
- Required table coverage: `8`
- SQL execution errors: `0`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| NW1 | True | False | False | False | True | None |
| NW10 | True | False | False | False | True | None |
| NW2 | True | True | True | True | True | None |
| NW3 | True | False | False | False | False | None |
| NW4 | True | False | False | False | True | None |
| NW5 | True | True | True | True | True | None |
| NW6 | True | False | False | False | True | None |
| NW7 | False | False | False | False | None | None |
| NW8 | False | False | False | True | True | None |
| NW9 | True | False | False | True | True | None |
