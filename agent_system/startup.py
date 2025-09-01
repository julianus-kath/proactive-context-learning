"""
Startup script for the multi-agent system with MCP server integration.

This script handles the startup process, including MCP server health checks,
configuration validation, and agent system initialization.
"""

import os
import sys
import time
import logging
import asyncio
import subprocess
from typing import Optional, Dict, Any
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agent_system.config import get_config, setup_logging, get_mcp_config
from agent_system.mcp_client import create_mcp_client
from agent_system.mcp_sql_agent import test_mcp_connection
from agent_system.agent_supervisor import create_multi_agent_system

logger = logging.getLogger(__name__)


class AgentSystemStartup:
    """
    Manages the startup process for the multi-agent system.
    
    This class handles MCP server health checks, configuration validation,
    and provides different startup modes (development, production, Docker).
    """
    
    def __init__(self):
        """Initialize the startup manager."""
        self.config = get_config()
        self.mcp_config = get_mcp_config()
        self.agent_system = None
        
    def check_environment(self) -> Dict[str, Any]:
        """
        Check the environment and dependencies.
        
        Returns:
            Dictionary with environment check results
        """
        results = {
            "openai_api_key": False,
            "mcp_server_reachable": False,
            "database_accessible": False,
            "dependencies_installed": False,
            "errors": []
        }
        
        try:
            # Check OpenAI API key
            if os.getenv("OPENAI_API_KEY"):
                results["openai_api_key"] = True
            else:
                results["errors"].append("OPENAI_API_KEY environment variable not set")
            
            # Check dependencies
            try:
                import langchain
                import langgraph
                import aiohttp
                results["dependencies_installed"] = True
            except ImportError as e:
                results["errors"].append(f"Missing dependency: {e}")
            
            # Check MCP server
            mcp_test = test_mcp_connection()
            if mcp_test["health_check"]:
                results["mcp_server_reachable"] = True
            else:
                results["errors"].extend(mcp_test["errors"])
            
            if mcp_test["query_execution"]:
                results["database_accessible"] = True
            
        except Exception as e:
            results["errors"].append(f"Environment check failed: {str(e)}")
        
        return results
    
    def wait_for_mcp_server(self, max_wait: int = 120, check_interval: int = 5) -> bool:
        """
        Wait for MCP server to become available.
        
        Args:
            max_wait: Maximum time to wait in seconds
            check_interval: Time between checks in seconds
            
        Returns:
            True if server becomes available, False otherwise
        """
        logger.info(f"Waiting for MCP server at {self.mcp_config.url}...")
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                client = create_mcp_client(
                    server_url=self.mcp_config.url,
                    api_key=self.mcp_config.api_key,
                    timeout=10,
                    sync=True
                )
                
                health_response = client.health_check()
                if health_response.success:
                    logger.info("MCP server is available!")
                    return True
                    
            except Exception as e:
                logger.debug(f"MCP server not ready: {e}")
            
            logger.info(f"MCP server not ready, waiting {check_interval}s...")
            time.sleep(check_interval)
        
        logger.error(f"MCP server did not become available within {max_wait} seconds")
        return False
    
    def start_mcp_server_docker(self) -> bool:
        """
        Start MCP server using Docker Compose.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Starting MCP server with Docker Compose...")
            
            # Check if docker-compose is available
            result = subprocess.run(
                ["docker-compose", "--version"],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error("Docker Compose not available")
                return False
            
            # Start the services
            compose_file = project_root / "docker-compose.yml"
            if not compose_file.exists():
                logger.error("docker-compose.yml not found")
                return False
            
            result = subprocess.run(
                ["docker-compose", "-f", str(compose_file), "up", "-d"],
                capture_output=True,
                text=True,
                cwd=project_root
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to start Docker services: {result.stderr}")
                return False
            
            logger.info("Docker services started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start MCP server with Docker: {e}")
            return False
    
    def initialize_agent_system(self) -> bool:
        """
        Initialize the multi-agent system.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Initializing multi-agent system...")
            self.agent_system = create_multi_agent_system()
            logger.info("Multi-agent system initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize agent system: {e}")
            return False
    
    def run_interactive_mode(self):
        """Run the agent system in interactive mode."""
        if not self.agent_system:
            logger.error("Agent system not initialized")
            return
        
        logger.info("Starting interactive mode. Type 'exit' to quit.")
        print("\n" + "="*50)
        print("Multi-Agent System with MCP Database Server")
        print("="*50)
        print("Available commands:")
        print("  - Ask questions about the ERP database")
        print("  - Request data analysis and queries")
        print("  - Type 'exit' to quit")
        print("  - Type 'health' to check MCP server status")
        print("="*50 + "\n")
        
        while True:
            try:
                user_input = input("\nUser: ").strip()
                
                if user_input.lower() == "exit":
                    break
                
                if user_input.lower() == "health":
                    # Check MCP server health
                    test_results = test_mcp_connection()
                    if all([test_results["health_check"], test_results["query_execution"]]):
                        print("✅ MCP server is healthy and database is accessible")
                    else:
                        print("❌ MCP server issues detected:")
                        for error in test_results["errors"]:
                            print(f"  - {error}")
                    continue
                
                if not user_input:
                    continue
                
                # Process the user input
                result = self.agent_system.invoke(
                    {"messages": [{"role": "user", "content": user_input}]}
                )
                
                # Print the final response
                final_message = result["messages"][-1]
                print(f"\nAgent: {final_message['content']}")
                
            except KeyboardInterrupt:
                print("\n\nExiting...")
                break
            except Exception as e:
                logger.error(f"Error processing user input: {e}")
                print(f"Error: {e}")
    
    def startup(self, mode: str = "development") -> bool:
        """
        Main startup process.
        
        Args:
            mode: Startup mode ('development', 'production', 'docker')
            
        Returns:
            True if startup successful, False otherwise
        """
        logger.info(f"Starting multi-agent system in {mode} mode...")
        
        # Setup logging
        setup_logging()
        
        # Check environment
        env_check = self.check_environment()
        
        if not env_check["openai_api_key"]:
            logger.error("OpenAI API key is required. Please set OPENAI_API_KEY environment variable.")
            return False
        
        if not env_check["dependencies_installed"]:
            logger.error("Missing dependencies. Please run: pip install -r requirements.txt")
            return False
        
        # Handle different startup modes
        if mode == "docker":
            # Start MCP server with Docker
            if not self.start_mcp_server_docker():
                logger.error("Failed to start MCP server with Docker")
                return False
        
        # Wait for MCP server to be available
        if not self.wait_for_mcp_server():
            logger.error("MCP server is not available")
            if mode != "docker":
                logger.info("Try starting the MCP server manually:")
                logger.info("  cd mcp_server && python start_server.py")
                logger.info("Or use Docker mode:")
                logger.info("  python startup.py --mode docker")
            return False
        
        # Initialize agent system
        if not self.initialize_agent_system():
            logger.error("Failed to initialize agent system")
            return False
        
        logger.info("Multi-agent system startup completed successfully!")
        return True


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Multi-Agent System Startup")
    parser.add_argument(
        "--mode",
        choices=["development", "production", "docker"],
        default="development",
        help="Startup mode"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive mode after startup"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check environment and exit"
    )
    
    args = parser.parse_args()
    
    startup_manager = AgentSystemStartup()
    
    if args.check_only:
        # Only check environment
        env_check = startup_manager.check_environment()
        print("Environment Check Results:")
        for key, value in env_check.items():
            if key != "errors":
                status = "✅" if value else "❌"
                print(f"  {status} {key.replace('_', ' ').title()}: {value}")
        
        if env_check["errors"]:
            print("\nErrors:")
            for error in env_check["errors"]:
                print(f"  - {error}")
        
        return 0 if all(v for k, v in env_check.items() if k != "errors") else 1
    
    # Full startup
    success = startup_manager.startup(args.mode)
    
    if not success:
        logger.error("Startup failed")
        return 1
    
    if args.interactive:
        startup_manager.run_interactive_mode()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())