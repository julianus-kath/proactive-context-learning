# Scout ON/OFF Semantic Comparison vs Reference SQL

- ON run: `20260222_195813_northwind_ab_scout_on_clean_v2`
- OFF run: `20260222_195526_northwind_ab_scout_off_clean`

## Aggregate

| Metric | ON | OFF |
|---|---:|---:|
| Strict result equality (same columns + ordered rows) | 2/10 | 2/10 |
| Same-column multiset equality (order-insensitive) | 2/10 | 2/10 |
| Positional multiset equality (ignore aliases) | 4/10 | 4/10 |
| Common-column multiset equality | 7/10 | 6/10 |
| Contract required table coverage | 10/10 | 10/10 |
| Re-execution errors from captured SQL | 0/10 | 0/10 |

## Per Query (positional-set semantic equivalence)

| Query | ON eq | OFF eq | ON req tables | OFF req tables |
|---|---|---|---|---|
| NW1 | False | False | True | True |
| NW10 | False | False | True | True |
| NW2 | True | True | True | True |
| NW3 | False | False | True | True |
| NW4 | False | False | True | True |
| NW5 | True | True | True | True |
| NW6 | False | False | True | True |
| NW7 | False | False | True | True |
| NW8 | True | True | True | True |
| NW9 | True | True | True | True |
