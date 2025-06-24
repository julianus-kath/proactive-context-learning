"""
Script to run the example client.
"""
import asyncio
import sys
import time

from crawling_agent.example_client import main as run_example_client


def main():
    """Run the example client."""
    print("Running example client...")
    print("Make sure all servers are running before continuing.")
    print("You can start the servers with: python -m crawling_agent.run_servers")
    print()
    
    # Wait for user confirmation
    input("Press Enter to continue...")
    
    # Run the example client
    asyncio.run(run_example_client())


if __name__ == "__main__":
    main()