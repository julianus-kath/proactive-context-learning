import json
from pathlib import Path

from eval.scoring.score_run import score_run


def _write_run_files(run_dir: Path, results: dict) -> None:
    manifest = {
        "run_id": "test_run",
        "run_name": "test",
        "timestamp": "2025-01-01T00:00:00Z",
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest))
    (run_dir / "results.json").write_text(json.dumps(results))


def test_semantic_correctness_metrics_mixed_statuses(tmp_path: Path) -> None:
    """
    Mixed semantic statuses:
    - Only successful queries with semantic_status == \"OK\" count as semantically correct.
    """
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    results = {
        "Q1": {
            "status": "success",
            "latency_ms_total": 100,
            "row_count": 10,
            "error": None,
            "sql_executed": ["SELECT 1"],
            "semantic_status": "OK",
        },
        "Q2": {
            "status": "success",
            "latency_ms_total": 200,
            "row_count": 5,
            "error": None,
            "sql_executed": ["SELECT 2"],
            "semantic_status": "ENTITY_MISMATCH",
        },
        "Q3": {
            "status": "failed",
            "latency_ms_total": 300,
            "row_count": 0,
            "error": "timeout",
            "sql_executed": [],
            "semantic_status": "OK",
        },
    }

    _write_run_files(run_dir, results)

    score = score_run(run_dir)
    metrics = score["metrics"]

    assert metrics["total_queries"] == 3
    assert metrics["successful_queries"] == 2
    assert metrics["failed_queries"] == 1

    # Only Q1 should be counted as semantically correct.
    assert metrics["entity_metric_join_correct_count"] == 1
    assert metrics["entity_metric_join_correct_rate"] == "33.3%"


def test_scoring_without_semantic_fields_is_backward_compatible(tmp_path: Path) -> None:
    """
    When semantic fields are absent, legacy metrics remain unchanged and
    semantic correctness metrics fall back to zero without raising errors.
    """
    run_dir = tmp_path / "run_no_semantics"
    run_dir.mkdir()

    results = {
        "Q1": {
            "status": "success",
            "latency_ms_total": 100,
            "row_count": 10,
            "error": None,
            "sql_executed": ["SELECT 1"],
        },
        "Q2": {
            "status": "success",
            "latency_ms_total": 150,
            "row_count": 3,
            "error": None,
            "sql_executed": ["SELECT 2"],
        },
        "Q3": {
            "status": "failed",
            "latency_ms_total": 250,
            "row_count": 0,
            "error": "timeout",
            "sql_executed": [],
        },
    }

    _write_run_files(run_dir, results)

    score = score_run(run_dir)
    metrics = score["metrics"]

    assert metrics["total_queries"] == 3
    assert metrics["successful_queries"] == 2
    assert metrics["failed_queries"] == 1

    # Legacy metrics should still be computed.
    assert metrics["success_rate"] == "66.7%"

    # Without semantic fields, semantic correctness metrics should be zeroed.
    assert metrics["entity_metric_join_correct_count"] == 0
    assert metrics["entity_metric_join_correct_rate"] == "0.0%"

