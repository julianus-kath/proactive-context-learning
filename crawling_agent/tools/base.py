"""
Base Tool interface and registry for the crawling agent.
"""
from typing import Dict, List, Any, Protocol, Optional, runtime_checkable
import logging

# Configure logging
logger = logging.getLogger(__name__)


@runtime_checkable
class Tool(Protocol):
    """
    Protocol defining the interface for agent tools.
    
    Tools are the primary way for the agent to interact with external systems
    and perform actions.
    """
    
    async def run(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the tool with the given parameters.
        
        Args:
            parameters: Tool-specific parameters
            
        Returns:
            The result of running the tool
        """
        ...
    
    def get_name(self) -> str:
        """
        Get the name of the tool.
        
        Returns:
            The tool name
        """
        ...
    
    def get_description(self) -> str:
        """
        Get a description of the tool.
        
        Returns:
            The tool description
        """
        ...
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for the tool's parameters.
        
        Returns:
            JSON schema for the parameters
        """
        ...


class ToolRegistry:
    """
    Registry for tools available to the agent.
    """
    
    def __init__(self):
        """Initialize the tool registry."""
        self.tools: Dict[str, Tool] = {}
        logger.info("Initialized tool registry")
    
    def register_tool(self, tool: Tool) -> None:
        """
        Register a tool with the registry.
        
        Args:
            tool: The tool to register
        """
        tool_name = tool.get_name()
        self.tools[tool_name] = tool
        logger.info(f"Registered tool: {tool_name}")
    
    def get_tool(self, tool_name: str) -> Optional[Tool]:
        """
        Get a tool by name.
        
        Args:
            tool_name: Name of the tool to get
            
        Returns:
            The tool, or None if not found
        """
        tool = self.tools.get(tool_name)
        if tool is None:
            logger.warning(f"Tool not found: {tool_name}")
        return tool
    
    def get_all_tools(self) -> List[Tool]:
        """
        Get all registered tools.
        
        Returns:
            List of all registered tools
        """
        return list(self.tools.values())
    
    def get_tool_descriptions(self) -> List[Dict[str, Any]]:
        """
        Get descriptions of all registered tools.
        
        Returns:
            List of tool descriptions
        """
        return [
            {
                "name": tool.get_name(),
                "description": tool.get_description(),
                "parameter_schema": tool.get_parameter_schema()
            }
            for tool in self.tools.values()
        ]