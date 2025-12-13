# Evaluation & Tracking System

A standalone, non-intrusive evaluation harness for the autonomous multi-agent reasoning system. Designed to support thesis hypothesis validation (H1: Proof of Concept, H2a: Proof of Performance).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Web UI (port 3000)                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│            LangGraph Service (port 5001)                    │
│  - Orchestrates multi-agent reasoning                       │
│  - Emits evaluation events (headers: X-Eval-Run-Id, etc.)   │
└──────────────────────────┬──────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
   │  MCP Server  │ │  Eval Client │ │  Benchmark   │
   │  (port 8000) │ │  (async)     │ │  Runner CLI  │
   └──────────────┘ └──────┬───────┘ └──────┬───────┘
                           │                │
                           └────────┬───────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │  Eval Service (port 7001)     │
                    │  - Stateless event sink       │
                    │  - Immutable artifact storage │
                    │  - JSON filesystem backend    │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │  eval/runs/<run_id>/          │
                    │  ├─ run_manifest.json         │
                    │  ├─ Q1.json, Q2.json, ...     │
                    │  ├─ trace_events.jsonl        │
                    │  ├─ results.json              │
                    │  └─ summary.json              │
                    └───────────────────────────────┘
```

## Key Features

- **Non-Intrusive**: Evaluation is entirely external; production system unaffected
- **Replayable**: Full trace artifacts stored as immutable JSON
- **Optional**: Can be disabled via environment variables
- **Auditable**: Every query generates complete lineage (SQL, tables, results, timing)
- **Thesis-Ready**: Captures all H1/H2a evidence in standardized format

## Quick Start

### 1. Start the Evaluation Service (separate process)

```bash
python -m eval.service
```

Or with custom port:

```bash
python -c "from eval.service import start_service; start_service(port=7001)"
```

Service will create `eval/runs/` directory for artifact storage.

### 2. Execute Benchmark

From the project root:

```bash
python -m eval.run_benchmark \
  --dataset eval/datasets/cockpit_queries.jsonl \
  --run-name northwind_v1 \
  --target http://localhost:5001 \
  --eval-service http://localhost:7001
```

Expected output:
```
📊 Loading benchmark dataset: eval/datasets/cockpit_queries.jsonl
✅ Loaded 12 queries
🚀 Starting run: 20251213_170456_northwind_v1
📁 Results will be saved to: eval/runs/20251213_170456_northwind_v1

[1/12] Q1: When will the product 'Chai' need to be reordered...
   ✅ Success (1234ms)

...

============================================================
📋 BENCHMARK COMPLETE
============================================================
Run ID: 20251213_170456_northwind_v1
Total Queries: 12
Successful: 11 (91.7%)
Failed: 1
Results saved to: eval/runs/20251213_170456_northwind_v1
============================================================
```

### 3. Score the Run

```bash
python -m eval.scoring.score_run eval/runs/20251213_170456_northwind_v1 --save
```

Output:
```
============================================================
Run: 20251213_170456_northwind_v1
============================================================
Total Queries: 12
Successful: 11 (91.7%)
Failed: 1
SQL Execution Rate: 100.0%
Non-Empty Results Rate: 91.7%
Avg Latency: 1456.23ms
============================================================

Failure Analysis:
  other: 1 (Q5)
```

## File Structure

### Dataset Format (cockpit_queries.jsonl)

Each line is a JSON query object:

```json
{
  "id": "Q1",
  "question": "When will the product 'Chai' need to be reordered?",
  "tags": ["inventory", "procurement"],
  "notes": "Requires trend analysis",
  "expected_tables": ["products", "orders", "order_details"]
}
```

### Run Artifacts

After each benchmark run, `eval/runs/<run_id>/` contains:

- **run_manifest.json**: Run metadata (timestamp, git commit, environment, model)
- **Q1.json, Q2.json, ...**: Per-query artifact (question, status, SQL, tables, results, latency)
- **results.json**: Aggregated results for all queries
- **summary.json**: High-level success metrics
- **trace_events.jsonl**: Complete trace of all pipeline stages
- **score.json**: Scoring report (created by `score_run.py`)

Example Q1.json:

```json
{
  "query_id": "Q1",
  "question": "When will the product 'Chai' need to be reordered?",
  "status": "success",
  "final_answer_text": "Chai will need reordering soon as stock is only 39 units...",
  "sql_executed": ["SELECT product_id FROM products WHERE product_name='Chai'..."],
  "tables_used": ["products", "orders", "order_details"],
  "result_preview": [...],
  "row_count": 42,
  "latency_ms_total": 1234,
  "latency_ms_by_stage": {
    "intent_parsing": 100,
    "discovery": 200,
    "sql_generation": 300,
    "execution": 400,
    "answer_formatting": 34
  },
  "retries": 0,
  "error": null
}
```

## Configuration

### Environment Variables

In `.env`:

```bash
# Enable evaluation system
EVAL_ENABLED=1

# Evaluation service URL (or empty to disable service integration)
EVAL_TRACKING_URL=http://localhost:7001
```

### Disabling Evaluation

To run production without evaluation:

```bash
EVAL_ENABLED=0 python -m chatbot_ui.langgraph_service
```

Or leave `EVAL_TRACKING_URL` empty for local-only (filesystem) storage:

```bash
EVAL_TRACKING_URL= python -m eval.run_benchmark ...
```

## Integration with LangGraph Service

The benchmark runner sends headers with each request:

```
X-Eval-Run-Id: 20251213_170456_northwind_v1
X-Eval-Query-Id: Q1
```

These headers should be:
1. Extracted by the LangGraph service
2. Included in the state passed through the agent pipeline
3. Used to emit trace events to the eval service (via `eval_client.emit_event()`)

See `chatbot_ui/langgraph_service.py` for instrumentation hooks.

## Scoring & Analysis

### Phase 1 Scoring (Implemented)

- **Success Rate**: % of queries completing without HTTP error
- **SQL Execution Rate**: % of successful queries with executed SQL
- **Non-Empty Results Rate**: % with row_count > 0
- **Failure Categorization**: Timeout, connection, syntax, table/column not found, permission, other

### Phase 2 Scoring (Future)

When expert SQL baselines are provided:

```python
from eval.scoring.score_run import compare_with_baseline

score = compare_with_baseline(
    run_dir=Path("eval/runs/20251213_170456_northwind_v1"),
    expert_baselines_path=Path("eval/baselines/northwind_expert.jsonl"),
    numeric_tolerance=0.01,  # 1% tolerance for numeric aggregates
)
```

## Operational Wiring

### Mac Startup Script

The `start_all_services_mac.sh` can optionally start the eval service:

```bash
# In start_all_services_mac.sh, add:
if [ "$ENABLE_EVAL" = "1" ]; then
    echo "Starting Evaluation Service..."
    nohup python -m eval.service > logs/eval_service.log 2>&1 &
    EVAL_PID=$!
fi
```

Then run:

```bash
ENABLE_EVAL=1 ./start_all_services_mac.sh
```

### Manual Multi-Service Setup

Terminal 1 (MCP Server):
```bash
python mcp_server/server.py
```

Terminal 2 (LangGraph Service):
```bash
python -m chatbot_ui.langgraph_service
```

Terminal 3 (Eval Service):
```bash
python -m eval.service
```

Terminal 4 (Benchmark):
```bash
python -m eval.run_benchmark --run-name test_run --eval-service http://localhost:7001
```

## Troubleshooting

### Eval service not saving artifacts

1. Check permissions on `eval/runs/` directory
2. Verify `EVAL_TRACKING_URL` is accessible from runner
3. Check eval service logs: `tail -f logs/eval_service.log`

### Benchmark runner fails to connect

```bash
# Test connectivity:
curl http://localhost:7001/health
curl http://localhost:5001/health
```

### Empty or missing results

1. Verify LangGraph service is returning full response objects
2. Check runner is including X-Eval-Run-Id and X-Eval-Query-Id headers
3. Verify eval_client is initialized in langgraph_service.py

## Advanced: Custom Baselines

To add expert SQL baselines for H2a validation:

```bash
# Create eval/baselines/northwind_expert.jsonl with expert solutions:
cat > eval/baselines/northwind_expert.jsonl << 'EOF'
{"id":"Q1","expert_sql":"SELECT * FROM products WHERE product_name='Chai'...", "expected_min_rows": 1}
{"id":"Q2","expert_sql":"SELECT SUM(quantity*unit_price) FROM orders...","expected_result": 12345.67}
EOF
```

Then update `scoring/score_run.py` to compare against baselines.

## Thesis Citation

This evaluation system implements the empirical validation framework for:
- **H1 (Proof of Concept)**: System autonomously discovers schema and executes strategic queries (evidenced by `sql_executed` and `tables_used`)
- **H2a (Proof of Performance)**: System produces correct and reliable results (evidenced by `success_rate`, `non_empty_results_rate`, and per-query `final_answer_text`)

All artifacts are immutable JSON and can be reviewed during thesis defense.

---

**Created**: December 2025  
**Status**: Phase 1 Complete (Basic scoring and artifact storage)  
**Next**: Phase 2 (Expert SQL baseline comparison)
