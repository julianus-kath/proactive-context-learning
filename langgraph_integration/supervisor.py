"""
ReAct-style supervisor loop for capability tools.

This module introduces a lightweight supervisor that:
- Chooses which capability tool to run next.
- Tracks supervisor-specific budgets and step counts.
- Maintains a high-level `supervisor_trace` without storing raw CoT.

Design goals:
- Keep orchestration adaptive but deterministic and testable.
- Reuse existing capability tools and BaseState contracts.
- Avoid duplicating heavy routing logic from the fixed pipeline.
"""

from __future__ import annotations

import logging
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph_integration.contracts.state import BaseState, ProgressSignal
from langgraph_integration.tools import capability_tools
from langgraph_integration.debug_logger import get_debug_logger


logger = logging.getLogger(__name__)
debug_logger = get_debug_logger()


ToolName = str


@dataclass
class SupervisorConfig:
    """
    Configuration for the ReAct-style supervisor loop.

    The supervisor enforces its own step and no-progress budgets while
    respecting the global LLM budget already tracked on BaseState.
    """

    # Maximum supervisor loop iterations (tool invocations)
    max_supervisor_steps: int = 12

    # Optional hard cap on total LLM calls (in addition to BaseState.max_llm_calls).
    # When None, the supervisor relies solely on BaseState.max_llm_calls.
    max_llm_calls_total: Optional[int] = None

    # Maximum number of consecutive "no progress" iterations (same tool + non-positive signal)
    max_no_progress_repeats: int = 3


class ReactSupervisor:
    """
    Small helper class encapsulating the ReAct-style loop over capability tools.

    Instances are lightweight and stateless beyond their config; all state lives
    on the shared BaseState mapping passed into `run()`.

    BaseState contract (supervisor-specific fields):
    - Consumes:
      - intent / relevant_tables / sql_query / validation_result / exec_result / final_response
      - total_llm_calls / max_llm_calls (global budget, shared with agents)
      - progress_signal / suggested_next_actions (set by capability tools)
    - Produces/updates:
      - supervisor_trace (structured think→act→observe trace, no raw CoT)
      - supervisor_step_count / max_supervisor_steps
      - last_tool_name / last_tool_progress_signal
      - no_progress_repeat_count
      - orchestration_mode="react_supervisor"
      - stop_reason (normalized to: success | clarify | budget_exhausted | fatal_error)
      - tool_output / last_tool_result (as populated by capability tools)
    """

    def __init__(self, config: Optional[SupervisorConfig] = None) -> None:
        self.config = config or SupervisorConfig()
        # LLM used to choose the next tool (ReAct-style decision making).
        # Uses a small, cheap model by default; callers can override via env.
        model = (
            os.getenv("SUPERVISOR_LLM_MODEL")
            or os.getenv("LANGGRAPH_LLM_MODEL")
            or os.getenv("OPENAI_MODEL")
            or "gpt-4o-mini"
        )
        # Temperature 0 for deterministic, testable behavior given the same state.
        self.llm = ChatOpenAI(model=model, temperature=0.0)

    async def _llm_select_next_tool(
        self,
        state: BaseState,
        last_tool_name: Optional[ToolName],
    ) -> Optional[ToolName]:
        """
        Use the supervisor LLM to choose the next capability tool.

        The LLM sees a compact summary of the current world state (intent,
        validation, execution, budgets, last tool, progress) and must select one
        of the known tools or "__STOP__".
        """
        try:
            intent = state.get("intent") or {}
            validation = state.get("validation_result") or {}
            exec_result = state.get("exec_result") or {}
            error_info = state.get("error_info") or {}

            summary: Dict[str, Any] = {
                "intent": {
                    "operation": intent.get("operation"),
                    "needs_clarification": bool(intent.get("needs_clarification")),
                    "primary_entities": intent.get("primary_entities") or [],
                    "metrics": intent.get("metrics") or [],
                },
                "have_relevant_tables": bool(state.get("relevant_tables")),
                "have_sql_query": bool((state.get("sql_query") or "").strip()),
                "validation_result": {
                    "is_valid": bool(validation.get("is_valid", False)),
                    "retry_action": validation.get("retry_action"),
                },
                "exec_result": {
                    "ok": bool(exec_result.get("ok")) if isinstance(exec_result, dict) else False,
                    "row_count": exec_result.get("row_count") if isinstance(exec_result, dict) else None,
                },
                "error_info_type": error_info.get("type") if isinstance(error_info, dict) else None,
                "last_tool_name": last_tool_name,
                "progress_signal": state.get("progress_signal"),
                "suggested_next_actions": list(state.get("suggested_next_actions") or []),
                "budgets": {
                    "supervisor_step_count": int(state.get("supervisor_step_count", 0) or 0),
                    "max_supervisor_steps": int(state.get("max_supervisor_steps", 0) or 0),
                    "total_llm_calls": int(state.get("total_llm_calls", 0) or 0),
                    "max_llm_calls": int(state.get("max_llm_calls", 0) or 0),
                    "no_progress_repeat_count": int(state.get("no_progress_repeat_count", 0) or 0),
                },
            }

            allowed_tools: List[ToolName] = [
                "interpret_query",
                "discover_schema",
                "plan_sql",
                "validate_sql",
                "execute_sql",
                "evaluate_result",
                "finalize_answer",
                "__STOP__",
            ]

            system = (
                "You are the supervisor for an ERP multi-agent system. "
                "Your job is to choose the NEXT capability tool to run, based on the current state. "
                "Tools:\n"
                "- interpret_query: parse intent / clarify what the user wants.\n"
                "- discover_schema: find relevant tables/views using the catalog.\n"
                "- plan_sql: build a join plan and generate SQL from intent + discovered tables.\n"
                "- validate_sql: check/repair SQL syntax and structure.\n"
                "- execute_sql: run a validated SQL query against the database.\n"
                "- evaluate_result: check result quality and decide if retry/replan is needed.\n"
                "- finalize_answer: format the final answer for the user.\n"
                "- __STOP__: stop the loop (only when an answer is ready or budgets are exhausted).\n\n"
                "Constraints:\n"
                "- Do NOT call execute_sql before there is a non-empty sql_query.\n"
                "- Prefer validate_sql before execute_sql when sql_query is present but not validated.\n"
                "- If intent.operation is 'health_check', you usually go directly to finalize_answer.\n"
                "- If intent.operation is 'schema_query' and no relevant_tables yet, call discover_schema.\n"
                "- If evaluate_result suggests try_next_candidate or replan_with_*, you may pick discover_schema or plan_sql.\n"
                "- Respect budgets and avoid infinite loops."
            )

            user = (
                "Current state summary (JSON):\n"
                f"{json.dumps(summary, ensure_ascii=False)}\n\n"
                "Respond with ONLY the name of the next tool to run, exactly one of:\n"
                f"{', '.join(allowed_tools)}\n"
            )

            response = await self.llm.ainvoke(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ]
            )
            text = (getattr(response, "content", "") or "").strip()
            # Take the first token/word as the tool name.
            candidate = text.split()[0] if text else ""
            if candidate in allowed_tools:
                return candidate  # type: ignore[return-value]
            logger.debug("Supervisor LLM returned unsupported tool %r; falling back to heuristic policy", candidate)
        except Exception:
            logger.debug("Supervisor LLM decision failed; falling back to heuristic policy", exc_info=True)
        return None

    async def run(self, state: BaseState) -> BaseState:
        """
        Run the supervisor loop until a terminal condition or budget is reached.
        """
        current: BaseState = dict(state)

        current.setdefault("supervisor_trace", [])
        current["orchestration_mode"] = "react_supervisor"
        current["supervisor_step_count"] = int(current.get("supervisor_step_count", 0) or 0)
        current["max_supervisor_steps"] = int(
            current.get("max_supervisor_steps") or self.config.max_supervisor_steps
        )
        current["no_progress_repeat_count"] = int(current.get("no_progress_repeat_count", 0) or 0)

        # Align supervisor-level LLM budget with BaseState.max_llm_calls when provided.
        state_max_llm = int(current.get("max_llm_calls") or 0) or None
        effective_llm_budget = self.config.max_llm_calls_total
        if state_max_llm is not None:
            effective_llm_budget = (
                min(state_max_llm, effective_llm_budget)
                if effective_llm_budget is not None
                else state_max_llm
            )

        last_tool_name: Optional[ToolName] = current.get("last_tool_name")
        last_progress: ProgressSignal = current.get("progress_signal") or "neutral"

        # Initial tool selection (may be overridden by LLM below).
        next_tool: Optional[ToolName] = _select_initial_tool(current, last_tool_name)

        while True:
            step = int(current.get("supervisor_step_count", 0) or 0)
            max_steps = int(current.get("max_supervisor_steps") or self.config.max_supervisor_steps)

            # Refresh LLM usage on each loop iteration so supervisor-level
            # budget checks reflect the latest state after tool invocations.
            total_llm_calls = int(current.get("total_llm_calls", 0) or 0)

            # Step-budget stop condition
            if step >= max_steps:
                logger.info(
                    "react_supervisor_budget_exhausted: steps=%s max_steps=%s",
                    step,
                    max_steps,
                )
                current["stop_reason"] = "budget_exhausted"
                current = await _ensure_final_answer(current)
                _append_trace_entry(
                    current,
                    step=step,
                    tool_name="__budget_stop__",
                    thought_summary="Stopped because supervisor step budget was exhausted.",
                    tool_inputs_digest={"reason": "max_supervisor_steps"},
                    observation_summary="Supervisor terminated due to step budget.",
                )
                break

            # Global LLM budget stop condition (shared with agents)
            if effective_llm_budget is not None and total_llm_calls >= effective_llm_budget:
                logger.info(
                    "react_supervisor_llm_budget_exhausted: total=%s max=%s",
                    total_llm_calls,
                    effective_llm_budget,
                )
                current["stop_reason"] = "budget_exhausted"
                current = await _ensure_final_answer(current)
                _append_trace_entry(
                    current,
                    step=step,
                    tool_name="__budget_stop__",
                    thought_summary="Stopped because the global LLM budget was exhausted.",
                    tool_inputs_digest={"reason": "max_llm_calls"},
                    observation_summary="Supervisor terminated due to LLM budget.",
                )
                break

            # Let the supervisor LLM choose an initial tool when none has been selected yet.
            if next_tool is None or next_tool == "__STOP__":
                candidate = await self._llm_select_next_tool(current, last_tool_name)
                if candidate:
                    next_tool = candidate

            if next_tool is None or next_tool == "__STOP__":
                # No further actions selected; ensure we have a final answer.
                current = await _ensure_final_answer(current)
                break

            # Terminal condition: if finalize_answer already ran and produced a response, stop.
            if _is_terminal(current, last_tool_name):
                current = await _ensure_final_answer(current)
                break

            before_snapshot: BaseState = dict(current)

            # Invoke the chosen capability tool.
            current = await _invoke_tool(next_tool, current)

            step += 1
            current["supervisor_step_count"] = step
            last_tool_name = next_tool

            # Update no-progress repeat counter using the tool's progress_signal.
            progress: ProgressSignal = current.get("progress_signal") or "neutral"
            if progress == "positive":
                current["no_progress_repeat_count"] = 0
            else:
                if last_progress == progress and last_tool_name == next_tool:
                    current["no_progress_repeat_count"] = int(
                        current.get("no_progress_repeat_count", 0) or 0
                    ) + 1
                else:
                    current["no_progress_repeat_count"] = 0
            last_progress = progress

            # Supervisor trace: short, summary-only decision and observation.
            thought_summary, obs_summary = _summarize_step(
                tool_name=next_tool,
                before_state=before_snapshot,
                after_state=current,
            )
            _append_trace_entry(
                current,
                step=step,
                tool_name=next_tool,
                thought_summary=thought_summary,
                tool_inputs_digest=_summarize_inputs(before_snapshot),
                observation_summary=obs_summary,
            )

            # No-progress budget enforcement
            if int(current.get("no_progress_repeat_count", 0) or 0) >= self.config.max_no_progress_repeats:
                logger.info(
                    "react_supervisor_no_progress_exhausted: repeats=%s max_repeats=%s",
                    current.get("no_progress_repeat_count"),
                    self.config.max_no_progress_repeats,
                )
                current["stop_reason"] = "budget_exhausted"
                _append_trace_entry(
                    current,
                    step=step,
                    tool_name="__budget_stop__",
                    thought_summary="Stopped because no-progress budget was exhausted.",
                    tool_inputs_digest={"reason": "no_progress_repeats"},
                    observation_summary="Supervisor terminated after repeated non-progress signals.",
                )
                current = await _ensure_final_answer(current)
                break

            # If a terminal condition was reached by this tool, stop.
            if _is_terminal(current, last_tool_name):
                current = await _ensure_final_answer(current)
                break

            # Determine the next tool based on current state and last tool.
            candidate = await self._llm_select_next_tool(current, last_tool_name)
            if candidate:
                next_tool = candidate
            else:
                next_tool = _select_next_tool(current, last_tool_name)

        _normalize_stop_reason(current)

        # Emit a final supervisor summary to the debug logger so that
        # downstream tools can inspect outcomes without reading full state.
        try:
            trace = current.get("supervisor_trace") or []
            budgets = {
                "supervisor_step_count": int(current.get("supervisor_step_count", 0) or 0),
                "max_supervisor_steps": int(current.get("max_supervisor_steps", 0) or 0),
                "total_llm_calls": int(current.get("total_llm_calls", 0) or 0),
                "max_llm_calls": int(current.get("max_llm_calls", 0) or 0),
                "no_progress_repeat_count": int(current.get("no_progress_repeat_count", 0) or 0),
            }
            debug_logger.supervisor_final(
                final_response=str(current.get("final_response") or ""),
                stop_reason=str(current.get("stop_reason") or ""),
                budgets=budgets,
                trace_length=len(trace),
            )
        except Exception:
            logger.debug("Failed to log supervisor_final to debug_logger", exc_info=True)

        return current


async def run_supervisor(state: BaseState, config: Optional[SupervisorConfig] = None) -> BaseState:
    """
    Convenience entry point used by QueryOrchestrator.

    This keeps the public API small while still allowing tests to construct
    a ReactSupervisor directly if needed.
    """
    supervisor = ReactSupervisor(config=config)
    return await supervisor.run(state)


def _select_initial_tool(state: BaseState, last_tool_name: Optional[ToolName]) -> Optional[ToolName]:
    """
    Initial entry decision for supervisor.

    - If intent is missing, start with interpret_query.
    - If intent is present but no relevant tables, prefer discovery.
    - Otherwise, move toward SQL planning and validation.
    """
    if last_tool_name:
        return last_tool_name

    intent = state.get("intent") or {}
    operation = intent.get("operation")

    if not intent:
        return "interpret_query"

    if operation == "schema_query":
        # Schema queries typically need discovery then answer.
        if not state.get("relevant_tables"):
            return "discover_schema"
        return "finalize_answer"

    if operation == "health_check":
        # Health checks can go directly to final answer.
        return "finalize_answer"

    # Default data query path.
    if not state.get("relevant_tables"):
        return "discover_schema"
    if not (state.get("sql_query") or "").strip():
        return "plan_sql"
    if not (state.get("validation_result") or {}):
        return "validate_sql"
    if not (state.get("exec_result") or {}):
        return "execute_sql"
    if not state.get("final_response"):
        return "evaluate_result"

    return "finalize_answer"


def _select_next_tool(state: BaseState, last_tool_name: Optional[ToolName]) -> Optional[ToolName]:
    """
    Supervisor policy for choosing the next tool based on the last tool,
    the progress signal, and suggested_next_actions.
    """
    if _is_terminal(state, last_tool_name):
        return "__STOP__"

    intent = state.get("intent") or {}
    operation = intent.get("operation")
    progress: ProgressSignal = state.get("progress_signal") or "neutral"
    suggested: List[str] = list(state.get("suggested_next_actions") or [])

    # After finalize_answer we are done.
    if last_tool_name == "finalize_answer":
        return "__STOP__"

    # Operation-specific routing from interpret_query
    if last_tool_name == "interpret_query":
        if operation == "schema_query":
            return "discover_schema"
        if operation == "health_check":
            return "finalize_answer"
        return "discover_schema"

    if last_tool_name == "discover_schema":
        # If discovery did not find any tables, either rediscover or clarify/stop.
        if not state.get("relevant_tables"):
            if "rediscover" in suggested:
                return "discover_schema"
            if "clarify" in suggested:
                return "finalize_answer"
            return "finalize_answer"
        return "plan_sql"

    if last_tool_name == "plan_sql":
        sql_query = (state.get("sql_query") or "").strip()
        if not sql_query:
            # On repeated failures, consider rediscovery or clarification.
            if "rediscover" in suggested:
                return "discover_schema"
            if "clarify" in suggested:
                return "finalize_answer"
            return "plan_sql"
        return "validate_sql"

    if last_tool_name == "validate_sql":
        validation = state.get("validation_result") or {}
        is_valid = bool(validation.get("is_valid", False))
        if is_valid:
            return "execute_sql"
        # Invalid SQL: supervisor should follow suggested actions.
        if "replan" in suggested:
            return "plan_sql"
        if "rediscover" in suggested:
            return "discover_schema"
        if "clarify" in suggested:
            return "finalize_answer"
        return "plan_sql"

    if last_tool_name == "execute_sql":
        # After execution, always evaluate results before answering.
        return "evaluate_result"

    if last_tool_name == "evaluate_result":
        validation = state.get("validation_result") or {}
        retry_action = (validation.get("retry_action") or "accept").lower()
        if retry_action == "accept":
            return "finalize_answer"
        if retry_action == "ask_user":
            return "finalize_answer"
        if retry_action == "try_next_candidate":
            # Prefer rediscovery of alternative candidates.
            return "discover_schema"
        if retry_action in ("replan_with_aggregation", "replan_with_filter"):
            return "plan_sql"
        # Conservative default.
        if progress == "positive":
            return "finalize_answer"
        if "replan" in suggested:
            return "plan_sql"
        if "rediscover" in suggested:
            return "discover_schema"
        if "clarify" in suggested:
            return "finalize_answer"
        return "finalize_answer"

    # Fallback for other tools (or unknown last_tool_name).
    return _select_initial_tool(state, last_tool_name)


def _is_terminal(state: BaseState, last_tool_name: Optional[ToolName]) -> bool:
    """
    Determine whether the supervisor should consider the state terminal.
    """
    if last_tool_name == "finalize_answer" and state.get("final_response"):
        return True

    stop_reason = state.get("stop_reason")
    if stop_reason in {"success", "clarify", "budget_exhausted", "fatal_error"}:
        return True

    # If a final response already exists and no further suggested actions, treat as terminal.
    if state.get("final_response") and not state.get("suggested_next_actions"):
        return True

    return False


async def _invoke_tool(tool_name: ToolName, state: BaseState) -> BaseState:
    """
    Dispatch to the appropriate capability tool implementation.
    """
    if tool_name == "interpret_query":
        return await capability_tools.interpret_query_tool(state)
    if tool_name == "discover_schema":
        return await capability_tools.discover_schema_tool(state)
    if tool_name == "plan_sql":
        return await capability_tools.plan_sql_tool(state)
    if tool_name == "validate_sql":
        return await capability_tools.validate_sql_tool(state)
    if tool_name == "execute_sql":
        return await capability_tools.execute_sql_tool(state)
    if tool_name == "evaluate_result":
        return await capability_tools.evaluate_result_tool(state)
    if tool_name == "finalize_answer":
        return await capability_tools.finalize_answer_tool(state)

    logger.warning("react_supervisor_unknown_tool: %s", tool_name)
    return state


async def _ensure_final_answer(state: BaseState) -> BaseState:
    """
    Ensure that final_response is populated by running finalize_answer_tool
    when needed.
    """
    if state.get("final_response"):
        return state
    return await _invoke_tool("finalize_answer", state)


def _summarize_inputs(state: BaseState) -> Dict[str, Any]:
    """
    Compute a compact, privacy-preserving digest of the tool inputs.
    """
    intent = state.get("intent") or {}
    return {
        "has_intent": bool(intent),
        "operation": intent.get("operation"),
        "primary_entities": list(intent.get("primary_entities") or [])[:3],
        "has_relevant_tables": bool(state.get("relevant_tables")),
        "sql_present": bool((state.get("sql_query") or "").strip()),
    }


def _summarize_step(
    tool_name: ToolName,
    before_state: BaseState,
    after_state: BaseState,
) -> Tuple[str, str]:
    """
    Produce short, human-readable summaries for supervisor_trace.
    """
    progress: ProgressSignal = after_state.get("progress_signal") or "neutral"
    thought = f"Chose tool '{tool_name}' based on current intent and progress."

    if tool_name == "interpret_query":
        intent = after_state.get("intent") or {}
        op = intent.get("operation") or "unknown"
        thought = f"Parsed user question to determine intent (operation={op})."
    elif tool_name == "discover_schema":
        thought = "Explored catalog to find tables relevant to the question."
    elif tool_name == "plan_sql":
        thought = "Planned SQL query based on discovered tables and intent."
    elif tool_name == "validate_sql":
        thought = "Validated the SQL query for correctness and safety."
    elif tool_name == "execute_sql":
        thought = "Executed the validated SQL query against the database."
    elif tool_name == "evaluate_result":
        thought = "Checked the execution result for semantic correctness."
    elif tool_name == "finalize_answer":
        thought = "Synthesized a final answer for the user."

    # Observation summary based on key fields.
    if tool_name == "interpret_query":
        intent = after_state.get("intent") or {}
        op = intent.get("operation")
        entities = ", ".join(intent.get("primary_entities") or []) or "n/a"
        obs = f"Intent operation={op}, entities={entities} (progress={progress})."
    elif tool_name == "discover_schema":
        tables = after_state.get("relevant_tables") or []
        obs = f"Discovery found {len(tables)} relevant tables (progress={progress})."
    elif tool_name == "plan_sql":
        sql_present = bool((after_state.get("sql_query") or "").strip())
        obs = f"SQL planning {'succeeded' if sql_present else 'did not produce SQL'} (progress={progress})."
    elif tool_name == "validate_sql":
        validation = after_state.get("validation_result") or {}
        is_valid = bool(validation.get("is_valid", False))
        obs = f"SQL validation is_valid={is_valid} (progress={progress})."
    elif tool_name == "execute_sql":
        exec_result = after_state.get("exec_result") or {}
        row_count = exec_result.get("row_count")
        obs = f"Execution ok={bool(exec_result.get('ok'))} rows={row_count} (progress={progress})."
    elif tool_name == "evaluate_result":
        validation = after_state.get("validation_result") or {}
        retry_action = (validation.get("retry_action") or "accept").lower()
        obs = f"Result evaluation retry_action={retry_action} (progress={progress})."
    elif tool_name == "finalize_answer":
        has_answer = bool(after_state.get("final_response"))
        obs = f"Final answer {'present' if has_answer else 'missing'} (progress={progress})."
    else:
        obs = f"Tool '{tool_name}' completed (progress={progress})."

    return thought, obs


def _append_trace_entry(
    state: BaseState,
    step: int,
    tool_name: ToolName,
    thought_summary: str,
    tool_inputs_digest: Dict[str, Any],
    observation_summary: str,
) -> None:
    """
    Append a single structured trace entry to supervisor_trace.
    """
    trace: List[Dict[str, Any]] = list(state.get("supervisor_trace") or [])
    budgets = {
        "supervisor_step_count": int(state.get("supervisor_step_count", 0) or 0),
        "max_supervisor_steps": int(state.get("max_supervisor_steps", 0) or 0),
        "total_llm_calls": int(state.get("total_llm_calls", 0) or 0),
        "max_llm_calls": int(state.get("max_llm_calls", 0) or 0),
        "no_progress_repeat_count": int(state.get("no_progress_repeat_count", 0) or 0),
    }
    entry = {
        "step": int(step),
        "tool": tool_name,
        "thought_summary": str(thought_summary)[:512],
        "tool_inputs_digest": tool_inputs_digest,
        "observation_summary": str(observation_summary)[:512],
        "progress_signal": state.get("progress_signal"),
        "budgets": budgets,
    }
    trace.append(entry)
    state["supervisor_trace"] = trace

    try:
        debug_logger.supervisor_step(
            step=entry["step"],
            tool=entry["tool"],
            thought_summary=entry["thought_summary"],
            observation_summary=entry["observation_summary"],
            progress_signal=entry["progress_signal"],
            suggested_next_actions=list(state.get("suggested_next_actions") or []),
            budgets=budgets,
        )
    except Exception:
        # Debug logging must never disrupt supervisor execution.
        logger.debug("Failed to log supervisor_step to debug_logger", exc_info=True)


def _normalize_stop_reason(state: BaseState) -> None:
    """
    Map internal stop conditions to a small, stable set of stop reasons.
    """
    reason = state.get("stop_reason")
    if reason in {"success", "clarify", "budget_exhausted", "fatal_error"}:
        return

    error_info = state.get("error_info") or {}
    intent = state.get("intent") or {}
    op = (intent.get("operation") or "").lower()

    # Budget-related stop reasons.
    if reason and "budget" in str(reason).lower():
        state["stop_reason"] = "budget_exhausted"
        return

    if error_info:
        err_type = str(error_info.get("type") or "").upper()
        if "BUDGET" in err_type:
            state["stop_reason"] = "budget_exhausted"
        else:
            state["stop_reason"] = "fatal_error"
        return

    if op == "clarify" or intent.get("needs_clarification"):
        state["stop_reason"] = "clarify"
        return

    # Default to success when we have a final answer and no errors.
    if state.get("final_response"):
        state["stop_reason"] = "success"
        return

    # Conservative fallback: treat as fatal_error.
    state["stop_reason"] = "fatal_error"


def build_supervisor_graph():
    graph = StateGraph(BaseState)

    async def supervisor_node(state: BaseState) -> BaseState:
        config = SupervisorConfig()
        return await run_supervisor(state, config=config)

    graph.add_node("react_supervisor", supervisor_node)
    graph.set_entry_point("react_supervisor")
    graph.add_edge("react_supervisor", END)
    return graph.compile()
