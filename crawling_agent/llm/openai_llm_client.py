"""
OpenAI LLM Client implementation.

This module provides an implementation of the BaseLLMClient for OpenAI's API.
It supports both traditional chat completions and the newer OpenAI Agents framework.
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional, Union

from openai import OpenAI
try:
    from agents import Agent, Runner, Tool
    from agents.schema import AgentResponse
    AGENTS_SDK_AVAILABLE = True
except ImportError:
    AGENTS_SDK_AVAILABLE = False

from crawling_agent.llm.base_llm_client import BaseLLMClient


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("OpenAILLMClient")


class OpenAILLMClient(BaseLLMClient):
    """
    OpenAI LLM client implementation.
    
    This class implements the BaseLLMClient interface for OpenAI's API.
    It supports both traditional chat completions and the newer OpenAI Agents framework.
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-2024-05-13",  # Updated to use o3 reasoning model
        organization: Optional[str] = None,
        use_agents_sdk: bool = True,
    ):
        """
        Initialize the OpenAI LLM client.
        
        Args:
            api_key: The OpenAI API key
            model: The model to use (default: "gpt-4o-2024-05-13" for o3 reasoning)
            organization: Optional organization ID
            use_agents_sdk: Whether to use the OpenAI Agents SDK (default: True)
        """
        self.api_key = api_key
        self.model = model
        self.organization = organization
        self.use_agents_sdk = use_agents_sdk and AGENTS_SDK_AVAILABLE
        
        # Initialize the OpenAI client
        # Set the API key in the environment variable
        os.environ["OPENAI_API_KEY"] = api_key
        if organization:
            os.environ["OPENAI_ORGANIZATION"] = organization
            
        # Create a custom httpx client with no proxy settings
        import httpx
        http_client = httpx.Client(
            base_url="https://api.openai.com/v1",
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )
            
        # Create the client with our custom http client
        self.client = OpenAI(http_client=http_client)
        
        # Check if we're using the o3 reasoning model
        self.is_o3_reasoning = "o3" in model.lower()
        
        logger.info(f"Initialized OpenAI LLM client with model: {model}")
        if self.use_agents_sdk:
            logger.info("Using OpenAI Agents SDK")
        if self.is_o3_reasoning:
            logger.info("Using o3 reasoning model")
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate a response from the OpenAI LLM.
        
        Args:
            messages: A list of message dictionaries, each with 'role' and 'content' keys
            tools: Optional list of tool definitions
            temperature: The temperature to use for generation (default: 0.7)
            max_tokens: The maximum number of tokens to generate (default: None)
            
        Returns:
            The LLM response as a dictionary
        """
        logger.debug(f"Generating response with {len(messages)} messages")
        
        # If using Agents SDK and tools are provided, use the Agent-based approach
        if self.use_agents_sdk and tools:
            return await self._generate_with_agents_sdk(messages, tools, temperature, max_tokens)
        
        # Otherwise, use the traditional chat completions API
        # Prepare the request parameters
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"
        
        try:
            # Log the request for debugging
            logger.debug(f"OpenAI API request: {json.dumps(params, indent=2)}")
            
            # Make the API call
            response = self.client.chat.completions.create(**params)
            
            # Convert the response to a dictionary
            response_dict = self._response_to_dict(response)
            
            # Log the response for debugging
            logger.debug(f"OpenAI API response: {json.dumps(response_dict, indent=2)}")
            
            return response_dict
        
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise
    
    async def generate_tool_calls(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate tool calls from the OpenAI LLM.
        
        Args:
            messages: A list of message dictionaries, each with 'role' and 'content' keys
            tools: List of tool definitions
            temperature: The temperature to use for generation (default: 0.7)
            max_tokens: The maximum number of tokens to generate (default: None)
            
        Returns:
            The LLM response as a dictionary, including tool calls
        """
        logger.debug(f"Generating tool calls with {len(messages)} messages and {len(tools)} tools")
        
        # If using Agents SDK, use the Agent-based approach
        if self.use_agents_sdk:
            return await self._generate_with_agents_sdk(messages, tools, temperature, max_tokens)
        
        # Otherwise, use the traditional chat completions API
        # Prepare the request parameters
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "tools": tools,
            "tool_choice": "auto",
        }
        
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        
        try:
            # Log the request for debugging
            logger.debug(f"OpenAI API request: {json.dumps(params, indent=2)}")
            
            # Make the API call
            response = self.client.chat.completions.create(**params)
            
            # Convert the response to a dictionary
            response_dict = self._response_to_dict(response)
            
            # Log the response for debugging
            logger.debug(f"OpenAI API response: {json.dumps(response_dict, indent=2)}")
            
            return response_dict
        
        except Exception as e:
            logger.error(f"Error generating tool calls: {str(e)}")
            raise
    
    async def _generate_with_agents_sdk(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate a response using the OpenAI Agents SDK.
        
        Args:
            messages: A list of message dictionaries, each with 'role' and 'content' keys
            tools: List of tool definitions
            temperature: The temperature to use for generation (default: 0.7)
            max_tokens: The maximum number of tokens to generate (default: None)
            
        Returns:
            The LLM response as a dictionary
        """
        if not AGENTS_SDK_AVAILABLE:
            logger.warning("OpenAI Agents SDK not available, falling back to chat completions API")
            # Fall back to traditional chat completions API
            return await self.generate_response(messages, tools, temperature, max_tokens)
        
        # Extract system message if present
        system_message = None
        user_messages = []
        for message in messages:
            if message["role"] == "system":
                system_message = message["content"]
            else:
                user_messages.append(message)
        
        # Create the agent
        agent = Agent(
            name="DataQueryAgent",
            instructions=system_message or "You are a helpful assistant that can query and analyze data from multiple sources.",
            model=self.model,
            temperature=temperature,
        )
        
        # Convert OpenAI tools format to Agents SDK format
        agent_tools = []
        for tool in tools:
            agent_tool = Tool(
                name=tool["function"]["name"],
                description=tool["function"].get("description", ""),
                input_schema=tool["function"].get("parameters", {}),
            )
            agent_tools.append(agent_tool)
        
        # Register the tools with the agent
        for tool in agent_tools:
            agent.register_tool(tool)
        
        # Get the last user message
        last_user_message = user_messages[-1]["content"] if user_messages else ""
        
        try:
            # Run the agent
            response: AgentResponse = await Runner.run_async(agent, last_user_message)
            
            # Convert the response to the expected format
            response_dict = {
                "role": "assistant",
                "content": response.final_output,
            }
            
            # Add tool calls if present
            if response.tool_calls:
                tool_calls = []
                for i, tool_call in enumerate(response.tool_calls):
                    tool_calls.append({
                        "id": f"call_{i}",
                        "type": "function",
                        "function": {
                            "name": tool_call.name,
                            "arguments": json.dumps(tool_call.input),
                        }
                    })
                response_dict["tool_calls"] = tool_calls
            
            return response_dict
        
        except Exception as e:
            logger.error(f"Error generating response with Agents SDK: {str(e)}")
            # Fall back to traditional chat completions API
            logger.info("Falling back to chat completions API")
            return await self.generate_response(messages, tools, temperature, max_tokens)
    
    def _response_to_dict(self, response: Any) -> Dict[str, Any]:
        """
        Convert an OpenAI API response to a dictionary.
        
        Args:
            response: The OpenAI API response
            
        Returns:
            The response as a dictionary
        """
        # Extract the message from the response
        message = response.choices[0].message
        
        # Create the base response dictionary
        response_dict = {
            "role": message.role,
            "content": message.content,
        }
        
        # Add tool calls if present
        if hasattr(message, "tool_calls") and message.tool_calls:
            tool_calls = []
            for tool_call in message.tool_calls:
                tool_calls.append({
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    }
                })
            response_dict["tool_calls"] = tool_calls
        
        return response_dict