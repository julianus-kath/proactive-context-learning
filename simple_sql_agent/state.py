"""
Minimal state schema for the SQL agent.

Only 10 fields vs 150+ in the old system.
"""

from typing import TypedDict, Optional, List, Dict, Any, Annotated
from langgraph.graph import MessagesState
import operator


class SQLAgentState(MessagesState):
    """
    Minimal state for the SQL agent.

    Extends MessagesState which provides:
    - messages: List of conversation messages (used by ReAct agent)

    Additional fields for SQL workflow:
    """

    # Input
    question: str  # User's natural language question

    # Discovery (populated by tools)
    tables_used: Optional[List[str]]  # Tables identified as relevant
    schema_context: Optional[str]  # Schema snippet for context

    # SQL generation
    sql_query: Optional[str]  # Generated SQL query

    # Execution
    query_result: Optional[Dict[str, Any]]  # Query result data
    row_count: Optional[int]  # Number of rows returned

    # Errors
    error: Optional[str]  # Error message if any

    # Output
    final_answer: Optional[str]  # Natural language answer
