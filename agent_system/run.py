"""
Script to run the multi-agent system from the command line.
"""

import os
import sys
import getpass

# Check if the database exists and generate it if needed
from agent_system.generate_data import check_database_exists, generate_synthetic_data

if not check_database_exists():
    generate_synthetic_data()

# Check if OpenAI API key is set
if not os.environ.get("OPENAI_API_KEY"):
    api_key = getpass.getpass("Enter your OpenAI API key: ")
    os.environ["OPENAI_API_KEY"] = api_key

# Import the multi-agent system
from agent_system.agent_supervisor import create_multi_agent_system

def main():
    """
    Run the multi-agent system.
    """
    print("Initializing multi-agent system...")
    agent_system = create_multi_agent_system()
    
    print("\nMulti-agent system initialized. Type 'exit' to quit.")
    
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

if __name__ == "__main__":
    main()