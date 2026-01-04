import os
from pathlib import Path

from langgraph_integration.debug_logger import DebugLogger


def _drain_buffer() -> None:
    # Import inside to avoid circular import issues.
    from langgraph_integration.debug_logger import DebugLogger as _DL  # type: ignore

    _DL.get_buffered_logs()


def test_agent_entry_state_snapshot_gated_by_env(tmp_path, monkeypatch):
    """
    agent_entry should only attach full state_snapshot when
    LANGGRAPH_DEBUG_VERBOSE is truthy.
    """
    log_dir = tmp_path / "logs"

    # Non-verbose mode: default (or explicit "0") should omit state_snapshot.
    monkeypatch.setenv("LANGGRAPH_DEBUG_VERBOSE", "0")
    _drain_buffer()
    logger = DebugLogger(name="test_logger_basic", log_dir=str(log_dir))
    logger.agent_entry("dummy_agent", {"foo": "bar"})

    from langgraph_integration.debug_logger import DebugLogger as DL  # type: ignore

    logs = DL.get_buffered_logs_no_clear()
    assert logs, "Expected at least one buffered log entry"
    last = logs[-1]
    data = last.get("data") or {}
    assert data.get("event") == "agent_entry"
    assert "state_snapshot" not in data

    # Verbose mode: enable full state snapshots.
    monkeypatch.setenv("LANGGRAPH_DEBUG_VERBOSE", "1")
    _drain_buffer()
    logger_verbose = DebugLogger(name="test_logger_verbose", log_dir=str(log_dir))
    logger_verbose.agent_entry("dummy_agent", {"foo": "bar"})

    logs_verbose = DL.get_buffered_logs_no_clear()
    assert logs_verbose, "Expected buffered logs in verbose mode"
    last_verbose = logs_verbose[-1]
    data_verbose = last_verbose.get("data") or {}
    assert data_verbose.get("event") == "agent_entry"
    assert data_verbose.get("state_snapshot") == {"foo": "bar"}

