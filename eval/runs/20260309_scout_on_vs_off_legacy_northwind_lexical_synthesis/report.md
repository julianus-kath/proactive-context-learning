# Scout ON vs OFF legacy on Northwind lexical-stress sets

## Experiment A: Existing `scout_limit_probe_v2` (18 prompts, L1-L6)
- ON run: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260309_113844_scout_limit_probe_v2_process_query_scout_on_r_new`
- OFF legacy run: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260309_115854_scout_limit_probe_v2_process_query_scout_off_legacy_r_new`
- Level analysis: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260309_lexical_breakdown_probe_v2_on_vs_off_legacy_analysis`

| Metric | ON | OFF legacy | Delta (ON-OFF) |
|---|---:|---:|---:|
| strict_equal_count | 3 | 6 | -3 |
| positional_set_equal_count | 4 | 7 | -3 |
| required_tables_ok_count | 5 | 12 | -7 |
| sql_exec_errors_count | 8 | 3 | 5 |

| Level | N | Δ SQL | Δ Required | Δ Strict | Δ Positional |
|---|---:|---:|---:|---:|---:|
| L1 | 3 | -1 | 0 | -1 | 0 |
| L2 | 3 | -1 | -2 | 0 | -1 |
| L3 | 3 | -1 | -2 | 0 | 0 |
| L4 | 3 | 0 | -1 | -1 | -1 |
| L5 | 3 | 0 | 0 | 0 | 0 |
| L6 | 3 | -2 | -2 | -1 | -1 |

## Experiment B: Generated `lexical_breakpoint_v1` (12 prompts, LX1-LX3)
- Dataset: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/datasets/northwind_queries_lexical_breakpoint_v1.jsonl`
- Reference SQL: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/datasets/northwind_queries_lexical_breakpoint_v1.reference_sql.json`
- ON run: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260309_121921_lexical_breakpoint_v1_process_query_scout_on_r1`
- OFF legacy run: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260309_123615_lexical_breakpoint_v1_process_query_scout_off_legacy_r1`
- Level analysis: `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260309_lexical_breakpoint_v1_analysis`

| Metric | ON | OFF legacy | Delta (ON-OFF) |
|---|---:|---:|---:|
| strict_equal_count | 1 | 2 | -1 |
| positional_set_equal_count | 2 | 3 | -1 |
| required_tables_ok_count | 4 | 7 | -3 |
| sql_exec_errors_count | 7 | 1 | 6 |

| Level | N | Δ SQL | Δ Required | Δ Strict | Δ Positional |
|---|---:|---:|---:|---:|---:|
| LX1 | 4 | 0 | -1 | 0 | 0 |
| LX2 | 4 | -2 | 0 | -1 | -1 |
| LX3 | 4 | -4 | -2 | 0 | 0 |

## Takeaway
- In both Northwind lexical-stress experiments, OFF legacy outperformed ON on strict equality and required-table coverage.
- No lexical-break point was found where OFF legacy collapses while ON remains stable.
- The opposite pattern appeared in Experiment B: ON degraded from LX2 to LX3 in SQL-generation and required-table coverage.