# Async Expert Evaluation (20260301_122737_nonlexical_v1_process_query_scout_on_r2)

- Reference SQL: `eval/datasets/northwind_queries_nonlexical_v1.reference_sql.json`
- Total queries: `20`
- Strict equal: `1`
- Same-column set equal: `1`
- Positional set equal: `1`
- Common-column set equal: `1`
- Required table coverage: `9`
- SQL execution errors: `4`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| NL1 | False | False | False | False | False | None |
| NL10 | True | False | False | False | True | None |
| NL11 | True | False | False | False | False | None |
| NL12 | True | False | False | False | False | None |
| NL13 | False | None | None | None | None | No candidate SQL in /process_query response |
| NL14 | True | False | False | False | False | None |
| NL15 | False | False | False | False | None | None |
| NL16 | False | True | True | True | None | None |
| NL17 | False | False | False | False | None | None |
| NL18 | False | False | False | False | None | None |
| NL19 | False | None | None | None | None | No candidate SQL in /process_query response |
| NL2 | False | False | False | False | False | None |
| NL20 | False | None | None | None | None | No candidate SQL in /process_query response |
| NL3 | False | None | None | None | None | No candidate SQL in /process_query response |
| NL4 | True | False | False | False | None | None |
| NL5 | True | False | False | False | False | None |
| NL6 | True | False | False | False | False | None |
| NL7 | False | False | False | False | False | None |
| NL8 | True | False | False | False | None | None |
| NL9 | True | False | False | False | False | None |
