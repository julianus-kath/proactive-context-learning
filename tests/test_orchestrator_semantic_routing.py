"""
Unit tests for semantic-aware routing in route_validation_result.

These tests exercise QueryOrchestrator._route_validation_result_for_state,
which mirrors the logic used by the route_validation_result closure in the
compiled LangGraph graph. The focus is on:
- mapping semantic_status / semantic_retry_action to existing retry_action values
- enforcing semantic and global plan budgets
- ensuring interactive mode ignores semantic replanning requests
"""

import os
import sys

import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from langgraph_integration.orchestrator import QueryOrchestrator
from langgraph_integration.contracts.state import BaseState


def _base_state(**overrides) -> BaseState:
    state: BaseState = {
        "user_input": "benchmark query",
        "intent": {"operation": "query"},
        "validation_result": {
            "valid": True,
            "retry_action": "accept",
        },
        "llm_usage": {"total": 0},
        "max_llm_calls": 20,
        "llm_budget_safety_margin": 0,
        "validation_attempt_count": 0,
        "exec_recovery_attempt_count": 0,
        "max_validation_attempts": 3,
        "max_exec_recovery_attempts": 3,
        "max_no_progress_repeats": 3,
        "repair_signatures_seen": {},
        "plan_attempt_count": 0,
        "max_total_plans": 4,
        "retry_attempt_count": 0,
        "max_retries_per_candidate_set": 3,
        "semantic_retry_count": 0,
        "max_semantic_retries": 2,
    }
    state.update(overrides)
    return state


class TestSemanticRouting:
    """Semantic-aware routing behaviour in benchmark vs interactive modes."""

    def test_entity_mismatch_triggers_semantic_replan_to_join(self):
        """ENTITY_MISMATCH in benchmark mode should map to replan_with_aggregation/join_sql."""
        orch = QueryOrchestrator()

        state = _base_state(
            eval_mode="benchmark",
            validation_result={
                "valid": True,
                "retry_action": "accept",
                "semantic_status": "ENTITY_MISMATCH",
                "semantic_retry_action": "replan",
            },
        )

        next_node = orch._route_validation_result_for_state(state)

        assert next_node == "join_sql"
        vr = state.get("validation_result") or {}
        assert vr.get("retry_action") == "replan_with_aggregation"
        # Semantic-driven replans should increment both plan and semantic counters.
        assert state.get("plan_attempt_count") == 1
        assert state.get("semantic_retry_count") == 1

    def test_join_path_invalid_triggers_try_next_candidate(self):
        """JOIN_PATH_INVALID in benchmark mode should map to try_next_candidate/discovery."""
        orch = QueryOrchestrator()

        state = _base_state(
            eval_mode="benchmark",
            validation_result={
                "valid": True,
                "retry_action": "accept",
                "semantic_status": "JOIN_PATH_INVALID",
                "semantic_retry_action": "replan",
            },
        )

        next_node = orch._route_validation_result_for_state(state)

        assert next_node == "discovery"
        vr = state.get("validation_result") or {}
        assert vr.get("retry_action") == "try_next_candidate"
        assert state.get("plan_attempt_count") == 1
        assert state.get("semantic_retry_count") == 1

    def test_semantic_budget_exhaustion_sets_stop_reason_and_skips_replan(self):
        """When semantic_retry_count reaches max_semantic_retries, no further semantic replans are triggered."""
        orch = QueryOrchestrator()

        state = _base_state(
            eval_mode="benchmark",
            semantic_retry_count=2,
            max_semantic_retries=2,
            validation_result={
                "valid": True,
                "retry_action": "accept",
                "semantic_status": "METRIC_MISMATCH",
                "semantic_retry_action": "replan",
            },
        )

        next_node = orch._route_validation_result_for_state(state)

        # With retry_action=accept and semantic budget exhausted, routing should go to answer.
        assert next_node == "answer"
        assert state.get("plan_attempt_count") == 0
        assert state.get("semantic_retry_count") == 2
        assert state.get("stop_reason") == "max_semantic_retries"

    def test_interactive_mode_ignores_semantic_replan_requests(self):
        """Interactive mode should treat semantic findings as logging-only and not trigger replans."""
        orch = QueryOrchestrator()

        state = _base_state(
            eval_mode=None,
            validation_result={
                "valid": True,
                "retry_action": "accept",
                "semantic_status": "ENTITY_MISMATCH",
                "semantic_retry_action": "replan",
            },
        )

        next_node = orch._route_validation_result_for_state(state)

        # Because retry_action remains 'accept', routing should go directly to answer.
        assert next_node == "answer"
        assert state.get("plan_attempt_count") == 0
        assert state.get("semantic_retry_count") == 0
