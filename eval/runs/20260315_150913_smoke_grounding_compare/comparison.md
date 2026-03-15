# /process_query Grounding Comparison

- Left run: `20260309_145932_underspecified_v1_process_query_scout_on_r2` (/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260309_145932_underspecified_v1_process_query_scout_on_r2)
- Right run: `20260309_145932_underspecified_v1_process_query_scout_on_r2` (/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260309_145932_underspecified_v1_process_query_scout_on_r2)

| Metric | Left | Right | Delta (Left-Right) |
|---|---:|---:|---:|
| total_queries | 12 | 12 | 0.0 |
| mean_required_table_recall | 0.24444444444444444 | 0.24444444444444444 | 0.0 |
| queries_with_all_required_tables_surfaced | 1 | 1 | 0.0 |
| required_tables_ok_rate | 0.08333333333333333 | 0.08333333333333333 | 0.0 |
| sql_present_count | 5 | 5 | 0.0 |
| sql_execution_success_count | 5 | 5 | 0.0 |
| median_latency_ms | 9871.5 | 9871.5 | 0.0 |
| policy_violations | 0 | 0 | 0.0 |
| trace_complete_count | 0 | 0 | 0.0 |

| Query | Left recall | Right recall | Delta | Left ok | Right ok | Left sql | Right sql |
|---|---:|---:|---:|---|---|---|---|
| US_CL10_U1 | 1.0 | 1.0 | 0.0 | True | True | True | True |
| US_CL10_U2 | 0.6 | 0.6 | 0.0 | False | False | True | True |
| US_CL10_U3 | 0.0 | 0.0 | 0.0 | False | False | False | False |
| US_CL2_U1 | 0.3333333333333333 | 0.3333333333333333 | 0.0 | False | False | True | True |
| US_CL2_U2 | 0.6666666666666666 | 0.6666666666666666 | 0.0 | False | False | True | True |
| US_CL2_U3 | 0.3333333333333333 | 0.3333333333333333 | 0.0 | False | False | True | True |
| US_CL3_U1 | 0.0 | 0.0 | 0.0 | False | False | False | False |
| US_CL3_U2 | 0.0 | 0.0 | 0.0 | False | False | False | False |
| US_CL3_U3 | 0.0 | 0.0 | 0.0 | False | False | False | False |
| US_CL6_U1 | 0.0 | 0.0 | 0.0 | False | False | False | False |
| US_CL6_U2 | 0.0 | 0.0 | 0.0 | False | False | False | False |
| US_CL6_U3 | 0.0 | 0.0 | 0.0 | False | False | False | False |
