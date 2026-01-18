"""
Evaluation & Tracking Service
Standalone FastAPI service that records experiment runs and per-query artifacts.
Runs independently on port 7001 (optional).
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Evaluation & Tracking Service",
    description="Records evaluation runs and per-query artifacts for thesis validation",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RUNS_DIR = Path(__file__).parent / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

class RunManifest(BaseModel):
    run_id: str
    run_name: str
    timestamp: str
    git_commit: Optional[str] = None
    dataset_path: str
    mcp_server_url: str
    model: str
    prompt_versions: Optional[Dict[str, str]] = None
    environment: Optional[Dict[str, str]] = None
    total_queries: int = 0
    completed_queries: int = 0
    failed_queries: int = 0

class QueryArtifact(BaseModel):
    query_id: str
    question: str
    status: str
    final_answer_text: Optional[str] = None
    sql_generated: List[str] = Field(default_factory=list)
    sql_executed: List[str] = Field(default_factory=list)
    tables_used: List[str] = Field(default_factory=list)
    result_preview: Optional[List[Dict[str, Any]]] = None
    row_count: Optional[int] = None
    latency_ms_total: int = 0
    latency_ms_by_stage: Optional[Dict[str, int]] = None
    retries: int = 0
    error: Optional[str] = None
    trace_events: Optional[List[Dict[str, Any]]] = None

class TraceEvent(BaseModel):
    run_id: str
    query_id: str
    event_type: str
    timestamp: str
    stage: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

@app.get("/health")
def health():
    return {"status": "ok", "service": "evaluation"}

@app.post("/runs")
def create_run(manifest: RunManifest) -> Dict[str, Any]:
    """Create a new evaluation run."""
    run_dir = RUNS_DIR / manifest.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    
    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2))
    
    logger.info(f"Created run {manifest.run_id} at {run_dir}")
    return {
        "ok": True,
        "run_id": manifest.run_id,
        "run_dir": str(run_dir),
        "timestamp": manifest.timestamp,
    }

@app.post("/runs/{run_id}/queries/{query_id}")
def save_query_artifact(run_id: str, query_id: str, artifact: QueryArtifact) -> Dict[str, Any]:
    """Save per-query artifact."""
    run_dir = RUNS_DIR / run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    artifact_path = run_dir / f"{query_id}.json"
    artifact_path.write_text(artifact.model_dump_json(indent=2))
    
    logger.info(f"Saved artifact for {run_id}/{query_id}")
    return {
        "ok": True,
        "run_id": run_id,
        "query_id": query_id,
        "artifact_path": str(artifact_path),
    }

@app.post("/events")
def append_event(event: TraceEvent) -> Dict[str, Any]:
    """Append a trace event (append-only log)."""
    run_dir = RUNS_DIR / event.run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run {event.run_id} not found")
    
    events_file = run_dir / "trace_events.jsonl"
    with open(events_file, "a") as f:
        f.write(event.model_dump_json() + "\n")
    
    return {"ok": True, "event_type": event.event_type}

@app.get("/runs/{run_id}")
def get_run(run_id: str) -> Dict[str, Any]:
    """Retrieve a run and its artifacts."""
    run_dir = RUNS_DIR / run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Manifest not found")
    
    manifest = json.loads(manifest_path.read_text())
    
    artifacts = {}
    for artifact_file in run_dir.glob("Q*.json"):
        query_id = artifact_file.stem
        artifacts[query_id] = json.loads(artifact_file.read_text())
    
    return {
        "run_id": run_id,
        "manifest": manifest,
        "artifacts": artifacts,
        "run_dir": str(run_dir),
    }

@app.get("/runs")
def list_runs() -> Dict[str, Any]:
    """List all runs."""
    runs = []
    for run_dir in RUNS_DIR.iterdir():
        if run_dir.is_dir() and (run_dir / "run_manifest.json").exists():
            manifest = json.loads((run_dir / "run_manifest.json").read_text())
            runs.append({
                "run_id": run_dir.name,
                "run_name": manifest.get("run_name"),
                "timestamp": manifest.get("timestamp"),
                "total_queries": manifest.get("total_queries"),
                "completed_queries": manifest.get("completed_queries"),
            })
    
    return {"runs": sorted(runs, key=lambda r: r["timestamp"], reverse=True)}

def start_service(host: str = "127.0.0.1", port: int = 7001):
    """Start the evaluation service."""
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )

if __name__ == "__main__":
    start_service()
