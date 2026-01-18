"""
Simple SQL Agent - A minimal text-to-SQL agent for ERP systems.

This module provides a single ReAct agent with 4 tools for querying
an MSSQL database via natural language.
"""

from simple_sql_agent.agent import create_sql_agent, SQLAgentGraph

__all__ = ["create_sql_agent", "SQLAgentGraph"]
