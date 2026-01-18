# ADR 0026: Evaluation & Tracking System for Thesis Validation

**Date:** December 13, 2025

---

## Problem

The autonomous multi-agent reasoning system must be rigorously evaluated to validate two core hypotheses:

1. **H1 (Proof of Concept)**: The system can autonomously discover database schemas and execute strategic queries without manual configuration.
2. **H2a (Proof of Performance)**: The system produces correct and reliable results when compared to expert baselines.

### Challenges

- **Reproducibility**: Need immutable, audit-trail artifacts that capture the complete reasoning process per query.
- **Non-Intrusiveness**: Evaluation infrastructure must not interfere with production system operation or performance.
- **Replayability**: Runs must be independently scoreable post-execution, allowing hypothesis testing after data collection.
- **Scalability**: System must handle batch runs (12+ queries) with complete trace lineage captured.
- **Integration**: Evaluation must be optional and disposable—the main system works identically whether evaluation is enabled or disabled.

### Current State

The LangGraph orchestrator executes queries end-to-end but provides no structured mechanism to:
- Capture intermediate reasoning artifacts (tables selected, SQL generated, etc.)
- Store execution traces across the 5-agent pipeline
- Compare results against expert baselines
- Generate reproducible experiment records

---

## Decision

Implement a **standalone, non-intrusive Evaluation & Tracking Service** with three components:

### 1. **Evaluation Service** (FastAPI, Port 7001)

A stateless HTTP service that receives and stores immutable experiment artifacts:

```
eval/service.py
├── POST /runs                           # Register new benchmark run
├── POST /runs/{run_id}/queries/{query_id}  # Save per-query artifact
├── POST /events                         # Append trace events (optional)
├── GET /runs                            # List all runs
└── GET /runs/{run_id}                   # Retrieve run metadata + artifacts
```

**Storage**: Filesystem-backed JSON (no database required)
```
eval/runs/{timestamp}_{run_name}/
├── run_manifest.json                    # Run metadata (model, commit, env)
├── Q1.json, Q2.json, ...                # Per-query artifacts
├── results.json                         # Aggregated results
├── summary.json                         # Success metrics
├── trace_events.jsonl                   # Optional trace log
└── score.json                           # Scoring report (post-hoc)
```

### 2. **Benchmark Runner CLI** (eval/run_benchmark.py)

Executes a fixed query catalog against the LangGraph service and captures artifacts:

```bash
python -m eval.run_benchmark \
  --dataset eval/datasets/cockpit_queries.jsonl \
  --run-name northwind_v1 \
  --target http://localhost:5001 \
  --eval-service http://localhost:7001  # Optional
```

**Workflow**:
1. Load 12 strategic "cockpit-style" queries
2. For each query:
   - Send to LangGraph `/chat` endpoint with evaluation headers
   - Capture response (final answer, SQL, tables, latency)
   - Save per-query artifact
3. Generate run summary with metrics
4. Optionally register with eval service

### 3. **Evaluation Client** (eval/eval_client.py)

Non-blocking HTTP client embedded in LangGraph service for event emission:

```python
from eval.eval_client import get_eval_client

eval_client = get_eval_client()
eval_client.emit_event_sync(
    run_id="20251213_170456_northwind_v1",
    query_id="Q1",
    event_type="stage_complete",
    stage="discovery",
    data={"tables_found": ["products", "orders"]}
)
```

**Properties**:
- Non-blocking with 2s timeout
- Respects `EVAL_ENABLED` and `EVAL_TRACKING_URL` env vars
- Gracefully handles failures (doesn't break main request)
- Both sync and async methods available

### 4. **Scoring Module** (eval/scoring/score_run.py)

Post-hoc analysis of completed runs:

```bash
python -m eval.scoring.score_run eval/runs/20251213_170456_northwind_v1 --save
```

**Phase 1 Metrics**:
- Success rate (% queries completing)
- SQL execution rate (% with generated SQL)
- Non-empty results rate (% with data returned)
- Failure categorization (timeout, connection, syntax, table/column not found, permission, other)
- Average latency

**Phase 2 (Future)**:
- Expert SQL baseline comparison
- Result correctness validation
- Numeric tolerance handling

### 5. **Benchmark Dataset** (eval/datasets/cockpit_queries.jsonl)

12 strategic "cockpit" questions for Northwind database:

```jsonl
{"id":"Q1","question":"When will product 'Chai' need reordering?","tags":["inventory","procurement"]}
{"id":"Q2","question":"What is total revenue for top 3 customers in 2024?","tags":["revenue","top-customers"]}
...
```

---

## Architecture Diagram

```
┌──────────────────────────────────────┐
│         Benchmark Runner CLI         │
│  (python -m eval.run_benchmark)      │
└──────────────────────┬───────────────┘
                       │
                       │ HTTP POST /chat
                       │ Headers: X-Eval-Run-Id, X-Eval-Query-Id
                       ▼
    ┌──────────────────────────────────────┐
    │    Web UI (port 3000)                │
    └──────────────────────────────────────┘
                       │
                       │ WebSocket
                       ▼
    ┌──────────────────────────────────────┐
    │   LangGraph Service (port 5001)      │
    │  ┌────────────────────────────────┐  │
    │  │   /chat Endpoint               │  │
    │  │  1. Extract eval headers       │  │
    │  │  2. Pass through agents        │  │
    │  │  3. Emit events to eval_client │  │
    │  │  4. Save artifact (optional)   │  │
    │  └────────────────────────────────┘  │
    │          ↓         ↓         ↓        │
    │    ┌─────────┐ ┌──────┐ ┌─────────┐ │
    │    │Intent   │ │Disc. │ │SQL Gen  │ │
    │    │Parser   │ │Agent │ │ Agent   │ │
    │    └─────────┘ └──────┘ └─────────┘ │
    │          ↓         ↓         ↓        │
    │    ┌─────────────────────────────┐  │
    │    │  MCP Client (port 8000)     │  │
    │    └─────────────────────────────┘  │
    └──────────────────┬───────────────────┘
                       │
           ┌───────────┼───────────┐
           │           │           │
           │           │    ┌──────▼──────────────┐
           │           │    │ Eval Client (async) │
           │           │    │  emit_event_sync()  │
           │           │    └──────┬──────────────┘
           │           │           │ (non-blocking,
           │           │           │  2s timeout)
           │           ▼           ▼
           │    ┌──────────────────────────────┐
           │    │ Eval Service (port 7001)     │
           │    │  ┌────────────────────────┐  │
           │    │  │ POST /runs             │  │
           │    │  │ POST /events           │  │
           │    │  │ POST /queries/{id}     │  │
           │    │  │ GET /runs              │  │
           │    │  └────────────────────────┘  │
           │    └──────────────────┬───────────┘
           │                       │
           ▼                       ▼
    ┌──────────────┐      ┌────────────────────────┐
    │  MCP Server  │      │ eval/runs/{run_id}/    │
    │ (Windows)    │      │ ├─ run_manifest.json   │
    │ port 8000    │      │ ├─ Q1.json, Q2.json... │
    │              │      │ ├─ results.json        │
    │ - Northwind  │      │ ├─ summary.json        │
    │   Database   │      │ ├─ trace_events.jsonl  │
    └──────────────┘      │ └─ score.json          │
                          └────────────────────────┘
                          (Immutable JSON Artifacts)
```

---

## Implementation Details

### Module Structure

```
eval/
├── __init__.py                          # Package exports
├── service.py                           # FastAPI evaluation service
├── eval_client.py                       # Non-blocking event/artifact client
├── run_benchmark.py                     # CLI benchmark runner
├── datasets/
│   ├── __init__.py
│   └── cockpit_queries.jsonl            # 12 benchmark queries
├── scoring/
│   ├── __init__.py
│   └── score_run.py                     # Scoring & analysis
├── README.md                            # Main documentation
├── INTEGRATION_GUIDE.md                 # LangGraph integration instructions
└── CLI_REFERENCE.md                     # Command reference
```

### Data Contracts

#### Per-Query Artifact (Q1.json)

```json
{
  "query_id": "Q1",
  "question": "When will product 'Chai' need reordering?",
  "status": "success|failed",
  "final_answer_text": "Natural language response...",
  "sql_executed": ["SELECT ... FROM products"],
  "sql_generated": ["SELECT ... (intermediate)"],
  "tables_used": ["products", "orders", "order_details"],
  "result_preview": [{"product_id": 1, ...}],
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

#### Run Manifest (run_manifest.json)

```json
{
  "run_id": "20251213_170456_northwind_v1",
  "run_name": "northwind_v1",
  "timestamp": "2025-12-13T17:04:56Z",
  "git_commit": "abc123def456...",
  "dataset_path": "eval/datasets/cockpit_queries.jsonl",
  "mcp_server_url": "http://localhost:8000",
  "model": "gpt-4",
  "environment": {
    "python_version": "3.11.5",
    "machine": "MacBook-Pro",
    "platform": "darwin"
  },
  "total_queries": 12,
  "completed_queries": 11,
  "failed_queries": 1
}
```

#### Score Report (score.json, generated post-hoc)

```json
{
  "run_id": "20251213_170456_northwind_v1",
  "metrics": {
    "total_queries": 12,
    "successful_queries": 11,
    "failed_queries": 1,
    "success_rate": "91.7%",
    "sql_executed_rate": "100.0%",
    "non_empty_results_rate": "91.7%",
    "avg_latency_ms": 1456.23
  },
  "failure_analysis": {
    "timeout": [],
    "connection_error": [],
    "sql_syntax_error": [],
    "table_not_found": [],
    "column_not_found": [],
    "permission_denied": [],
    "other": ["Q5"]
  },
  "per_query_status": {
    "Q1": {"status": "success", "latency_ms": 1234, "row_count": 42},
    "Q5": {"status": "failed", "latency_ms": 5000, "error": "..."}
  }
}
```

---

## Integration with LangGraph Service

The `/chat` endpoint in `chatbot_ui/langgraph_service.py` should:

### 1. Extract Evaluation Headers

```python
@app.post("/chat")
async def chat(
    request: QueryRequest,
    x_eval_run_id: Optional[str] = Header(None),
    x_eval_query_id: Optional[str] = Header(None),
):
    eval_run_id = x_eval_run_id or str(uuid.uuid4())
    eval_query_id = x_eval_query_id or "standalone"
    # ... pass through state ...
```

### 2. Initialize Evaluation Client

```python
from eval.eval_client import get_eval_client

eval_client = get_eval_client()  # Singleton, respects env vars
```

### 3. Emit Trace Events (Optional)

At key pipeline stages:

```python
# Intent parsing stage
eval_client.emit_event_sync(eval_run_id, eval_query_id, "stage_start", 
                           stage="intent_parsing")
intent = await parse_intent(user_input)
eval_client.emit_event_sync(eval_run_id, eval_query_id, "stage_complete",
                           stage="intent_parsing", data={"intent": intent})

# Discovery stage
eval_client.emit_event_sync(eval_run_id, eval_query_id, "stage_start",
                           stage="discovery")
tables = await discover_tables(intent)
eval_client.emit_event_sync(eval_run_id, eval_query_id, "stage_complete",
                           stage="discovery", data={"tables_found": tables})

# ... continue for SQL generation, execution, answer formatting ...
```

### 4. Save Final Artifact (Optional)

```python
artifact = {
    "query_id": eval_query_id,
    "question": request.user_input,
    "status": "success",
    "final_answer_text": result.get("final_response"),
    "sql_executed": [result.get("exec_result", {}).get("sql_query", "")],
    "tables_used": result.get("exec_result", {}).get("tables_used", []),
    "row_count": len(result.get("exec_result", {}).get("rows", [])),
    "latency_ms_total": int((time.time() - start_time) * 1000),
}
eval_client.save_query_artifact_sync(eval_run_id, eval_query_id, artifact)
```

**Note**: These integrations are **completely optional**. The system works identically with or without them.

---

## Operational Flow: Starting Services

### Option 1: All Services (Recommended for Evaluation)

**Terminal 1 - MCP Server**:
```bash
cd /path/to/code
python mcp_server/server.py
# Output: Server running on port 8000
```

**Terminal 2 - Evaluation Service**:
```bash
cd /path/to/code
python -m eval.service
# Output: Uvicorn running on http://127.0.0.1:7001
```

**Terminal 3 - LangGraph Service**:
```bash
cd /path/to/code
python -m chatbot_ui.langgraph_service
# Output: FastAPI running on http://localhost:5001
```

**Terminal 4 - Web UI** (optional):
```bash
cd /path/to/code/chatbot_ui
python web_app.py
# Output: Running on http://localhost:3000
```

**Terminal 5 - Benchmark Runner**:
```bash
cd /path/to/code
python -m eval.run_benchmark \
  --dataset eval/datasets/cockpit_queries.jsonl \
  --run-name northwind_v1 \
  --target http://localhost:5001 \
  --eval-service http://localhost:7001
```

### Option 2: Production (No Evaluation)

Disable evaluation with environment variable:

```bash
EVAL_ENABLED=0 python -m chatbot_ui.langgraph_service
```

Or set empty tracking URL:

```bash
EVAL_TRACKING_URL= python -m eval.run_benchmark ...
```

### Option 3: Via Mac Startup Script

Update `start_all_services_mac.sh` to optionally start eval service:

```bash
# Add to startup script:
if [ "$ENABLE_EVAL" = "1" ]; then
    echo -e "${YELLOW}🚀 Starting Evaluation Service (port 7001)...${NC}"
    nohup python -m eval.service > "$LOG_DIR/eval_service.log" 2>&1 &
    EVAL_PID=$!
    echo -e "${GREEN}✅ Evaluation Service started (PID: $EVAL_PID)${NC}"
    
    # Wait for service readiness
    wait_for_service "http://localhost:7001/health" "Evaluation Service"
fi
```

Then run:

```bash
ENABLE_EVAL=1 ./start_all_services_mac.sh
```

---

## Environment Configuration

### .env Variables (Already Added)

```bash
# Enable evaluation system
EVAL_ENABLED=1

# URL of evaluation service (leave empty to disable service integration)
EVAL_TRACKING_URL=http://localhost:7001
```

### Behavior by Configuration

| EVAL_ENABLED | EVAL_TRACKING_URL | Behavior |
|:---:|:---:|---|
| `1` | `http://localhost:7001` | Full tracking: events + artifacts sent to service |
| `1` | *(empty)* | Local-only: artifacts saved to filesystem only |
| `0` | *(any)* | Disabled: no evaluation overhead at all |

---

## Use Cases

### H1 Validation (Proof of Concept)

**Objective**: Demonstrate autonomous schema discovery and query execution

**Evidence captured**:
- `tables_used` field: Shows which tables were discovered
- `sql_executed` field: Shows generated SQL was executed
- Success rate > 0%: Proves end-to-end capability

**Artifact review**:
```bash
cat eval/runs/20251213_170456_northwind_v1/Q1.json | jq '.tables_used, .sql_executed'
```

### H2a Validation (Proof of Performance)

**Objective**: Demonstrate correct and reliable results vs expert baselines

**Evidence captured**:
- `success_rate`: % of queries completing
- `non_empty_results_rate`: % returning data
- `final_answer_text`: Natural language summaries reviewable by experts
- Per-query latency: Performance metrics

**Artifact review**:
```bash
cat eval/runs/20251213_170456_northwind_v1/score.json | jq '.metrics'
```

### Debugging Failed Queries

**Example**: Q5 failed

```bash
# View error and trace
cat eval/runs/20251213_170456_northwind_v1/Q5.json | jq '{error, latency_ms_total}'

# View trace events for that query
cat eval/runs/20251213_170456_northwind_v1/trace_events.jsonl | jq 'select(.query_id == "Q5")'
```

### Comparative Analysis (Multiple Runs)

```bash
# Score all runs
for run_dir in eval/runs/*/; do
  python -m eval.scoring.score_run "$run_dir" --save
done

# Compare metrics
echo "=== Run 1 ===" && jq '.metrics.success_rate' eval/runs/run1/score.json
echo "=== Run 2 ===" && jq '.metrics.success_rate' eval/runs/run2/score.json
```

---

## Consequences

### Positive

✅ **Reproducibility**: All runs stored as immutable JSON; can replay scoring indefinitely  
✅ **Auditability**: Complete trace lineage for each query (tables, SQL, results)  
✅ **Non-Intrusiveness**: Evaluation is entirely external; zero impact if disabled  
✅ **Thesis-Ready**: Artifacts in standardized format suitable for defense references  
✅ **Extensibility**: Phase 2 can add expert SQL baselines without changing Phase 1 data  
✅ **Scalability**: Filesystem storage sufficient; can migrate to DB later if needed  

### Trade-offs

⚠️ **Operational Overhead**: Three additional services (eval, MCP, LangGraph) to manage  
⚠️ **Disk Usage**: Complete artifact storage (~50 KB/run × 12 queries); manageable for thesis  
⚠️ **Latency**: ~2s timeout on eval client; negligible with non-blocking calls  
⚠️ **Configuration**: Environment variables control behavior; potential for operator error  

### Mitigations

- **Startup Script**: Optionally automates service startup via `start_all_services_mac.sh`
- **Health Checks**: Each service has `/health` endpoint for monitoring
- **Graceful Degradation**: System works identically with `EVAL_ENABLED=0`
- **Fallback Storage**: Artifacts saved locally even if eval service unavailable

---

## Success Criteria

✅ Single-command benchmark execution  
✅ 12 queries → 12 immutable artifacts + summary  
✅ Scoring metrics computed post-hoc  
✅ Complete documentation (README, integration guide, CLI reference)  
✅ Optional integration (zero impact when disabled)  
✅ Thesis citations cite immutable JSON artifacts  

---

## Testing & Validation

### Unit Tests

```bash
# Test eval client non-blocking behavior
python -m pytest tests/test_eval_client.py -v

# Test scoring module
python -m pytest tests/test_eval_scoring.py -v
```

### Integration Test

```bash
# 1. Start all services in background
python -m eval.service &
python -m eval.run_benchmark --run-name integration_test --eval-service http://localhost:7001

# 2. Verify artifacts
ls -la eval/runs/
cat eval/runs/*/summary.json | jq .

# 3. Score and verify metrics
python -m eval.scoring.score_run eval/runs/* --save
cat eval/runs/*/score.json | jq '.metrics'
```

### Manual Smoke Test

```bash
# Check service health
curl http://localhost:7001/health
# Response: {"status": "ok", "service": "evaluation"}

# List runs
curl http://localhost:7001/runs
# Response: {"runs": [...]}
```

---

## Future Work

### Phase 2: Expert Baseline Comparison

Add expert SQL ground truth:

```bash
# Create eval/baselines/northwind_expert.jsonl
{"id":"Q1","expert_sql":"SELECT...","expected_rows":42,"tolerance":0}
```

Extend scoring:

```python
from eval.scoring.score_run import compare_with_baseline

score = compare_with_baseline(
    run_dir=Path("eval/runs/20251213_170456_northwind_v1"),
    expert_baselines_path=Path("eval/baselines/northwind_expert.jsonl"),
    numeric_tolerance=0.01,  # 1% tolerance for aggregates
)
```

### Phase 3: Continuous Integration

Integrate with CI/CD:

```yaml
# .github/workflows/eval.yml
- name: Run Benchmark
  run: python -m eval.run_benchmark --run-name ci_run

- name: Score Results
  run: |
    for run in eval/runs/*/; do
      python -m eval.scoring.score_run "$run" --save
    done

- name: Compare Against Baseline
  run: python scripts/compare_runs.py
```

---

## References

- `eval/README.md`: Main evaluation system documentation
- `eval/INTEGRATION_GUIDE.md`: Step-by-step LangGraph integration instructions
- `eval/CLI_REFERENCE.md`: Complete command reference and examples
- `EVAL_IMPLEMENTATION_SUMMARY.md`: High-level overview and architecture
- `start_all_services_mac.sh`: Startup script with optional eval service integration

---

## Appendix: Complete Quick Start

```bash
# Terminal 1: MCP Server
python mcp_server/server.py

# Terminal 2: Eval Service
python -m eval.service

# Terminal 3: LangGraph Service
python -m chatbot_ui.langgraph_service

# Terminal 4: Benchmark Runner
python -m eval.run_benchmark \
  --dataset eval/datasets/cockpit_queries.jsonl \
  --run-name northwind_baseline \
  --target http://localhost:5001 \
  --eval-service http://localhost:7001

# When benchmark completes:
python -m eval.scoring.score_run eval/runs/20251213_170456_northwind_baseline --save

# View results
cat eval/runs/*/score.json | jq '.metrics'
```

---

**Approval**: Ready for thesis implementation  
**Last Updated**: December 13, 2025
