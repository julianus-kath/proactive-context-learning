"""
Simple example of using the Agent Crawler.
"""

import os
import sys
import json
from pathlib import Path

# Add the parent directory to the path so we can import the agent_crawler package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from agent_crawler.agent import DataCrawlerAgent
from agent_crawler.schema import QueryPlan, DataSourceType


def main():
    """Run a simple query example."""
    # Check if OpenAI API key is set
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        print("Warning: OPENAI_API_KEY environment variable not set.")
        print("The agent will be initialized without LLM capabilities.")
        print("You can still execute predefined queries, but not natural language queries.")
        print("")
    
    # Initialize the agent
    agent = DataCrawlerAgent(openai_api_key=openai_api_key)
    
    try:
        # Example 1: Execute a predefined SQL query
        print("Example 1: Execute a predefined SQL query")
        print("------------------------------------------")
        
        # Create a query plan
        query_plan = QueryPlan(
            data_sources=[DataSourceType.SQL],
            sql_query="SELECT c.customer_id, c.name, c.country, COUNT(s.sale_id) as sale_count, SUM(s.total_amount) as total_sales "
                      "FROM customers c "
                      "JOIN sales s ON c.customer_id = s.customer_id "
                      "WHERE c.country = 'Germany' "
                      "GROUP BY c.customer_id "
                      "ORDER BY total_sales DESC "
                      "LIMIT 5",
            reasoning="Find the top 5 customers in Germany by total sales"
        )
        
        # Execute the query plan
        results = agent.execute_query_plan(query_plan)
        
        # Print the results
        print(f"Found {len(results)} result sets")
        for i, result in enumerate(results):
            print(f"\nResult {i+1} from {result.source}:")
            print(json.dumps(result.data, indent=2))
        
        print("\n")
        
        # Example 2: Execute a predefined document query
        print("Example 2: Execute a predefined document query")
        print("----------------------------------------------")
        
        # Create a query plan
        query_plan = QueryPlan(
            data_sources=[DataSourceType.DOCUMENT],
            document_queries=[
                {
                    "collection": "customer_feedback",
                    "type": "query",
                    "query": {"rating": 5}
                }
            ],
            reasoning="Find all 5-star customer feedback"
        )
        
        # Execute the query plan
        results = agent.execute_query_plan(query_plan)
        
        # Print the results
        print(f"Found {len(results)} result sets")
        for i, result in enumerate(results):
            print(f"\nResult {i+1} from {result.source}:")
            print(f"Collection: {result.metadata.get('collection')}")
            print(f"Total documents: {len(result.data)}")
            if result.data:
                print("First document:")
                print(json.dumps(result.data[0], indent=2))
        
        print("\n")
        
        # Example 3: Execute a predefined graph query
        print("Example 3: Execute a predefined graph query")
        print("-------------------------------------------")
        
        # Create a query plan
        query_plan = QueryPlan(
            data_sources=[DataSourceType.GRAPH],
            graph_queries=[
                {
                    "network": "employee_network",
                    "type": "get_nodes",
                    "params": {
                        "labels": ["Employee"],
                        "properties": {"department": "Sales"}
                    }
                }
            ],
            reasoning="Find all employees in the Sales department"
        )
        
        # Execute the query plan
        results = agent.execute_query_plan(query_plan)
        
        # Print the results
        print(f"Found {len(results)} result sets")
        for i, result in enumerate(results):
            print(f"\nResult {i+1} from {result.source}:")
            print(f"Network: {result.metadata.get('network')}")
            if "nodes" in result.data:
                print(f"Total nodes: {len(result.data['nodes'])}")
                if result.data["nodes"]:
                    print("First node:")
                    print(json.dumps(result.data["nodes"][0], indent=2))
        
        print("\n")
        
        # Example 4: Natural language query (requires OpenAI API key)
        if openai_api_key:
            print("Example 4: Natural language query")
            print("----------------------------------")
            
            # Process a natural language query
            question = "Which customers in Germany have the highest total sales?"
            print(f"Question: {question}")
            
            user_query = agent.process_query(question)
            
            # Print the query plan
            print("\nQuery Plan:")
            print(f"Data Sources: {', '.join(user_query.query_plan.data_sources)}")
            
            if user_query.query_plan.sql_query:
                print("\nSQL Query:")
                print(user_query.query_plan.sql_query)
            
            # Print the answer
            print("\nAnswer:")
            print(user_query.results.answer)
    finally:
        # Close the agent
        agent.close()


if __name__ == "__main__":
    main()