# Lexical Breakdown Analysis (Scout ON vs OFF legacy)

ON run: 20260309_113844_scout_limit_probe_v2_process_query_scout_on_r_new
OFF run: 20260309_115854_scout_limit_probe_v2_process_query_scout_off_legacy_r_new

## Overall expert summary

| Metric | ON | OFF legacy | Delta (ON-OFF) |
|---|---:|---:|---:|
| strict_equal_count | 3 | 6 | -3 |
| positional_set_equal_count | 4 | 7 | -3 |
| required_tables_ok_count | 5 | 12 | -7 |
| sql_exec_errors_count | 8 | 3 | 5 |

## By lexical level

| Level | N | ON SQL | OFF SQL | Δ SQL | ON Required | OFF Required | Δ Required | ON Strict | OFF Strict | Δ Strict | ON Positional | OFF Positional | Δ Positional |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| L1 | 3 | 2 | 3 | -1 | 2 | 2 | 0 | 0 | 1 | -1 | 1 | 1 | 0 |
| L2 | 3 | 2 | 3 | -1 | 1 | 3 | -2 | 1 | 1 | 0 | 1 | 2 | -1 |
| L3 | 3 | 2 | 3 | -1 | 1 | 3 | -2 | 1 | 1 | 0 | 1 | 1 | 0 |
| L4 | 3 | 1 | 1 | 0 | 0 | 1 | -1 | 0 | 1 | -1 | 0 | 1 | -1 |
| L5 | 3 | 2 | 2 | 0 | 1 | 1 | 0 | 1 | 1 | 0 | 1 | 1 | 0 |
| L6 | 3 | 1 | 3 | -2 | 0 | 2 | -2 | 0 | 1 | -1 | 0 | 1 | -1 |

## Query-level deltas (selected)

### L1
- P_CL10_L1: required ON/OFF=False/False, strict ON/OFF=None/False
- P_CL2_L1: required ON/OFF=True/True, strict ON/OFF=False/True

### L2
- P_CL2_L2: required ON/OFF=False/True, strict ON/OFF=False/False
- P_CL6_L2: required ON/OFF=False/True, strict ON/OFF=None/False

### L3
- P_CL2_L3: required ON/OFF=False/True, strict ON/OFF=False/False
- P_CL6_L3: required ON/OFF=False/True, strict ON/OFF=None/False

### L4
- P_CL10_L4: required ON/OFF=False/True, strict ON/OFF=None/True
- P_CL2_L4: required ON/OFF=False/False, strict ON/OFF=False/None

### L5

### L6
- P_CL10_L6: required ON/OFF=False/True, strict ON/OFF=False/True
- P_CL2_L6: required ON/OFF=False/False, strict ON/OFF=None/False
- P_CL6_L6: required ON/OFF=False/True, strict ON/OFF=None/False