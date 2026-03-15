# Async Expert Evaluation (20260301_124351_nonlexical_v2_process_query_scout_off_aligned_r1)

- Reference SQL: `eval/datasets/northwind_queries_nonlexical_v2.reference_sql.json`
- Total queries: `20`
- Strict equal: `1`
- Same-column set equal: `1`
- Positional set equal: `1`
- Common-column set equal: `3`
- Required table coverage: `13`
- SQL execution errors: `3`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| NL1 | True | False | False | False | False | None |
| NL10 | True | False | False | False | True | None |
| NL11 | True | False | False | False | False | None |
| NL12 | True | False | False | False | False | None |
| NL13 | False | None | None | None | None | No candidate SQL in /process_query response |
| NL14 | True | False | False | False | False | None |
| NL15 | False | False | False | False | None | None |
| NL16 | True | True | True | True | None | None |
| NL17 | False | None | None | None | None | No candidate SQL in /process_query response |
| NL18 | False | False | False | False | True | None |
| NL19 | False | None | None | None | None | No candidate SQL in /process_query response |
| NL2 | False | False | False | False | False | None |
| NL20 | True | False | False | False | False | None |
| NL3 | True | False | False | False | False | None |
| NL4 | True | False | False | False | True | None |
| NL5 | True | False | False | False | False | None |
| NL6 | True | False | False | False | False | None |
| NL7 | True | False | False | False | False | None |
| NL8 | True | False | False | False | None | None |
| NL9 | False | False | False | False | False | None |
