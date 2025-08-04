"""
Simple test script for the Crawling Agent.
"""
import sys
import json
from crawling_agent.translator.query_translator import QueryTranslator
from crawling_agent.controller.crawling_controller import CrawlingAgentController

def main():
    """Test the Crawling Agent with a simple query."""
    print("Testing Crawling Agent...")
    
    # Initialize components
    translator = QueryTranslator(use_mock=False)
    controller = CrawlingAgentController(mock_mode=False)
    
    # Test query
    query = "Find all products with price greater than 100"
    print(f"Query: {query}")
    
    # Translate the query
    task_instruction = translator.translate(query)
    print(f"Task ID: {task_instruction.task_id}")
    print(f"Description: {task_instruction.description}")
    
    # Execute the task
    results = controller.execute_task(task_instruction)
    
    # Print the results
    print("\nResults:")
    print(json.dumps(results, indent=2))
    
    return 0

if __name__ == "__main__":
    sys.exit(main())