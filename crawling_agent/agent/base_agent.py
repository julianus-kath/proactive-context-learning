"""
Base Agent implementation.

This module provides a base class for agents that can reason across multiple data sources.
"""
import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union

from crawling_agent.llm.base_llm_client import BaseLLMClient


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BaseAgent")


class BaseAgent(ABC):
    """
    Base class for all agents.
    
    This abstract class defines the interface that all agents must implement.
    """
    
    def __init__(
        self,
        llm_client: BaseLLMClient,
        system_prompt: str,
        debug: bool = False,
    ):
        """
        Initialize the base agent.
        
        Args:
            llm_client: The LLM client to use
            system_prompt: The system prompt to use
            debug: Whether to enable debug mode (default: False)
        """
        self.llm_client = llm_client
        self.system_prompt = system_prompt
        self.debug = debug
        self.conversation_history = []
        
        # Add the system message to the conversation history
        self.conversation_history.append({
            "role": "system",
            "content": system_prompt,
        })
        
        logger.info("Initialized base agent")
        if debug:
            logger.setLevel(logging.DEBUG)
            logger.debug("Debug mode enabled")
    
    @abstractmethod
    async def process_query(self, query: str) -> str:
        """
        Process a user query and return a response.
        
        Args:
            query: The user query
            
        Returns:
            The agent's response
        """
        pass
    
    def add_message_to_history(self, role: str, content: str):
        """
        Add a message to the conversation history.
        
        Args:
            role: The role of the message sender (e.g., "user", "assistant")
            content: The content of the message
        """
        self.conversation_history.append({
            "role": role,
            "content": content,
        })
        
        if self.debug:
            logger.debug(f"Added message to history - Role: {role}")
            logger.debug(f"Content: {content}")
    
    def add_tool_result_to_history(self, tool_name: str, result: str):
        """
        Add a tool result to the conversation history.
        
        Args:
            tool_name: The name of the tool
            result: The result of the tool call
        """
        # Find the last assistant message with tool_calls
        assistant_message = None
        tool_call_id = None
        
        # Search backwards through the conversation history
        for i in range(len(self.conversation_history) - 1, -1, -1):
            message = self.conversation_history[i]
            if message.get("role") == "assistant" and "tool_calls" in message:
                assistant_message = message
                # Find the tool call with the matching name
                for tool_call in message["tool_calls"]:
                    if tool_call.get("function", {}).get("name") == tool_name:
                        tool_call_id = tool_call.get("id")
                        break
                break
        
        # If we couldn't find a matching tool call, generate a random ID
        if tool_call_id is None:
            tool_call_id = f"call_{int(time.time())}"
        
        # Add the tool result to the conversation history
        self.conversation_history.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result,
        })
        
        if self.debug:
            logger.debug(f"Added tool result to history - Tool: {tool_name}")
            logger.debug(f"Result: {result}")
    
    def clear_history(self, keep_system_prompt: bool = True):
        """
        Clear the conversation history.
        
        Args:
            keep_system_prompt: Whether to keep the system prompt (default: True)
        """
        if keep_system_prompt and self.conversation_history and self.conversation_history[0]["role"] == "system":
            self.conversation_history = [self.conversation_history[0]]
        else:
            self.conversation_history = []
            # Re-add the system prompt if needed
            if keep_system_prompt:
                self.conversation_history.append({
                    "role": "system",
                    "content": self.system_prompt,
                })
        
        logger.info("Cleared conversation history")
    
    def get_conversation_history(self) -> List[Dict[str, str]]:
        """
        Get the conversation history.
        
        Returns:
            The conversation history as a list of message dictionaries
        """
        return self.conversation_history