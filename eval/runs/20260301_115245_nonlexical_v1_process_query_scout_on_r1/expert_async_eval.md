# Async Expert Evaluation (20260301_115245_nonlexical_v1_process_query_scout_on_r1)

- Reference SQL: `eval/datasets/northwind_queries_nonlexical_v1.reference_sql.json`
- Total queries: `20`
- Strict equal: `1`
- Same-column set equal: `1`
- Positional set equal: `1`
- Common-column set equal: `4`
- Required table coverage: `10`
- SQL execution errors: `2`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| NL1 | False | False | False | False | False | None |
| NL10 | True | False | False | False | True | None |
| NL11 | True | False | False | False | False | None |
| NL12 | True | False | False | False | False | None |
| NL13 | False | None | None | None | None | No candidate SQL in /process_query response |
| NL14 | True | False | False | False | False | None |
| NL15 | False | False | False | False | None | None |
| NL16 | True | True | True | True | None | None |
| NL17 | False | False | False | False | None | None |
| NL18 | False | False | False | False | True | None |
| NL19 | False | False | False | False | False | None |
| NL2 | False | False | False | False | False | None |
| NL20 | False | None | None | None | None | No candidate SQL in /process_query response |
| NL3 | True | False | False | False | True | None |
| NL4 | True | False | False | False | None | None |
| NL5 | True | False | False | False | True | None |
| NL6 | True | False | False | False | False | None |
| NL7 | False | False | False | False | False | None |
| NL8 | True | False | False | False | None | None |
| NL9 | False | False | False | False | False | None |
