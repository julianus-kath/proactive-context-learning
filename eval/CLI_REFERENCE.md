# Evaluation System - CLI Reference

Quick command reference for running benchmarks and scoring runs.

## Service Management

### Start Evaluation Service

```bash
# Default (port 7001)
python -m eval.service

# Custom port
python -c "from eval.service import start_service; start_service(port=8001)"

# With custom logging
LOG_LEVEL=DEBUG python -m eval.service
```

### Check Service Health

```bash
curl http://localhost:7001/health
# Response: {"status": "ok", "service": "evaluation"}
```

### List All Runs

```bash
curl http://localhost:7001/runs
```

### Retrieve Specific Run

```bash
curl http://localhost:7001/runs/{run_id}
```

## Benchmark Execution

### Basic Benchmark

```bash
python -m eval.run_benchmark
```

This runs with defaults:
- Dataset: `eval/datasets/cockpit_queries.jsonl`
- Run name: `benchmark_run`
- Target: `http://localhost:5001`
- Eval service: (disabled)

### Full Options

```bash
python -m eval.run_benchmark \
  --dataset eval/datasets/cockpit_queries.jsonl \
  --run-name northwind_v1 \
  --target http://localhost:5001 \
  --eval-service http://localhost:7001
```

### With Environment Variables

```bash
# Disable evaluation tracking
EVAL_ENABLED=0 python -m eval.run_benchmark --run-name test_no_eval

# Change eval service URL
EVAL_TRACKING_URL=http://remote.eval.service:7001 \
  python -m eval.run_benchmark --run-name remote_eval
```

### Different Target (e.g., staging)

```bash
python -m eval.run_benchmark \
  --target http://staging.system:5001 \
  --run-name staging_test_v1
```

### Benchmark Without Eval Service (filesystem only)

```bash
python -m eval.run_benchmark \
  --run-name local_only
# Results saved to: eval/runs/20251213_170456_local_only/
```

## Scoring & Analysis

### Score a Run

```bash
python -m eval.scoring.score_run eval/runs/20251213_170456_northwind_v1
```

Output:
```
✅ Scoring complete

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

### Save Score to File

```bash
python -m eval.scoring.score_run eval/runs/20251213_170456_northwind_v1 --save
# Creates: eval/runs/20251213_170456_northwind_v1/score.json
```

### Score Latest Run

```bash
# Find latest run
LATEST=$(ls -td eval/runs/*/ | head -1 | xargs basename)
python -m eval.scoring.score_run "eval/runs/$LATEST" --save
```

## Artifact Inspection

### View Run Manifest

```bash
cat eval/runs/20251213_170456_northwind_v1/run_manifest.json | jq .
```

### View Query Result

```bash
cat eval/runs/20251213_170456_northwind_v1/Q1.json | jq .

# Pretty print specific field
cat eval/runs/20251213_170456_northwind_v1/Q1.json | jq '.sql_executed'
```

### View All Results Summary

```bash
cat eval/runs/20251213_170456_northwind_v1/summary.json | jq .

# Extract success rate
cat eval/runs/20251213_170456_northwind_v1/summary.json | jq '.success_rate'
```

### Watch Trace Events (Real-time)

```bash
# While benchmark is running in another terminal:
tail -f eval/runs/20251213_170456_northwind_v1/trace_events.jsonl | jq .
```

### Count Events by Type

```bash
cat eval/runs/20251213_170456_northwind_v1/trace_events.jsonl | \
  jq '.event_type' | sort | uniq -c
```

### Extract All SQL Queries

```bash
cat eval/runs/20251213_170456_northwind_v1/results.json | \
  jq -r '.[] | select(.sql_executed | length > 0) | .sql_executed[]'
```

### Find Failed Queries

```bash
cat eval/runs/20251213_170456_northwind_v1/results.json | \
  jq '.[] | select(.status == "failed") | {id: .query_id, error: .error}'
```

## Directory Navigation

### List All Runs

```bash
ls -lh eval/runs/
```

### List Latest 5 Runs

```bash
ls -td eval/runs/*/ | head -5 | xargs -I {} basename {}
```

### Show Run Size

```bash
du -sh eval/runs/20251213_170456_northwind_v1/
```

### Compare Two Runs

```bash
# Side-by-side summary
echo "=== Run 1 ===" && \
cat eval/runs/run1/summary.json | jq . && \
echo "=== Run 2 ===" && \
cat eval/runs/run2/summary.json | jq .
```

## Batch Operations

### Run Multiple Benchmarks

```bash
# Run with different configs
for model in gpt-4 gpt-4-turbo; do
  OPENAI_MODEL=$model \
    python -m eval.run_benchmark --run-name $model
done
```

### Score All Runs

```bash
for run_dir in eval/runs/*/; do
  echo "Scoring $(basename $run_dir)..."
  python -m eval.scoring.score_run "$run_dir" --save
done
```

### Export All Scores as CSV

```bash
echo "run_id,total,successful,failed,success_rate,avg_latency_ms" > scores.csv

for score_file in eval/runs/*/score.json; do
  run_id=$(dirname $score_file | xargs basename)
  jq -r \
    --arg run "$run_id" \
    '$run + "," + .metrics.total_queries | tostring + "," + .metrics.successful_queries | tostring + "," + .metrics.failed_queries | tostring + "," + .metrics.success_rate + "," + (.metrics.avg_latency_ms | tostring)' \
    "$score_file" >> scores.csv
done

cat scores.csv
```

## Filtering & Analysis

### Get Failures by Category

```bash
cat eval/runs/20251213_170456_northwind_v1/score.json | \
  jq '.failure_analysis'
```

### Latency Analysis

```bash
# Average latency
cat eval/runs/20251213_170456_northwind_v1/results.json | \
  jq '[.[] | .latency_ms_total] | add / length'

# Slowest queries
cat eval/runs/20251213_170456_northwind_v1/results.json | \
  jq '.[] | {id: .query_id, latency: .latency_ms_total}' | \
  jq -s 'sort_by(.latency) | reverse | .[] | select(.latency > 1000)'
```

### SQL Coverage

```bash
# Which queries had SQL executed?
cat eval/runs/20251213_170456_northwind_v1/results.json | \
  jq '.[] | select(.sql_executed | length > 0) | .query_id'
```

### Non-Empty Results

```bash
# Which queries returned data?
cat eval/runs/20251213_170456_northwind_v1/results.json | \
  jq '.[] | select(.row_count > 0) | {id: .query_id, rows: .row_count}'
```

## Advanced: Custom Dataset

### Create Custom Dataset

```bash
cat > eval/datasets/custom_test.jsonl << 'EOF'
{"id":"custom_1","question":"What is the total revenue?","tags":["revenue"]}
{"id":"custom_2","question":"Show top 10 customers","tags":["top-customers"]}
EOF
```

### Run with Custom Dataset

```bash
python -m eval.run_benchmark \
  --dataset eval/datasets/custom_test.jsonl \
  --run-name custom_test
```

## Cleanup

### Delete Specific Run

```bash
rm -rf eval/runs/20251213_170456_northwind_v1/
```

### Archive Old Runs

```bash
# Create archive
mkdir -p eval/archives
mv eval/runs/202512* eval/archives/

# List archived runs
ls eval/archives/
```

### Clean Up (Keep last N runs)

```bash
# Keep last 3 runs, delete others
ls -td eval/runs/*/ | tail -n +4 | xargs rm -rf
```

## Troubleshooting Commands

### Test LangGraph Service

```bash
curl -X POST http://localhost:5001/chat \
  -H "Content-Type: application/json" \
  -d '{"user_input": "What is 2+2?"}'
```

### Test Eval Service

```bash
curl http://localhost:7001/health
curl http://localhost:7001/runs
```

### Check Ports

```bash
lsof -i :5001    # LangGraph
lsof -i :7001    # Eval Service
lsof -i :8000    # MCP Server
```

### View Service Logs

```bash
tail -f logs/langgraph_service.log
tail -f logs/eval_service.log
```

### Debug: Trace Event Inspection

```bash
# Count events
wc -l eval/runs/20251213_170456_northwind_v1/trace_events.jsonl

# First event
head -1 eval/runs/20251213_170456_northwind_v1/trace_events.jsonl | jq .

# Events for specific query
cat eval/runs/20251213_170456_northwind_v1/trace_events.jsonl | \
  jq 'select(.query_id == "Q1")'

# Events by stage
cat eval/runs/20251213_170456_northwind_v1/trace_events.jsonl | \
  jq 'select(.stage) | .stage' | sort | uniq -c
```

## Environment Setup for Batch Runs

Create a `.env.benchmark` file:

```bash
# .env.benchmark
OPENAI_MODEL=gpt-4
EVAL_ENABLED=1
EVAL_TRACKING_URL=http://localhost:7001
MCP_SERVER_URL=http://localhost:8000
```

Then run:

```bash
export $(cat .env.benchmark | xargs)
python -m eval.run_benchmark --run-name production_v1
```

---

**Quick Aliases** (add to ~/.bashrc or ~/.zshrc):

```bash
alias eval-run="python -m eval.run_benchmark"
alias eval-score="python -m eval.scoring.score_run"
alias eval-latest="ls -td eval/runs/*/ | head -1 | xargs -I {} python -m eval.scoring.score_run {} --save"
alias eval-list="cat eval/runs/*/summary.json | jq '{run_id, success_rate}'"
```

Then:

```bash
eval-run --run-name test
eval-score eval/runs/*/
eval-latest
eval-list
```
