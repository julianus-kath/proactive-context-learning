"""
Capability tool wrappers for ReAct-style supervision.

Each function in this module:
 - Invokes the corresponding orchestrator agent/subgraph.
 - Populates a shared tool envelope on BaseState:
   - tool_output (tool-specific diff, e.g. intent / sql_query / exec_result)
   - error_info (normalized via ErrorInfo model)
   - progress_signal (coarse: positive | neutral | negative)
   - suggested_next_actions (bounded hints: rediscover | replan | clarify | stop)
   - last_tool_name / last_tool_progress_signal / last_tool_result
 - Leaves existing orchestrator metrics (node_entry_counts, llm_usage)
   to the underlying agent implementations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from langgraph_integration.contracts.state import (
    BaseState,
    ProgressSignal,
    SuggestedNextAction,
    ToolCallResult,
    normalize_error_info_payload,
)
from langgraph_integration.orchestrator import get_orchestrator


ToolName = str


async def interpret_query_tool(state: BaseState) -> BaseState:
    """
    Capability tool: interpret/parse the user query into structured intent.
    """
    orchestrator = get_orchestrator()
    result = await orchestrator.invoke_agent("parse_intent", state)
    updated_state = result.get("output_state") or {}
    error_info = result.get("error_info")

    tool_output = {
        "intent": updated_state.get("intent") or {},
    }
    progress_signal, next_actions = _derive_progress_and_actions(
        "interpret_query", updated_state, error_info
    )
    return _attach_tool_envelope(
        updated_state,
        tool_name="interpret_query",
        progress_signal=progress_signal,
        suggested_next_actions=next_actions,
        tool_output=tool_output,
        error_info=error_info,
    )


async def discover_schema_tool(state: BaseState) -> BaseState:
    """
    Capability tool: run DiscoveryAgent to find relevant tables/views and schema snippet.
    """
    orchestrator = get_orchestrator()
    result = await orchestrator.invoke_agent("discovery", state)
    updated_state = result.get("output_state") or {}
    error_info = result.get("error_info")

    tool_output = {
        "relevant_tables": updated_state.get("relevant_tables") or [],
        "schema_snippet": updated_state.get("schema_snippet") or "",
        "candidate_views": updated_state.get("candidate_views") or [],
        "column_index": updated_state.get("column_index") or {},
    }
    progress_signal, next_actions = _derive_progress_and_actions(
        "discover_schema", updated_state, error_info
    )
    return _attach_tool_envelope(
        updated_state,
        tool_name="discover_schema",
        progress_signal=progress_signal,
        suggested_next_actions=next_actions,
        tool_output=tool_output,
        error_info=error_info,
    )


async def plan_sql_tool(state: BaseState) -> BaseState:
    """
    Capability tool: run JoinPlanAndSQLAgent to build join plan and generate SQL.
    """
    orchestrator = get_orchestrator()
    result = await orchestrator.invoke_agent("join_sql", state)
    updated_state = result.get("output_state") or {}
    error_info = result.get("error_info")

    join_plan = updated_state.get("join_plan")
    if not isinstance(join_plan, dict):
        join_plan = {}

    tool_output = {
        "join_plan": join_plan,
        "sql_query": updated_state.get("sql_query") or "",
        # Surface key planner metadata for the supervisor.
        "plan_status": join_plan.get("plan_status"),
        "plan_confidence": join_plan.get("plan_confidence"),
        "plan_issues": join_plan.get("plan_issues") or [],
        "template": join_plan.get("template"),
    }
    progress_signal, next_actions = _derive_progress_and_actions(
        "plan_sql", updated_state, error_info
    )
    return _attach_tool_envelope(
        updated_state,
        tool_name="plan_sql",
        progress_signal=progress_signal,
        suggested_next_actions=next_actions,
        tool_output=tool_output,
        error_info=error_info,
    )


async def validate_sql_tool(state: BaseState) -> BaseState:
    """
    Capability tool: run SQLValidatorAgent to validate and repair SQL.
    """
    orchestrator = get_orchestrator()
    result = await orchestrator.invoke_agent("validate_sql", state)
    updated_state = result.get("output_state") or {}
    error_info = result.get("error_info")

    tool_output = {
        "sql_query": updated_state.get("sql_query") or "",
        "validation_result": updated_state.get("validation_result") or {},
    }
    progress_signal, next_actions = _derive_progress_and_actions(
        "validate_sql", updated_state, error_info
    )
    return _attach_tool_envelope(
        updated_state,
        tool_name="validate_sql",
        progress_signal=progress_signal,
        suggested_next_actions=next_actions,
        tool_output=tool_output,
        error_info=error_info,
    )


async def execute_sql_tool(state: BaseState) -> BaseState:
    """
    Capability tool: execute validated SQL via ExecAndRecoveryAgent.

    Enforces a HARD validation gate:
    - If validation_result.is_valid is not True, this tool WILL NOT call
      ExecAndRecoveryAgent or MCP. Instead it populates a structured
      VALIDATION_GATE_VIOLATION error and returns immediately.
    """
    validation = state.get("validation_result") or {}
    is_valid = isinstance(validation, dict) and bool(validation.get("is_valid", False))

    if not is_valid:
        error_payload = {
            "type": "VALIDATION_GATE_VIOLATION",
            "message": (
                "execute_sql_tool refused to run because the SQL query has not "
                "passed structural validation."
            ),
            "suggestion": (
                "Re-run SQL planning/validation or clarify the question before "
                "attempting execution again."
            ),
            "context": {
                "has_validation_result": bool(validation),
                "validation_result": validation,
            },
        }
        normalized_error = normalize_error_info_payload(error_payload)
        gated_state: BaseState = dict(state)
        if normalized_error:
            gated_state["error_info"] = normalized_error

        tool_output = {
            "sql_query": gated_state.get("sql_query") or "",
            "validation_result": validation,
            "exec_result": gated_state.get("exec_result"),
        }
        progress_signal: ProgressSignal = "negative"
        suggested_next_actions: List[SuggestedNextAction] = ["replan", "clarify", "stop"]
        return _attach_tool_envelope(
            gated_state,
            tool_name="execute_sql",
            progress_signal=progress_signal,
            suggested_next_actions=suggested_next_actions,
            tool_output=tool_output,
            error_info=normalized_error,
        )

    orchestrator = get_orchestrator()
    result = await orchestrator.invoke_agent("exec_recovery", state)
    updated_state = result.get("output_state") or {}
    error_info = result.get("error_info")

    tool_output = {
        "sql_query": updated_state.get("sql_query") or "",
        "exec_result": updated_state.get("exec_result"),
        "validation_result": updated_state.get("validation_result") or {},
    }
    progress_signal, next_actions = _derive_progress_and_actions(
        "execute_sql", updated_state, error_info
    )
    return _attach_tool_envelope(
        updated_state,
        tool_name="execute_sql",
        progress_signal=progress_signal,
        suggested_next_actions=next_actions,
        tool_output=tool_output,
        error_info=error_info,
    )


async def evaluate_result_tool(state: BaseState) -> BaseState:
    """
    Capability tool: run deterministic ResultValidator over exec_result + metadata.
    """
    orchestrator = get_orchestrator()
    result = await orchestrator.invoke_agent("result_validator", state)
    updated_state = result.get("output_state") or {}
    error_info = result.get("error_info")

    tool_output = {
        "validation_result": updated_state.get("validation_result") or {},
        "exec_result": updated_state.get("exec_result"),
    }
    progress_signal, next_actions = _derive_progress_and_actions(
        "evaluate_result", updated_state, error_info
    )
    return _attach_tool_envelope(
        updated_state,
        tool_name="evaluate_result",
        progress_signal=progress_signal,
        suggested_next_actions=next_actions,
        tool_output=tool_output,
        error_info=error_info,
    )


async def finalize_answer_tool(state: BaseState) -> BaseState:
    """
    Capability tool: format the final answer using AnswerAgent.
    """
    orchestrator = get_orchestrator()
    result = await orchestrator.invoke_agent("answer", state)
    updated_state = result.get("output_state") or {}
    error_info = result.get("error_info")

    tool_output = {
        "final_response": updated_state.get("final_response"),
        "answer_mode": updated_state.get("answer_mode"),
    }
    progress_signal, next_actions = _derive_progress_and_actions(
        "finalize_answer", updated_state, error_info
    )
    return _attach_tool_envelope(
        updated_state,
        tool_name="finalize_answer",
        progress_signal=progress_signal,
        suggested_next_actions=next_actions,
        tool_output=tool_output,
        error_info=error_info,
    )


def _derive_progress_and_actions(
    tool_name: ToolName,
    state: BaseState,
    error_info: Optional[Dict[str, Any]],
) -> Tuple[ProgressSignal, List[SuggestedNextAction]]:
    """
    Map tool outcome to a coarse-grained progress signal and suggested next actions.

    This is intentionally simple and deterministic so that supervisors can reason
    about progress without inspecting raw state or chain-of-thought.
    """
    # Hard error path overrides other heuristics (except for plan_sql, which
    # uses join_plan metadata for more nuanced progress signals).
    if error_info and tool_name != "plan_sql":
        if tool_name in {"interpret_query", "discover_schema"}:
            return "negative", ["clarify", "stop"]
        if tool_name in {"validate_sql", "execute_sql", "evaluate_result"}:
            return "negative", ["replan", "clarify", "stop"]
        if tool_name == "finalize_answer":
            return "neutral", ["stop"]

    if tool_name == "plan_sql":
        join_plan = state.get("join_plan") or {}
        if not isinstance(join_plan, dict):
            join_plan = {}

        plan_status = join_plan.get("plan_status")
        sql_query = (state.get("sql_query") or "").strip()

        # Normalize error payload so we can safely inspect its type.
        normalized_error = normalize_error_info_payload(error_info) if error_info else None
        error_type = ""
        if isinstance(normalized_error, dict):
            raw_type = normalized_error.get("type")
            if raw_type:
                error_type = str(raw_type).upper()

        # Determine whether the underlying intent is analytic. We intentionally
        # use a coarse heuristic here rather than duplicating planner routing.
        intent = state.get("intent") or {}
        analytic_template = intent.get("analytic_template")
        metrics = intent.get("metrics") or []
        is_analytic_intent = bool(analytic_template) or bool(metrics)

        # Failed or incomplete plans (including explicit join-error types) are
        # negative progress and should push the supervisor toward
        # rediscovery/replanning/clarification instead of execution.
        is_join_error = bool(normalized_error and error_type)
        if is_join_error or plan_status in {"incomplete", "unsupported"}:
            return "negative", ["rediscover", "replan", "clarify", "stop"]

        # Exploratory plans are neutral (not positive) when the intent is
        # clearly analytic; the supervisor should consider replanning or
        # rediscovery rather than treating them as success.
        if plan_status == "exploratory" and is_analytic_intent:
            return "neutral", ["replan", "rediscover", "clarify", "stop"]

        # A healthy plan with non-empty SQL is a positive step. For genuinely
        # exploratory/detail intents, exploratory status is acceptable.
        if sql_query and (plan_status in {None, "ok", "exploratory"}):
            return "positive", ["replan", "stop"]

        # Plans that claim to be OK but don't produce SQL should be treated as
        # negative progress so the supervisor can take corrective action.
        if plan_status == "ok" and not sql_query:
            return "negative", ["replan", "rediscover", "clarify", "stop"]

        # Conservative default when no SQL and no explicit failure metadata.
        return "neutral", ["rediscover", "replan", "clarify", "stop"]

    if tool_name == "interpret_query":
        intent = state.get("intent") or {}
        operation = intent.get("operation")
        if operation in {"query", "schema_query", "health_check"}:
            return "positive", ["rediscover", "replan", "stop"]
        return "neutral", ["clarify", "stop"]

    if tool_name == "discover_schema":
        tables = state.get("relevant_tables") or []
        if tables:
            return "positive", ["replan", "stop"]
        return "neutral", ["rediscover", "clarify", "stop"]

    if tool_name == "plan_sql":
        sql_query = (state.get("sql_query") or "").strip()
        if sql_query:
            return "positive", ["replan", "stop"]
        return "neutral", ["rediscover", "replan", "clarify"]

    if tool_name == "validate_sql":
        validation = state.get("validation_result") or {}
        is_valid = bool(validation.get("is_valid", False))
        if is_valid:
            return "positive", ["stop"]
        return "negative", ["replan", "clarify", "stop"]

    if tool_name == "execute_sql":
        exec_result = state.get("exec_result") or {}
        if isinstance(exec_result, dict) and exec_result.get("ok"):
            return "positive", ["stop"]
        return "negative", ["replan", "clarify", "stop"]

    if tool_name == "evaluate_result":
        validation = state.get("validation_result") or {}
        retry_action = (validation.get("retry_action") or "accept").lower()
        if retry_action == "accept":
            return "positive", ["stop"]
        if retry_action == "ask_user":
            return "neutral", ["clarify", "stop"]
        # try_next_candidate / replan_with_* → supervisor should consider replanning
        return "negative", ["replan", "rediscover", "stop"]

    if tool_name == "finalize_answer":
        if state.get("final_response"):
            return "positive", ["stop"]
        return "neutral", ["clarify", "stop"]

    # Conservative default
    return "neutral", ["stop"]


def _attach_tool_envelope(
    state: BaseState,
    tool_name: ToolName,
    progress_signal: ProgressSignal,
    suggested_next_actions: List[SuggestedNextAction],
    tool_output: Dict[str, Any],
    error_info: Optional[Dict[str, Any]],
) -> BaseState:
    """
    Attach the shared ToolCallResult envelope to the state.
    """
    envelope: ToolCallResult = {
        "tool_output": tool_output or {},
        "error_info": error_info,
        "progress_signal": progress_signal,
        "suggested_next_actions": list(suggested_next_actions or []),
    }

    state["last_tool_result"] = envelope
    state["tool_output"] = envelope["tool_output"]
    state["progress_signal"] = envelope["progress_signal"]
    state["suggested_next_actions"] = envelope["suggested_next_actions"]
    state["last_tool_name"] = tool_name
    state["last_tool_progress_signal"] = progress_signal

    return state
