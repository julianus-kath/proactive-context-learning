from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from langgraph.graph import StateGraph, START, END

from .contracts.state import BaseState
from .orchestrator import QueryOrchestrator, create_query_orchestrator


def _normalize_user_input(state: BaseState) -> str:
    value = state.get("user_input") if isinstance(state, dict) else None
    if isinstance(value, str) and value.strip():
        return value
    raise ValueError("user_input is required to run the workflow")


def _normalize_messages(state: BaseState) -> Optional[list]:
    value = state.get("messages") if isinstance(state, dict) else None
    return value if isinstance(value, list) else []


def _normalize_conversation_id(state: BaseState) -> Optional[str]:
    value = state.get("conversation_id") if isinstance(state, dict) else None
    if value is None:
        return None
    return str(value)


def _extract_metadata(state: BaseState) -> Dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    reserved = {"user_input", "messages", "conversation_id"}
    return {k: v for k, v in state.items() if k not in reserved}


def _merge_states(original: BaseState, updates: Optional[Dict[str, Any]]) -> BaseState:
    merged: BaseState = dict(original or {})
    if isinstance(updates, dict):
        merged.update(updates)
    return merged


def _run_sync(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError as exc:
        if "asyncio.run" in str(exc):
            raise RuntimeError("Use await on WorkflowGraph.ainvoke or DatabaseWorkflow.ainvoke inside an event loop") from exc
        raise


class WorkflowGraph:
    def __init__(self, orchestrator: Optional[QueryOrchestrator] = None) -> None:
        self.orchestrator = orchestrator or create_query_orchestrator()
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(BaseState)
        workflow.add_node("react_supervisor", self._supervisor_node)
        workflow.add_edge(START, "react_supervisor")
        workflow.add_edge("react_supervisor", END)
        return workflow.compile()

    async def _supervisor_node(self, state: BaseState) -> BaseState:
        return await self._invoke_supervisor(state or {})

    async def _invoke_supervisor(self, state: BaseState) -> BaseState:
        user_input = _normalize_user_input(state)
        messages = _normalize_messages(state)
        conversation_id = _normalize_conversation_id(state)
        metadata = _extract_metadata(state)
        result = await self.orchestrator.process_query(
            user_input=user_input,
            messages=messages,
            conversation_id=conversation_id,
            metadata=metadata,
        )
        return _merge_states(state, result)

    async def ainvoke(self, state: Optional[BaseState] = None) -> BaseState:
        payload = state or {}
        return await self.graph.ainvoke(payload)

    def invoke(self, state: Optional[BaseState] = None) -> BaseState:
        payload = state or {}
        return _run_sync(self.ainvoke(payload))


class DatabaseWorkflow:
    def __init__(
        self,
        llm_model: str = "gpt-4o",
        llm_temp: float = 0.0,
        max_joins: int = 3,
        max_retries: int = 2,
        row_limit: int = 1000,
        query_timeout_seconds: int = 30,
    ) -> None:
        self.orchestrator = create_query_orchestrator(
            llm_model=llm_model,
            llm_temp=llm_temp,
            max_joins=max_joins,
            max_retries=max_retries,
            row_limit=row_limit,
            query_timeout_seconds=query_timeout_seconds,
        )
        self._graph = WorkflowGraph(self.orchestrator)
        self.workflow = self._graph.graph

    async def ainvoke(self, state: Optional[BaseState] = None) -> BaseState:
        return await self._graph.ainvoke(state or {})

    def invoke(self, state: Optional[BaseState] = None) -> BaseState:
        return self._graph.invoke(state or {})

    async def process_query(
        self,
        user_input: str,
        messages: Optional[Any] = None,
        conversation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_messages = messages if isinstance(messages, list) else []
        return await self.orchestrator.process_query(
            user_input=user_input,
            messages=normalized_messages,
            conversation_id=conversation_id,
            metadata=metadata,
        )


_graph_wrapper: Optional[WorkflowGraph] = None


def _get_graph_wrapper() -> WorkflowGraph:
    global _graph_wrapper
    if _graph_wrapper is None:
        _graph_wrapper = WorkflowGraph()
    return _graph_wrapper


def create_database_workflow(
    llm_model: str = "gpt-4o",
    llm_temp: float = 0.0,
    max_joins: int = 3,
    max_retries: int = 2,
    row_limit: int = 1000,
    query_timeout_seconds: int = 30,
) -> DatabaseWorkflow:
    return DatabaseWorkflow(
        llm_model=llm_model,
        llm_temp=llm_temp,
        max_joins=max_joins,
        max_retries=max_retries,
        row_limit=row_limit,
        query_timeout_seconds=query_timeout_seconds,
    )


def build_graph():
    return _get_graph_wrapper().graph


graph = build_graph()
