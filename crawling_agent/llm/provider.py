"""
Abstract LLM provider interface and implementations.
"""
import os
import json
import abc
import logging
from typing import Dict, List, Any, Optional, Union

# Configure logging
logger = logging.getLogger(__name__)


class LLMProvider(abc.ABC):
    """
    Abstract base class for LLM providers.
    
    This interface defines the common methods that all LLM providers must implement,
    allowing the agent to use different LLM backends interchangeably.
    """
    
    @abc.abstractmethod
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the LLM provider with configuration.
        
        Args:
            config: Provider-specific configuration
        """
        pass
    
    @abc.abstractmethod
    async def generate(self, 
                      prompt: str, 
                      system_message: Optional[str] = None,
                      temperature: float = 0.7, 
                      max_tokens: Optional[int] = None,
                      stop_sequences: Optional[List[str]] = None) -> str:
        """
        Generate a completion for the given prompt.
        
        Args:
            prompt: The prompt to generate a completion for
            system_message: Optional system message to set context
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            stop_sequences: Optional list of sequences where the model should stop generating
            
        Returns:
            The generated text
        """
        pass
    
    @abc.abstractmethod
    async def generate_with_json_output(self, 
                                       prompt: str, 
                                       output_schema: Dict[str, Any],
                                       system_message: Optional[str] = None,
                                       temperature: float = 0.2) -> Dict[str, Any]:
        """
        Generate a completion with structured JSON output.
        
        Args:
            prompt: The prompt to generate a completion for
            output_schema: JSON schema defining the expected output structure
            system_message: Optional system message to set context
            temperature: Sampling temperature (0.0 to 1.0)
            
        Returns:
            The generated output as a Python dictionary
        """
        pass
    
    @abc.abstractmethod
    def get_provider_name(self) -> str:
        """
        Get the name of the provider.
        
        Returns:
            The provider name
        """
        pass
    
    @abc.abstractmethod
    def get_model_name(self) -> str:
        """
        Get the name of the model being used.
        
        Returns:
            The model name
        """
        pass
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """
        Get the default configuration for this provider.
        
        Returns:
            Default configuration dictionary
        """
        return {}


class OpenAIProvider(LLMProvider):
    """
    OpenAI API implementation of the LLM provider interface.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the OpenAI provider.
        
        Args:
            config: Configuration dictionary with the following keys:
                - api_key: OpenAI API key (required)
                - model: Model to use (default: "gpt-4")
                - organization: OpenAI organization ID (optional)
        """
        try:
            import openai
        except ImportError:
            raise ImportError(
                "The OpenAI package is required to use the OpenAI provider. "
                "Please install it with `pip install openai`."
            )
        
        # Get API key from config or environment variable
        self.api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key is required. Provide it in the config or "
                "set the OPENAI_API_KEY environment variable."
            )
        
        # Get organization ID from config or environment variable
        self.organization = config.get("organization") or os.environ.get("OPENAI_ORGANIZATION")
        
        # Get model from config, environment variable, or use default
        self.model = config.get("model") or os.environ.get("OPENAI_MODEL", "gpt-4")
        
        # Initialize the client
        self.client = openai.AsyncOpenAI(
            api_key=self.api_key,
            organization=self.organization
        )
        
        logger.info(f"Initialized OpenAI provider with model: {self.model}")
    
    async def generate(self, 
                      prompt: str, 
                      system_message: Optional[str] = None,
                      temperature: float = 0.7, 
                      max_tokens: Optional[int] = None,
                      stop_sequences: Optional[List[str]] = None) -> str:
        """
        Generate a completion using the OpenAI API.
        
        Args:
            prompt: The prompt to generate a completion for
            system_message: Optional system message to set context
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            stop_sequences: Optional list of sequences where the model should stop generating
            
        Returns:
            The generated text
        """
        messages = []
        
        # Add system message if provided
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        # Add user prompt
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stop=stop_sequences
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating completion with OpenAI: {str(e)}")
            raise
    
    async def generate_with_json_output(self, 
                                       prompt: str, 
                                       output_schema: Dict[str, Any],
                                       system_message: Optional[str] = None,
                                       temperature: float = 0.2) -> Dict[str, Any]:
        """
        Generate a completion with structured JSON output using the OpenAI API.
        
        Args:
            prompt: The prompt to generate a completion for
            output_schema: JSON schema defining the expected output structure
            system_message: Optional system message to set context
            temperature: Sampling temperature (0.0 to 1.0)
            
        Returns:
            The generated output as a Python dictionary
        """
        if not system_message:
            system_message = "You are a helpful assistant that always responds in JSON format."
        else:
            system_message += "\n\nYou must respond in JSON format."
        
        # Add schema information to the prompt
        schema_prompt = f"\n\nYour response must conform to the following JSON schema:\n{json.dumps(output_schema, indent=2)}"
        full_prompt = prompt + schema_prompt
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=temperature,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
            
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from OpenAI response: {str(e)}")
            logger.error(f"Raw response: {content}")
            raise
            
        except Exception as e:
            logger.error(f"Error generating JSON completion with OpenAI: {str(e)}")
            raise
    
    def get_provider_name(self) -> str:
        """
        Get the name of the provider.
        
        Returns:
            The provider name
        """
        return "openai"
    
    def get_model_name(self) -> str:
        """
        Get the name of the model being used.
        
        Returns:
            The model name
        """
        return self.model
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """
        Get the default configuration for the OpenAI provider.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "model": "gpt-4",
            "api_key": os.environ.get("OPENAI_API_KEY", ""),
            "organization": os.environ.get("OPENAI_ORGANIZATION", "")
        }


class MockProvider(LLMProvider):
    """
    Mock LLM provider for testing purposes.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the mock provider.
        
        Args:
            config: Configuration dictionary with the following keys:
                - responses: Dictionary mapping prompts to responses (optional)
                - default_response: Default response for prompts not in responses (optional)
        """
        self.responses = config.get("responses", {})
        self.default_response = config.get("default_response", "This is a mock response.")
        self.model = config.get("model", "mock-model")
        logger.info("Initialized Mock LLM provider")
    
    async def generate(self, 
                      prompt: str, 
                      system_message: Optional[str] = None,
                      temperature: float = 0.7, 
                      max_tokens: Optional[int] = None,
                      stop_sequences: Optional[List[str]] = None) -> str:
        """
        Generate a mock completion.
        
        Args:
            prompt: The prompt to generate a completion for
            system_message: Optional system message to set context
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            stop_sequences: Optional list of sequences where the model should stop generating
            
        Returns:
            The mock response
        """
        # Check if we have a predefined response for this prompt
        for pattern, response in self.responses.items():
            if pattern in prompt:
                return response
        
        return self.default_response
    
    async def generate_with_json_output(self, 
                                       prompt: str, 
                                       output_schema: Dict[str, Any],
                                       system_message: Optional[str] = None,
                                       temperature: float = 0.2) -> Dict[str, Any]:
        """
        Generate a mock JSON completion.
        
        Args:
            prompt: The prompt to generate a completion for
            output_schema: JSON schema defining the expected output structure
            system_message: Optional system message to set context
            temperature: Sampling temperature (0.0 to 1.0)
            
        Returns:
            A mock JSON response
        """
        # For testing, return a simple JSON that matches the schema
        if "properties" in output_schema:
            result = {}
            for prop, details in output_schema["properties"].items():
                if details.get("type") == "string":
                    result[prop] = f"Mock {prop}"
                elif details.get("type") == "number" or details.get("type") == "integer":
                    result[prop] = 42
                elif details.get("type") == "boolean":
                    result[prop] = True
                elif details.get("type") == "array":
                    result[prop] = []
                elif details.get("type") == "object":
                    result[prop] = {}
                else:
                    result[prop] = None
            return result
        
        return {"result": "This is a mock JSON response."}
    
    def get_provider_name(self) -> str:
        """
        Get the name of the provider.
        
        Returns:
            The provider name
        """
        return "mock"
    
    def get_model_name(self) -> str:
        """
        Get the name of the model being used.
        
        Returns:
            The model name
        """
        return self.model
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """
        Get the default configuration for the mock provider.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "model": "mock-model",
            "responses": {},
            "default_response": "This is a mock response."
        }


class LLMProviderFactory:
    """
    Factory for creating LLM providers.
    """
    
    _providers = {
        "openai": OpenAIProvider,
        "mock": MockProvider
    }
    
    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """
        Register a new LLM provider.
        
        Args:
            name: Provider name
            provider_class: Provider class
        """
        cls._providers[name] = provider_class
    
    @classmethod
    def create(cls, provider_name: str, config: Optional[Dict[str, Any]] = None) -> LLMProvider:
        """
        Create an LLM provider instance.
        
        Args:
            provider_name: Name of the provider to create
            config: Provider-specific configuration
            
        Returns:
            An instance of the specified LLM provider
            
        Raises:
            ValueError: If the provider is not registered
        """
        if provider_name not in cls._providers:
            raise ValueError(f"Unknown LLM provider: {provider_name}")
        
        provider_class = cls._providers[provider_name]
        
        # Use default config if none provided
        if config is None:
            config = provider_class.get_default_config()
        
        return provider_class(config)
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """
        Get a list of available provider names.
        
        Returns:
            List of provider names
        """
        return list(cls._providers.keys())