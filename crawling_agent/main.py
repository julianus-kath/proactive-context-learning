"""
Main entry point for the Crawling Agent.
Handles GUI input and controls the agent execution.
"""
import argparse
import json
import os
import sys
import uuid
from typing import Dict, Any, Optional

from crawling_agent.translator.query_translator import QueryTranslator
from crawling_agent.controller.crawling_controller import CrawlingAgentController
from crawling_agent.models.task_instruction import TaskInstruction
from crawling_agent.utils.logger import get_logger


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Crawling Agent for data fusion")
    
    parser.add_argument(
        "--query", "-q",
        type=str,
        help="Natural language query to process"
    )
    
    parser.add_argument(
        "--input-file", "-i",
        type=str,
        help="Path to a JSON file containing the query"
    )
    
    parser.add_argument(
        "--output-file", "-o",
        type=str,
        help="Path to save the output JSON results"
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Path to the configuration file"
    )
    
    parser.add_argument(
        "--mock", "-m",
        action="store_true",
        help="Run in mock mode without real database connections"
    )
    
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug logging"
    )
    
    return parser.parse_args()


def setup_environment(args):
    """Set up environment variables based on command line arguments."""
    if args.debug:
        os.environ["CRAWLING_AGENT_LOG_LEVEL"] = "DEBUG"
    
    # Other environment setup can be done here


def get_query_from_input(args) -> Optional[str]:
    """
    Get the query from command line arguments or input file.
    
    Args:
        args: Command line arguments
        
    Returns:
        The query string or None if not provided
    """
    if args.query:
        return args.query
    
    if args.input_file:
        try:
            with open(args.input_file, 'r') as f:
                data = json.load(f)
                return data.get("query")
        except Exception as e:
            print(f"Error reading input file: {str(e)}")
            return None
    
    return None


def save_results(results: Dict[str, Any], output_file: Optional[str] = None) -> None:
    """
    Save results to a file or print to stdout.
    
    Args:
        results: The results to save
        output_file: Path to the output file (optional)
    """
    if output_file:
        try:
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Results saved to {output_file}")
        except Exception as e:
            print(f"Error saving results: {str(e)}")
            print(json.dumps(results, indent=2))
    else:
        print(json.dumps(results, indent=2))


def main():
    """Main entry point for the Crawling Agent."""
    args = parse_args()
    setup_environment(args)
    
    # Print to stdout for debugging
    print("Starting Crawling Agent")
    
    logger = get_logger(__name__)
    logger.info("Starting Crawling Agent")
    
    # Get the query
    query = get_query_from_input(args)
    if not query:
        logger.error("No query provided. Use --query or --input-file")
        sys.exit(1)
    
    try:
        # Initialize components
        translator = QueryTranslator(use_mock=True)  # Always use mock for now
        controller = CrawlingAgentController(
            config_path=args.config,
            mock_mode=args.mock
        )
        
        # Translate the query
        logger.info(f"Translating query: {query}")
        task_instruction = translator.translate(query)
        
        # Execute the task
        logger.info(f"Executing task: {task_instruction.task_id}")
        results = controller.execute_task(task_instruction)
        
        # Save or print the results
        save_results(results, args.output_file)
        
        logger.info("Crawling Agent execution completed successfully")
        return 0
        
    except Exception as e:
        logger.error(f"Error in Crawling Agent: {str(e)}")
        logger.exception(e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
