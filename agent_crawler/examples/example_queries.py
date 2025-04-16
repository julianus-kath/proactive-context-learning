"""
Example queries for the Agent Crawler.
"""

import os
import sys
from pathlib import Path

# Add the parent directory to the path so we can import the agent_crawler package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from agent_crawler.agent import DataCrawlerAgent


# Example queries from the thesis
EXAMPLE_QUERIES = [
    "Which customers in the DACH region have not been contacted but have an outstanding invoice?",
    "Show me all customers in Germany who have an outstanding invoice over 90 days.",
    "Which 10 customers placed the highest order volume last year, and do any of them lack assigned account managers in the CRM?",
    "What products have received negative feedback in the last month but continue to sell well?",
    "Which sales representatives have the highest customer satisfaction ratings but below-average sales numbers?",
    "Show me the supply chain path for product X, from supplier to warehouse to distribution center.",
    "Which customers have viewed product Y multiple times but never purchased it?",
    "What are the common characteristics of our top 20 customers by revenue?",
    "Which employees collaborate frequently according to the organizational network but work in different departments?",
    "What products are frequently purchased together with product Z, and how has this pattern changed over the last quarter?"
]


def main():
    """Run example queries."""
    # Check if OpenAI API key is set
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        print("Error: OPENAI_API_KEY environment variable not set.")
        print("This script requires an OpenAI API key to run.")
        return 1
    
    # Initialize the agent
    agent = DataCrawlerAgent(openai_api_key=openai_api_key)
    
    try:
        print("Agent Crawler Example Queries")
        print("-----------------------------")
        print("")
        
        # Let the user select a query
        print("Available queries:")
        for i, query in enumerate(EXAMPLE_QUERIES):
            print(f"{i+1}. {query}")
        print("")
        
        while True:
            try:
                selection = input("Enter query number (or 'q' to quit): ")
                if selection.lower() in ['q', 'quit', 'exit']:
                    break
                
                query_index = int(selection) - 1
                if query_index < 0 or query_index >= len(EXAMPLE_QUERIES):
                    print(f"Invalid selection. Please enter a number between 1 and {len(EXAMPLE_QUERIES)}.")
                    continue
                
                # Process the selected query
                question = EXAMPLE_QUERIES[query_index]
                print(f"\nProcessing query: {question}")
                print("This may take a moment...\n")
                
                user_query = agent.process_query(question)
                
                # Print the query plan
                print("Query Plan:")
                print(f"Data Sources: {', '.join(user_query.query_plan.data_sources)}")
                
                if user_query.query_plan.sql_query:
                    print("\nSQL Query:")
                    print(user_query.query_plan.sql_query)
                
                if user_query.query_plan.document_queries:
                    print("\nDocument Queries:")
                    for i, query in enumerate(user_query.query_plan.document_queries):
                        print(f"Query {i+1}: {query}")
                
                if user_query.query_plan.graph_queries:
                    print("\nGraph Queries:")
                    for i, query in enumerate(user_query.query_plan.graph_queries):
                        print(f"Query {i+1}: {query}")
                
                # Print the answer
                print("\nAnswer:")
                print(user_query.results.answer)
                print("\n" + "-" * 80 + "\n")
            except ValueError:
                print("Invalid input. Please enter a number.")
            except Exception as e:
                print(f"Error processing query: {e}")
    finally:
        # Close the agent
        agent.close()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())