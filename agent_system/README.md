# Multi-Agent Supervisor Architecture

This project implements a multi-agent supervisor architecture using LangGraph. The system consists of a supervisor agent that coordinates specialized worker agents for different data sources, starting with an SQL agent for querying the ERP database.

## Architecture

The multi-agent system follows the supervisor architecture pattern:

1. **Supervisor Agent**: Coordinates all worker agents and handles user interactions
2. **SQL Agent**: Specialized agent for querying the ERP database
3. (Future) Additional specialized agents for other data sources

The system uses LangGraph to manage the flow of control between agents, with the supervisor agent delegating tasks to specialized agents and then summarizing their results for the user.

## Components

### SQL Database Connector

The `SQLDatabaseConnector` class provides an interface to the ERP database, allowing the SQL agent to:

- Get the database schema
- Get information about specific tables
- Execute SQL queries

### SQL Agent

The SQL agent is a specialized agent that can:

- Understand the database schema
- Write and execute SQL queries based on user requests
- Explain query results

### Supervisor Agent

The supervisor agent:

- Understands user requests
- Determines which specialized agent can best handle the request
- Transfers the request to the appropriate agent
- Summarizes results for the user

## Usage

### Prerequisites

- Python 3.8+
- OpenAI API key

### Installation

1. Install the required packages:

```bash
pip install -r requirements.txt
```

2. Set your OpenAI API key:

```bash
export OPENAI_API_KEY=your_api_key_here
```

### Running the System

You can run the system directly from the command line:

```bash
python agent_supervisor.py
```

Or you can use the Jupyter notebook for interactive testing:

```bash
jupyter notebook test_agents.ipynb
```

## Example Queries

Here are some example queries you can try:

- "What tables are in the ERP database and what information do they contain?"
- "Show me the top 5 customers by total sales amount"
- "Find the top 3 products by sales quantity and show their current stock levels in the warehouse"
- "What is the monthly sales trend for the past year? Show total sales amount by month."

## Extending the System

To add new specialized agents:

1. Create a new module for the agent with its tools and functionality
2. Add a new handoff tool in the supervisor agent
3. Add the new agent to the multi-agent graph in `create_multi_agent_system()`

## Future Work

- Add document store agent for accessing unstructured data
- Add graph database agent for accessing relationship data
- Implement memory for persistent context across queries
- Add visualization capabilities for query results