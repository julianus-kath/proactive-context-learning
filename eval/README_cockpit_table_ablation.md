# Cockpit Table-Correctness Ablation Pipeline

This pipeline compares Scout ON vs Scout OFF variants on production-style cockpit questions
using partner-provided required-table labels (without requiring reference SQL).

## One-command orchestrator

Use:

```bash
python -m eval.run_cockpit_table_ablation \
  --dataset eval/datasets/cockpit_partner_queries_v1.jsonl \
  --table-labels eval/datasets/cockpit_partner_table_labels_v1.json \
  --replicates 1
```

Dry-run preflight (no API calls):

```bash
python -m eval.run_cockpit_table_ablation --dry-run --replicates 1
```

## Inputs

- Query set:
  - `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/datasets/cockpit_partner_queries_v1.jsonl`
- Table labels:
  - `/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/eval/datasets/cockpit_partner_table_labels_v1.json`

## Step 1: Run /process_query in each mode

Use the existing runner with `--evaluate-expert` omitted.

Scout ON:

```bash
python -m eval.start_northwind_process_query \
  --dataset eval/datasets/cockpit_partner_queries_v1.jsonl \
  --run-name cockpit_partner_v1_process_query_scout_on_r1 \
  --mode-label scout_on \
  --target http://localhost:5001 \
  --api-key supersecretapikey \
  --mcp-url http://localhost:8000 \
  --mcp-api-key supersecretapikey \
  --concurrency 1
```

Scout OFF aligned:

```bash
export SCOUT_DISABLE=true
export SCOUT_OFF_CONTROL_MODE=aligned_table_ranker
python -m eval.start_northwind_process_query \
  --dataset eval/datasets/cockpit_partner_queries_v1.jsonl \
  --run-name cockpit_partner_v1_process_query_scout_off_aligned_r1 \
  --mode-label scout_off_aligned \
  --target http://localhost:5001 \
  --api-key supersecretapikey \
  --mcp-url http://localhost:8000 \
  --mcp-api-key supersecretapikey \
  --concurrency 1
```

Scout OFF legacy (lexical):

```bash
export SCOUT_DISABLE=true
export SCOUT_OFF_CONTROL_MODE=legacy_lexical_schema_linking
python -m eval.start_northwind_process_query \
  --dataset eval/datasets/cockpit_partner_queries_v1.jsonl \
  --run-name cockpit_partner_v1_process_query_scout_off_legacy_r1 \
  --mode-label scout_off_legacy \
  --target http://localhost:5001 \
  --api-key supersecretapikey \
  --mcp-url http://localhost:8000 \
  --mcp-api-key supersecretapikey \
  --concurrency 1
```

## Step 2: Evaluate each run against table labels

```bash
python -m eval.evaluate_process_query_table_labels \
  --run-dir eval/runs/<RUN_ID_DIR> \
  --table-labels eval/datasets/cockpit_partner_table_labels_v1.json
```

Outputs inside each run dir:
- `table_label_eval.json`
- `table_label_eval.md`
- `table_label_manual_review_template.json`

## Step 3: Compare modes

Example ON vs OFF legacy:

```bash
python -m eval.compare_process_query_table_label_runs \
  --on-run-dir eval/runs/<ON_RUN_ID_DIR> \
  --off-run-dir eval/runs/<OFF_RUN_ID_DIR> \
  --out-name cockpit_partner_v1_on_vs_off_legacy_table_eval
```

Outputs:
- `eval/runs/<timestamp>_cockpit_partner_v1_on_vs_off_legacy_table_eval/comparison.json`
- `eval/runs/<timestamp>_cockpit_partner_v1_on_vs_off_legacy_table_eval/comparison.md`

## Interpretation note

This evaluation supports table-grounding and retrieval-path analysis.
It does not establish end-to-end semantic correctness of final answers without SQL/result-set ground truth.

## MCP-only fallback (when /process_query is unavailable)

If only the MCP server is reachable (for example, `/health` and `/mcp` on port 8000, but no agent `/process_query` port),
use the retrieval-only table evaluation below.

Run one mode snapshot:

```bash
python -m eval.run_cockpit_mcp_table_retrieval \
  --mcp-url http://<HOST>:8000 \
  --mcp-api-key supersecretapikey \
  --expect-health-backend ScoutRunner \
  --expect-search-source scout_runner_catalog \
  --require-aligned-fields \
  --mode-label scout_on \
  --run-name cockpit_partner_remote_mcp_scout_on_r1
```

OFF aligned mode (after MCP restart with Scout disabled + aligned ranker):

```bash
python -m eval.run_cockpit_mcp_table_retrieval \
  --mcp-url http://<HOST>:8000 \
  --mcp-api-key supersecretapikey \
  --expect-health-backend SchemaCatalog \
  --expect-off-control-mode aligned_table_ranker \
  --expect-search-source schema_catalog \
  --require-aligned-fields \
  --mode-label scout_off_aligned \
  --run-name cockpit_partner_remote_mcp_scout_off_aligned_r1
```

OFF legacy mode (after MCP restart with Scout disabled + lexical ranker):

```bash
python -m eval.run_cockpit_mcp_table_retrieval \
  --mcp-url http://<HOST>:8000 \
  --mcp-api-key supersecretapikey \
  --expect-health-backend SchemaCatalog \
  --expect-off-control-mode legacy_lexical_schema_linking \
  --expect-search-source schema_catalog \
  --require-aligned-fields \
  --mode-label scout_off_legacy \
  --run-name cockpit_partner_remote_mcp_scout_off_legacy_r1
```

Check partner labels against live catalog names:

```bash
python -m eval.check_partner_table_labels_against_catalog \
  --mcp-url http://<HOST>:8000 \
  --mcp-api-key supersecretapikey \
  --out-name cockpit_partner_label_catalog_check_remote_r1
```

After restarting the remote MCP server in another mode, run again and compare:

```bash
python -m eval.compare_cockpit_mcp_table_retrieval_runs \
  --left-run-dir eval/runs/<RUN_DIR_A> \
  --right-run-dir eval/runs/<RUN_DIR_B> \
  --out-name cockpit_partner_mcp_retrieval_a_vs_b
```

This MCP-only path evaluates retrieval/table coverage only.
It does not measure final SQL generation quality because `/process_query` is not part of the path.

If this fails with missing aligned fields, run the capability probe:

```bash
python -m eval.probe_mcp_search_capabilities \
  --mcp-url http://<HOST>:8000 \
  --mcp-api-key supersecretapikey
```
