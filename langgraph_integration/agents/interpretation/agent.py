"""
InterpretationAgent - Follow-up interpreter over prior results (no DB access).

Purpose:
- Take the last execution result (rows/columns/tables/sql) and the user's follow-up
  question, then produce a concise, user-friendly interpretation without issuing
  any new database queries.

Inputs (from state):
- user_input: current user follow-up question
- previous_exec_result: dict with { ok, rows, row_count, columns?, truncated? }
- previous_sql: last executed SQL (optional)
- previous_sources: list of source tables/views (optional)

Output:
- final_response: concise answer based solely on provided rows
"""

import json
import logging
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph_integration.contracts.state import BaseState

logger = logging.getLogger(__name__)


class InterpretationAgent:
    def __init__(self, llm_model: str = "gpt-4o", llm_temp: float = 0.0):
        self.llm = ChatOpenAI(model=llm_model, temperature=llm_temp)

    def build_subgraph(self) -> StateGraph:
        graph = StateGraph(BaseState)
        graph.add_node("interpret", self._interpret_node)
        graph.set_entry_point("interpret")
        graph.add_edge("interpret", END)
        return graph.compile()

    async def _interpret_node(self, state: BaseState) -> BaseState:
        user_input = state.get("user_input", "")
        prev_exec = state.get("previous_exec_result") or state.get("exec_result") or {}
        prev_sql = state.get("previous_sql", state.get("sql_query", ""))
        prev_sources = state.get("previous_sources", [])

        if not isinstance(prev_exec, dict) or not prev_exec.get("ok"):
            state["final_response"] = (
                "No prior results available to interpret. Please run a query first."
            )
            return state

        rows = prev_exec.get("rows") or prev_exec.get("data") or []
        # Compact rows preview to keep prompts small
        preview = rows[:50] if isinstance(rows, list) else []
        try:
            rows_json = json.dumps(preview, ensure_ascii=False)
        except Exception:
            rows_json = "[]"

        tables_str = ", ".join(prev_sources) if prev_sources else "(unknown)"

        prompt = f"""
You are an interpreter of tabular query results. Do not run any new queries.
Answer the user's follow-up based ONLY on the provided rows JSON.

Rules:
- Keep the answer to 1-3 sentences, concise and direct.
- If the user asks to sort/filter/summarize, do it logically from the rows.
- If insufficient data to answer, state exactly what's missing (still keep it concise).
- Always cite the table(s) used when available.

User question:
{user_input}

Tables: {tables_str}
Last SQL: {prev_sql}
Rows (first up to 50):
```json
{rows_json}
```

Provide only the final answer, no explanations.
"""

        try:
            response = await self.llm.ainvoke(prompt)
            text = (response.content or "").strip()
            # Append tiny appendix with tables
            if tables_str and tables_str != "(unknown)":
                text += f"\n\nTables: {tables_str}"
            state["final_response"] = text
            return state
        except Exception as e:
            logger.error(f"InterpretationAgent failed: {e}")
            state["final_response"] = (
                "I couldn't interpret the previous results due to an internal error."
            )
            return state


