# Async Expert Evaluation (20260302_132546_on_edge_v1_process_query_scout_on_r1)

- Reference SQL: `eval/datasets/northwind_queries_on_edge_v1.reference_sql.json`
- Total queries: `3`
- Strict equal: `1`
- Same-column set equal: `1`
- Positional set equal: `1`
- Common-column set equal: `0`
- Required table coverage: `2`
- SQL execution errors: `0`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| OE1 | False | False | False | False | None | None |
| OE2 | True | False | False | False | False | None |
| OE3 | True | True | True | True | None | None |
