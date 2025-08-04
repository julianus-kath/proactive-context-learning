"""
Multi-agent supervisor architecture using LangGraph.

This module implements a supervisor agent that coordinates specialized worker agents
for different data sources, starting with the ERP database.
"""

import os
from typing import Dict, List, Any, Optional, Annotated, Tuple
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, FunctionMessage
from langchain_core.tools import tool, BaseTool, StructuredTool, Tool, InjectedToolCallId
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.types import Command
from langgraph.prebuilt import InjectedState

# Import MCP-enabled SQL agent tools
from agent_system.mcp_sql_agent import run_sql_query, get_table_info, get_database_schema, get_sample_data, check_mcp_server_health


def create_handoff_tool(*, agent_name: str, description: str | None = None):
    """
    Create a tool that hands off control to another agent.
    
    Args:
        agent_name: Name of the agent to hand off to
        description: Description of the tool
        
    Returns:
        Handoff tool
    """
    name = f"transfer_to_{agent_name}"
    description = description or f"Ask {agent_name} for help."

    @tool(name, description=description)
    def handoff_tool(
        state: Annotated[MessagesState, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        tool_message = {
            "role": "tool",
            "content": f"Successfully transferred to {agent_name}",
            "name": name,
            "tool_call_id": tool_call_id,
        }
        return Command(
            goto=agent_name,
            update={**state, "messages": state["messages"] + [tool_message]},
            graph=Command.PARENT,
        )

    return handoff_tool


def create_supervisor_agent():
    """
    Create the supervisor agent that coordinates worker agents.
    
    Returns:
        Supervisor agent
    """
    # Create handoff tools for worker agents
    assign_to_sql_agent = create_handoff_tool(
        agent_name="sql_agent",
        description="Assign task to the SQL agent for querying the ERP database.",
    )
    
    # Create the supervisor agent
    supervisor_agent = create_react_agent(
        model=ChatOpenAI(model="gpt-4o", temperature=0),
        tools=[assign_to_sql_agent],
        prompt=(
            "You are a supervisor agent that coordinates specialized worker agents to help users access and analyze data.\n\n"
            "Currently, you have access to the following agents:\n"
            "- SQL Agent: For querying the ERP database which contains business data like customers, products, sales, etc.\n\n"
            "Your job is to:\n"
            "1. Understand the user's request\n"
            "2. Determine which specialized agent can best handle the request\n"
            "3. Transfer the request to the appropriate agent using the provided tools\n"
            "4. Summarize the results for the user when the worker agent completes its task\n\n"
            "Do not try to answer complex data questions yourself. Instead, delegate to the appropriate specialized agent."
        ),
        name="supervisor",
    )
    
    return supervisor_agent


def create_sql_agent():
    """
    Create the SQL agent for querying the ERP database via MCP server.
    
    Returns:
        SQL agent
    """
    # Create tools for the SQL agent (now using MCP server)
    sql_query_tool = Tool.from_function(
        func=run_sql_query,
        name="run_sql_query",
        description="Run a SQL query against the ERP database via MCP server."
    )
    
    table_info_tool = Tool.from_function(
        func=get_table_info,
        name="get_table_info",
        description="Get information about a specific table or all tables in the ERP database via MCP server."
    )
    
    schema_tool = Tool.from_function(
        func=get_database_schema,
        name="get_database_schema",
        description="Get the complete schema of the ERP database via MCP server."
    )
    
    sample_data_tool = Tool.from_function(
        func=get_sample_data,
        name="get_sample_data",
        description="Get sample data from a specific table in the ERP database via MCP server."
    )
    
    health_check_tool = Tool.from_function(
        func=check_mcp_server_health,
        name="check_mcp_server_health",
        description="Check the health status of the MCP database server."
    )
    
    # Create the SQL agent
    sql_agent = create_react_agent(
        model=ChatOpenAI(model="gpt-4o", temperature=0),
        tools=[sql_query_tool, table_info_tool, schema_tool, sample_data_tool, health_check_tool],
        prompt=(
            "You are a SQL expert agent that helps users query and analyze data from the ERP database via the MCP (Model Context Protocol) server.\n\n"
            "The ERP database contains business data including:\n"
            "- Customers: Information about clients\n"
            "- Products: Details about products in inventory\n"
            "- Sales: Transaction records between customers and products\n"
            "- Suppliers: Information about vendors\n"
            "- Employees: Staff member records\n"
            "- Warehouse: Inventory stock information\n\n"
            "You access the database through a secure MCP server that provides:\n"
            "- Standardized database access\n"
            "- Read-only operations for data safety\n"
            "- Query limits and timeouts for performance\n"
            "- Authentication and security\n\n"
            "Your job is to:\n"
            "1. Help users understand the database schema using get_database_schema\n"
            "2. Write and execute SQL queries using run_sql_query\n"
            "3. Get detailed table information using get_table_info\n"
            "4. Retrieve sample data using get_sample_data\n"
            "5. Check MCP server health if there are connection issues\n"
            "6. Explain the results in a clear, concise manner\n\n"
            "Always check the database schema first if you're unsure about table structures.\n"
            "If you encounter errors, check the MCP server health status."
        ),
        name="sql_agent",
    )
    
    return sql_agent


def create_multi_agent_system():
    """
    Create the multi-agent system with supervisor and worker agents.
    
    Returns:
        Compiled multi-agent graph
    """
    # Create the agents
    supervisor_agent = create_supervisor_agent()
    sql_agent = create_sql_agent()
    
    # Define the multi-agent graph
    workflow = (
        StateGraph(MessagesState)
        .add_node(supervisor_agent, destinations=["sql_agent", END])
        .add_node(sql_agent)
        .add_edge(START, "supervisor")
        # Always return back to the supervisor
        .add_edge("sql_agent", "supervisor")
        .compile()
    )
    
    return workflow


# For direct execution
if __name__ == "__main__":
    # Check if OpenAI API key is set
    if not os.environ.get("OPENAI_API_KEY"):
        print("Please set the OPENAI_API_KEY environment variable.")
        exit(1)
    
    # Create the multi-agent system
    agent_system = create_multi_agent_system()
    
    # Run the agent system
    print("Multi-agent system initialized. Type 'exit' to quit.")
    
    while True:
        user_input = input("\nUser: ")
        
        if user_input.lower() == "exit":
            break
        
        # Process the user input
        result = agent_system.invoke(
            {"messages": [{"role": "user", "content": user_input}]}
        )
        
        # Print the final response
        final_message = result["messages"][-1]
        print(f"\nAgent: {final_message['content']}")