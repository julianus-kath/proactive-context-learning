# Cockpit MCP Table-Retrieval Comparison

- Left run: `20260311_053124_cockpit_partner_remote_mcp_scout_off_aligned_r1` (/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260311_053124_cockpit_partner_remote_mcp_scout_off_aligned_r1)
- Right run: `20260311_075958_cockpit_partner_remote_mcp_scout_off_legacy_r1` (/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260311_075958_cockpit_partner_remote_mcp_scout_off_legacy_r1)
- Query count compared: `9`

## Aggregate (left minus right)

| Metric | Left | Right | Delta |
|---|---:|---:|---:|
| mean_recall_at_5 | 0.1111 | 0.1111 | 0.0 |
| required_tables_ok_count_at_5 | 1 | 1 | 0.0 |
| required_tables_ok_rate_at_5 | 0.1111 | 0.1111 | 0.0 |
| mean_recall_at_10 | 0.1481 | 0.1111 | 0.037 |
| required_tables_ok_count_at_10 | 1 | 1 | 0.0 |
| required_tables_ok_rate_at_10 | 0.1111 | 0.1111 | 0.0 |
| mrr | 0.0554 | 0.1111 | -0.0557 |

## Per-query delta (Recall@10)

| Query | Left Recall@10 | Right Recall@10 | Delta | Required ok@10 (L/R) |
|---|---:|---:|---:|---|
| CP6 | 0.3333333333333333 | 0.0 | 0.3333 | False/False |
| CP9 | 0.0 | 0.0 | 0.0 | False/False |
| CP8 | 0.0 | 0.0 | 0.0 | False/False |
| CP7 | 1.0 | 1.0 | 0.0 | True/True |
| CP5 | 0.0 | 0.0 | 0.0 | False/False |
| CP4 | 0.0 | 0.0 | 0.0 | False/False |
| CP3 | 0.0 | 0.0 | 0.0 | False/False |
| CP2 | 0.0 | 0.0 | 0.0 | False/False |
| CP1 | 0.0 | 0.0 | 0.0 | False/False |
