"""
Interactive test script for the multi-agent system.
Can be run in terminal mode or called with a single query (useful for n8n integration).

Usage:
    # Interactive mode
    python -m agent_system.interactive_test
    
    # Single query mode (for n8n)
    python -m agent_system.interactive_test "Show me the top 5 customers by sales"
"""

import os
import sys
import getpass
import json

# Add the parent directory to the path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Set OpenAI API key if not already set
if not os.environ.get("OPENAI_API_KEY"):
    # Only prompt for API key in interactive mode
    if len(sys.argv) <= 1:
        os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter your OpenAI API key: ")
    else:
        print("Error: OPENAI_API_KEY environment variable not set.")
        sys.exit(1)

# Check if the database exists and generate it if needed
from agent_system.generate_data import check_database_exists, generate_synthetic_data

if not check_database_exists():
    print("Database does not exist. Generating synthetic data...")
    generate_synthetic_data()
else:
    # Only print this in interactive mode
    if len(sys.argv) <= 1:
        print("Database exists. Skipping data generation.")

# Import the multi-agent system
from agent_system.agent_supervisor import create_multi_agent_system

def process_query(query, agent_system=None):
    """
    Process a single query and return the result.
    
    Args:
        query: The query to process
        agent_system: Optional pre-created agent system
        
    Returns:
        The response from the agent
    """
    # Create agent system if not provided
    if agent_system is None:
        agent_system = create_multi_agent_system()
    
    # Process the query
    result = agent_system.invoke(
        {"messages": [{"role": "user", "content": query}]}
    )
    
    # Return the final response
    final_message = result["messages"][-1]
    return final_message['content']

def run_example_query(agent_system, query):
    """
    Run an example query and print the results.
    
    Args:
        agent_system: The multi-agent system
        query: The query to run
    """
    print(f"\n\n=== Running query: {query} ===\n")
    
    # Process the query
    response = process_query(query, agent_system)
    
    # Print the response
    print(f"\nAgent: {response}")
    print("\n" + "="*80 + "\n")

def main():
    """
    Run the interactive test or process a single query.
    """
    # Check if a query was provided as a command-line argument
    if len(sys.argv) > 1:
        # Single query mode (for n8n integration)
        query = sys.argv[1]
        try:
            response = process_query(query)
            print(response)
        except Exception as e:
            print(f"Error processing query: {str(e)}")
            sys.exit(1)
        return
    
    # Interactive mode
    print("Creating multi-agent system...")
    agent_system = create_multi_agent_system()
    print("Multi-agent system created.")
    
    # Example 1: Get Database Schema
    query1 = "What tables are in the ERP database and what information do they contain?"
    run_example_query(agent_system, query1)
    
    # Example 2: Query Customer Data
    query2 = "Show me the top 5 customers by total sales amount"
    run_example_query(agent_system, query2)
    
    # Example 3: Complex Query Across Multiple Tables
    query3 = "Find the top 3 products by sales quantity and show their current stock levels in the warehouse"
    run_example_query(agent_system, query3)
    
    # Example 4: Business Analysis Query
    query4 = "What is the monthly sales trend for the past year? Show total sales amount by month."
    run_example_query(agent_system, query4)
    
    # Interactive mode
    print("\nEntering interactive mode. Type 'exit' to quit.")
    
    while True:
        user_input = input("\nEnter your query: ")
        
        if user_input.lower() == "exit":
            break
        
        # Process the user input
        response = process_query(user_input, agent_system)
        print(f"\nAgent: {response}")

if __name__ == "__main__":
    main()