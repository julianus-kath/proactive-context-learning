"""
Example of using the Agent Crawler for multi-source data fusion.
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
    """Run a multi-source query example."""
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
        # Example: Customer 360 View - Combining data from multiple sources
        print("Example: Customer 360 View")
        print("---------------------------")
        
        # Create a query plan that combines data from all three sources
        query_plan = QueryPlan(
            data_sources=[DataSourceType.SQL, DataSourceType.DOCUMENT, DataSourceType.GRAPH],
            sql_query="""
                SELECT 
                    c.customer_id, 
                    c.name, 
                    c.industry, 
                    c.company_size,
                    c.country,
                    COUNT(s.sale_id) as total_purchases,
                    SUM(s.total_amount) as total_spent
                FROM 
                    customers c
                LEFT JOIN 
                    sales s ON c.customer_id = s.customer_id
                WHERE 
                    c.customer_id = 1
                GROUP BY 
                    c.customer_id
            """,
            document_queries=[
                {
                    "collection": "customer_feedback",
                    "type": "query",
                    "query": {"customer_id": 1}
                },
                {
                    "collection": "support_tickets",
                    "type": "query",
                    "query": {"customer_id": 1}
                }
            ],
            graph_queries=[
                {
                    "network": "customer_product_network",
                    "type": "get_neighbors",
                    "params": {
                        "node_id": "customer-1",
                        "direction": "outgoing"
                    }
                }
            ],
            reasoning="Create a comprehensive view of customer #1 by combining their basic information, purchase history, feedback, support tickets, and product interactions."
        )
        
        # Execute the query plan
        results = agent.execute_query_plan(query_plan)
        
        # Print the results
        print(f"Found {len(results)} result sets from different data sources")
        
        # Process SQL results (basic customer info and purchase history)
        sql_results = next((r for r in results if r.source == DataSourceType.SQL), None)
        if sql_results and sql_results.data:
            customer_info = sql_results.data[0]
            print("\nCustomer Information:")
            print(f"ID: {customer_info.get('customer_id')}")
            print(f"Name: {customer_info.get('name')}")
            print(f"Industry: {customer_info.get('industry')}")
            print(f"Size: {customer_info.get('company_size')}")
            print(f"Country: {customer_info.get('country')}")
            print(f"Total Purchases: {customer_info.get('total_purchases')}")
            print(f"Total Spent: ${customer_info.get('total_spent'):.2f}")
        
        # Process document results (feedback and support tickets)
        doc_results = [r for r in results if r.source == DataSourceType.DOCUMENT]
        
        # Process feedback
        feedback_result = next((r for r in doc_results if r.metadata.get('collection') == 'customer_feedback'), None)
        if feedback_result:
            feedback = feedback_result.data
            print(f"\nCustomer Feedback ({len(feedback)} records):")
            for i, fb in enumerate(feedback[:3]):  # Show up to 3 feedback records
                print(f"  {i+1}. Rating: {fb.get('rating')}/5 - {fb.get('title')}")
                print(f"     Date: {fb.get('feedback_date')}")
                print(f"     Content: {fb.get('content')[:100]}..." if len(fb.get('content', '')) > 100 else f"     Content: {fb.get('content')}")
            
            if len(feedback) > 3:
                print(f"  ... and {len(feedback) - 3} more feedback records")
        
        # Process support tickets
        tickets_result = next((r for r in doc_results if r.metadata.get('collection') == 'support_tickets'), None)
        if tickets_result:
            tickets = tickets_result.data
            print(f"\nSupport Tickets ({len(tickets)} records):")
            for i, ticket in enumerate(tickets[:3]):  # Show up to 3 tickets
                print(f"  {i+1}. Subject: {ticket.get('subject')}")
                print(f"     Status: {ticket.get('status')}")
                print(f"     Created: {ticket.get('created_date')}")
                print(f"     Priority: {ticket.get('priority')}")
            
            if len(tickets) > 3:
                print(f"  ... and {len(tickets) - 3} more support tickets")
        
        # Process graph results (product interactions)
        graph_results = next((r for r in results if r.source == DataSourceType.GRAPH), None)
        if graph_results:
            edges = graph_results.data.get('edges', [])
            nodes = graph_results.data.get('nodes', [])
            
            # Map product IDs to names
            product_names = {}
            for node in nodes:
                if 'product-' in node.get('id', ''):
                    props = node.get('properties', {})
                    product_names[node.get('id')] = props.get('name', 'Unknown Product')
            
            # Group interactions by type
            interactions = {}
            for edge in edges:
                edge_type = edge.get('type', 'UNKNOWN')
                if edge_type not in interactions:
                    interactions[edge_type] = []
                interactions[edge_type].append(edge)
            
            print(f"\nProduct Interactions ({len(edges)} total):")
            for interaction_type, edges in interactions.items():
                print(f"  {interaction_type}: {len(edges)} interactions")
                for i, edge in enumerate(edges[:3]):  # Show up to 3 interactions per type
                    target = edge.get('target')
                    product_name = product_names.get(target, 'Unknown Product')
                    print(f"    - {product_name}")
                
                if len(edges) > 3:
                    print(f"    ... and {len(edges) - 3} more {interaction_type} interactions")
        
        print("\n")
        
        # Example: Natural language query for customer 360 view (requires OpenAI API key)
        if openai_api_key:
            print("Natural Language Query Example")
            print("------------------------------")
            
            # Process a natural language query
            question = "Give me a complete profile of customer #1, including their purchase history, feedback, support tickets, and product interactions."
            print(f"Question: {question}")
            
            user_query = agent.process_query(question)
            
            # Print the answer
            print("\nAnswer:")
            print(user_query.results.answer)
    finally:
        # Close the agent
        agent.close()


if __name__ == "__main__":
    main()