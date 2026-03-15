# Async Expert Evaluation (20260301_123314_nonlexical_v1_process_query_scout_off_legacy_r2)

- Reference SQL: `eval/datasets/northwind_queries_nonlexical_v1.reference_sql.json`
- Total queries: `20`
- Strict equal: `2`
- Same-column set equal: `2`
- Positional set equal: `2`
- Common-column set equal: `2`
- Required table coverage: `13`
- SQL execution errors: `0`

| Query | Required OK | Strict | Same Cols | Positional | Common Cols | Candidate SQL error |
|---|---|---|---|---|---|---|
| NL1 | True | False | False | False | False | None |
| NL10 | True | False | False | False | True | None |
| NL11 | True | False | False | False | False | None |
| NL12 | True | False | False | False | False | None |
| NL13 | False | False | False | False | None | None |
| NL14 | False | False | False | False | False | None |
| NL15 | False | False | False | False | None | None |
| NL16 | True | True | True | True | None | None |
| NL17 | False | True | True | True | None | None |
| NL18 | False | False | False | False | True | None |
| NL19 | False | False | False | False | False | None |
| NL2 | True | False | False | False | False | None |
| NL20 | True | False | False | False | False | None |
| NL3 | False | False | False | False | None | None |
| NL4 | True | False | False | False | None | None |
| NL5 | True | False | False | False | False | None |
| NL6 | True | False | False | False | False | None |
| NL7 | True | False | False | False | False | None |
| NL8 | True | False | False | False | None | None |
| NL9 | True | False | False | False | False | None |
