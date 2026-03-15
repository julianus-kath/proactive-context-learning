# Cockpit MCP Table-Retrieval Comparison

- Left run: `20260310_111456_cockpit_partner_remote_mcp_scout_on_r1` (/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260310_111456_cockpit_partner_remote_mcp_scout_on_r1)
- Right run: `20260310_111756_cockpit_partner_remote_mcp_scout_on_r2` (/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/runs/20260310_111756_cockpit_partner_remote_mcp_scout_on_r2)
- Query count compared: `9`

## Aggregate (left minus right)

| Metric | Left | Right | Delta |
|---|---:|---:|---:|
| mean_recall_at_5 | 0.1111 | 0.1111 | 0.0 |
| required_tables_ok_count_at_5 | 1 | 1 | 0.0 |
| required_tables_ok_rate_at_5 | 0.1111 | 0.1111 | 0.0 |
| mean_recall_at_10 | 0.2222 | 0.2222 | 0.0 |
| required_tables_ok_count_at_10 | 2 | 2 | 0.0 |
| required_tables_ok_rate_at_10 | 0.2222 | 0.2222 | 0.0 |
| mrr | 0.0509 | 0.0509 | 0.0 |

## Per-query delta (Recall@10)

| Query | Left Recall@10 | Right Recall@10 | Delta | Required ok@10 (L/R) |
|---|---:|---:|---:|---|
| CP9 | 0.0 | 0.0 | 0.0 | False/False |
| CP8 | 0.0 | 0.0 | 0.0 | False/False |
| CP7 | 1.0 | 1.0 | 0.0 | True/True |
| CP6 | 0.0 | 0.0 | 0.0 | False/False |
| CP5 | 0.0 | 0.0 | 0.0 | False/False |
| CP4 | 1.0 | 1.0 | 0.0 | True/True |
| CP3 | 0.0 | 0.0 | 0.0 | False/False |
| CP2 | 0.0 | 0.0 | 0.0 | False/False |
| CP1 | 0.0 | 0.0 | 0.0 | False/False |
