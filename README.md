# Master Thesis Project: Multi-Agent System for Data Fusion

This repository contains the implementation of a multi-agent system for data fusion across heterogeneous data sources, including relational databases, document stores, and graph databases.

## Project Structure

- **agent_system/**: Multi-agent supervisor architecture using LangGraph
  - Supervisor agent that coordinates specialized worker agents
  - SQL agent for querying the ERP database
  - (Future) Document store agent and graph database agent
  
- **synthetic_data_service/**: Synthetic data generation for testing
  - Relational data models (customers, products, sales, etc.)
  - (Future) Document store and graph database data

## Setup

### Prerequisites

- Python 3.8+
- OpenAI API key

### Installation

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set your OpenAI API key:
   ```bash
   export OPENAI_API_KEY=your_api_key_here
   ```

## Usage

### Generate Synthetic Data

```bash
python -m agent_system.generate_data
```

### Run the Multi-Agent System

```bash
python -m agent_system.run
```

### Interactive Testing with Jupyter Notebook

```bash
jupyter notebook agent_system/test_agents.ipynb
```

## Example Queries

- "What tables are in the ERP database and what information do they contain?"
- "Show me the top 5 customers by total sales amount"
- "Find the top 3 products by sales quantity and show their current stock levels in the warehouse"
- "What is the monthly sales trend for the past year? Show total sales amount by month."

## Future Work

- Add document store agent for accessing unstructured data
- Add graph database agent for accessing relationship data
- Implement memory for persistent context across queries
- Add visualization capabilities for query results