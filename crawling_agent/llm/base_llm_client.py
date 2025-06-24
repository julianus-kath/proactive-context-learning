"""
Base LLM Client implementation.

This module provides a base class for LLM clients that can be used by the agent.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union


class BaseLLMClient(ABC):
    """
    Base class for all LLM clients.
    
    This abstract class defines the interface that all LLM clients must implement.
    """
    
    @abstractmethod
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate a response from the LLM.
        
        Args:
            messages: A list of message dictionaries, each with 'role' and 'content' keys
            tools: Optional list of tool definitions
            temperature: The temperature to use for generation (default: 0.7)
            max_tokens: The maximum number of tokens to generate (default: None)
            
        Returns:
            The LLM response as a dictionary
        """
        pass
    
    @abstractmethod
    async def generate_tool_calls(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate tool calls from the LLM.
        
        Args:
            messages: A list of message dictionaries, each with 'role' and 'content' keys
            tools: List of tool definitions
            temperature: The temperature to use for generation (default: 0.7)
            max_tokens: The maximum number of tokens to generate (default: None)
            
        Returns:
            The LLM response as a dictionary, including tool calls
        """
        pass