# /process_query Table-Label ON vs OFF Comparison

- ON run: `20260309_145932_underspecified_v1_process_query_scout_on_r2` (/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260309_145932_underspecified_v1_process_query_scout_on_r2)
- OFF run: `20260309_150238_underspecified_v1_process_query_scout_off_legacy_r2` (/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260309_150238_underspecified_v1_process_query_scout_off_legacy_r2)
- ON scout mode: `ScoutRunner` active=`True`
- OFF scout mode: `SchemaCatalog` active=`False`

| Metric | ON | OFF | Delta (ON-OFF) |
|---|---:|---:|---:|
| responses_found_count | 12 | 12 | 0.0 |
| responses_found_rate | 1.0 | 1.0 | 0.0 |
| sql_present_count | 5 | 8 | -3.0 |
| sql_present_rate | 0.4166666666666667 | 0.6666666666666666 | -0.24999999999999994 |
| required_tables_ok_count | 1 | 3 | -2.0 |
| required_tables_ok_rate_all_queries | 0.08333333333333333 | 0.25 | -0.16666666666666669 |
| required_tables_ok_rate_labeled_queries | 0.08333333333333333 | 0.25 | -0.16666666666666669 |
| mean_required_table_recall | 0.24444444444444444 | 0.4777777777777778 | -0.23333333333333336 |
| median_required_table_recall | 0.0 | 0.5 | -0.5 |

| Query | ON required ok | OFF required ok | ON recall | OFF recall | ON sql | OFF sql |
|---|---|---|---:|---:|---|---|
| US_CL10_U1 | True | False | 1.000 | 0.800 | True | True |
| US_CL10_U2 | False | False | 0.600 | 0.600 | True | True |
| US_CL10_U3 | False | True | 0.000 | 1.000 | False | True |
| US_CL2_U1 | False | False | 0.333 | 0.000 | True | False |
| US_CL2_U2 | False | True | 0.667 | 1.000 | True | True |
| US_CL2_U3 | False | False | 0.333 | 0.333 | True | True |
| US_CL3_U1 | False | False | 0.000 | 0.000 | False | False |
| US_CL3_U2 | False | False | 0.000 | 0.500 | False | True |
| US_CL3_U3 | False | False | 0.000 | 0.500 | False | True |
| US_CL6_U1 | False | True | 0.000 | 1.000 | False | True |
| US_CL6_U2 | False | False | 0.000 | 0.000 | False | False |
| US_CL6_U3 | False | False | 0.000 | 0.000 | False | False |
