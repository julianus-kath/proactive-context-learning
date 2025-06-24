"""
LLM Client Factory.

This module provides a factory for creating LLM clients.
"""
import logging
import os
from typing import Dict, Optional, Type

from crawling_agent.llm.base_llm_client import BaseLLMClient
from crawling_agent.llm.openai_llm_client import OpenAILLMClient


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("LLMClientFactory")


class LLMClientFactory:
    """
    Factory for creating LLM clients.
    
    This class provides methods for creating different types of LLM clients.
    """
    
    # Registry of available LLM client types
    _client_types: Dict[str, Type[BaseLLMClient]] = {
        "openai": OpenAILLMClient,
    }
    
    @classmethod
    def create_client(
        cls,
        client_type: str,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        use_agents_sdk: bool = True,
        **kwargs
    ) -> BaseLLMClient:
        """
        Create an LLM client of the specified type.
        
        Args:
            client_type: The type of LLM client to create (e.g., "openai")
            api_key: Optional API key (if not provided, will look for environment variable)
            model: Optional model name (if not provided, will use default)
            use_agents_sdk: Whether to use the OpenAI Agents SDK (default: True)
            **kwargs: Additional keyword arguments to pass to the client constructor
            
        Returns:
            An instance of the specified LLM client type
            
        Raises:
            ValueError: If the specified client type is not supported
        """
        if client_type not in cls._client_types:
            raise ValueError(f"Unsupported LLM client type: {client_type}")
        
        client_class = cls._client_types[client_type]
        
        # Handle OpenAI client
        if client_type == "openai":
            # Get API key from environment variable if not provided
            if api_key is None:
                api_key = os.environ.get("OPENAI_API_KEY")
                if api_key is None:
                    raise ValueError("OpenAI API key not provided and not found in environment")
            
            # Use default model if not provided
            if model is None:
                model = "gpt-4o-2024-05-13"  # Default to o3 reasoning model
            
            logger.info(f"Creating OpenAI LLM client with model: {model}")
            return client_class(
                api_key=api_key, 
                model=model, 
                use_agents_sdk=use_agents_sdk,
                **kwargs
            )
        
        # Handle other client types as needed
        
        # This should never happen due to the check at the beginning
        raise ValueError(f"Unsupported LLM client type: {client_type}")
    
    @classmethod
    def register_client_type(cls, name: str, client_class: Type[BaseLLMClient]):
        """
        Register a new LLM client type.
        
        Args:
            name: The name of the client type
            client_class: The client class
            
        Raises:
            ValueError: If a client type with the same name is already registered
        """
        if name in cls._client_types:
            raise ValueError(f"LLM client type already registered: {name}")
        
        cls._client_types[name] = client_class
        logger.info(f"Registered new LLM client type: {name}")
    
    @classmethod
    def get_available_client_types(cls) -> list:
        """
        Get a list of available LLM client types.
        
        Returns:
            A list of available LLM client type names
        """
        return list(cls._client_types.keys())