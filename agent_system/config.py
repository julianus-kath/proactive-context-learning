"""
Configuration settings for the multi-agent system.

This module provides configuration management for the agent system,
including MCP server settings, agent parameters, and environment variables.
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MCPServerConfig:
    """Configuration for MCP server connection."""
    url: str = "http://localhost:8000"
    api_key: str = "supersecretapikey"
    timeout: int = 30
    health_check_interval: int = 60  # seconds
    max_retries: int = 3
    retry_delay: int = 5  # seconds


@dataclass
class AgentConfig:
    """Configuration for agent behavior."""
    model: str = "gpt-4o"
    temperature: float = 0.0
    max_tokens: Optional[int] = None
    verbose: bool = False
    debug: bool = False


@dataclass
class SystemConfig:
    """Overall system configuration."""
    mcp_server: MCPServerConfig
    agent: AgentConfig
    log_level: str = "INFO"
    log_file: Optional[str] = None
    environment: str = "development"  # development, staging, production


class ConfigManager:
    """
    Configuration manager for the multi-agent system.
    
    This class handles loading configuration from environment variables,
    config files, and provides defaults for all settings.
    """
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_file: Optional path to configuration file
        """
        self.config_file = config_file
        self._config: Optional[SystemConfig] = None
        
    def load_config(self) -> SystemConfig:
        """
        Load configuration from environment variables and files.
        
        Returns:
            SystemConfig instance
        """
        if self._config is not None:
            return self._config
        
        # Load MCP server configuration
        mcp_config = MCPServerConfig(
            url=os.getenv("MCP_SERVER_URL", "http://localhost:8000"),
            api_key=os.getenv("MCP_API_KEY", "supersecretapikey"),
            timeout=int(os.getenv("MCP_TIMEOUT", "30")),
            health_check_interval=int(os.getenv("MCP_HEALTH_CHECK_INTERVAL", "60")),
            max_retries=int(os.getenv("MCP_MAX_RETRIES", "3")),
            retry_delay=int(os.getenv("MCP_RETRY_DELAY", "5"))
        )
        
        # Load agent configuration
        agent_config = AgentConfig(
            model=os.getenv("AGENT_MODEL", "gpt-4o"),
            temperature=float(os.getenv("AGENT_TEMPERATURE", "0.0")),
            max_tokens=int(os.getenv("AGENT_MAX_TOKENS")) if os.getenv("AGENT_MAX_TOKENS") else None,
            verbose=os.getenv("AGENT_VERBOSE", "false").lower() == "true",
            debug=os.getenv("AGENT_DEBUG", "false").lower() == "true"
        )
        
        # Load system configuration
        self._config = SystemConfig(
            mcp_server=mcp_config,
            agent=agent_config,
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=os.getenv("LOG_FILE"),
            environment=os.getenv("ENVIRONMENT", "development")
        )
        
        return self._config
    
    def get_config(self) -> SystemConfig:
        """
        Get the current configuration, loading it if necessary.
        
        Returns:
            SystemConfig instance
        """
        if self._config is None:
            return self.load_config()
        return self._config
    
    def update_mcp_config(self, **kwargs):
        """
        Update MCP server configuration.
        
        Args:
            **kwargs: Configuration parameters to update
        """
        config = self.get_config()
        for key, value in kwargs.items():
            if hasattr(config.mcp_server, key):
                setattr(config.mcp_server, key, value)
    
    def update_agent_config(self, **kwargs):
        """
        Update agent configuration.
        
        Args:
            **kwargs: Configuration parameters to update
        """
        config = self.get_config()
        for key, value in kwargs.items():
            if hasattr(config.agent, key):
                setattr(config.agent, key, value)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.
        
        Returns:
            Configuration as dictionary
        """
        config = self.get_config()
        return {
            "mcp_server": {
                "url": config.mcp_server.url,
                "api_key": config.mcp_server.api_key,
                "timeout": config.mcp_server.timeout,
                "health_check_interval": config.mcp_server.health_check_interval,
                "max_retries": config.mcp_server.max_retries,
                "retry_delay": config.mcp_server.retry_delay
            },
            "agent": {
                "model": config.agent.model,
                "temperature": config.agent.temperature,
                "max_tokens": config.agent.max_tokens,
                "verbose": config.agent.verbose,
                "debug": config.agent.debug
            },
            "system": {
                "log_level": config.log_level,
                "log_file": config.log_file,
                "environment": config.environment
            }
        }


# Global configuration manager instance
_config_manager = None


def get_config_manager() -> ConfigManager:
    """
    Get the global configuration manager instance.
    
    Returns:
        ConfigManager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config() -> SystemConfig:
    """
    Get the current system configuration.
    
    Returns:
        SystemConfig instance
    """
    return get_config_manager().get_config()


def get_mcp_config() -> MCPServerConfig:
    """
    Get MCP server configuration.
    
    Returns:
        MCPServerConfig instance
    """
    return get_config().mcp_server


def get_agent_config() -> AgentConfig:
    """
    Get agent configuration.
    
    Returns:
        AgentConfig instance
    """
    return get_config().agent


# Environment configuration helpers
def is_development() -> bool:
    """Check if running in development environment."""
    return get_config().environment == "development"


def is_production() -> bool:
    """Check if running in production environment."""
    return get_config().environment == "production"


def setup_logging():
    """Setup logging based on configuration."""
    import logging
    
    config = get_config()
    
    # Set log level
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    
    # Configure logging
    logging_config = {
        'level': log_level,
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'datefmt': '%Y-%m-%d %H:%M:%S'
    }
    
    if config.log_file:
        logging_config['filename'] = config.log_file
        logging_config['filemode'] = 'a'
    
    logging.basicConfig(**logging_config)
    
    # Set specific logger levels
    if config.agent.debug:
        logging.getLogger('agent_system').setLevel(logging.DEBUG)
    
    if config.agent.verbose:
        logging.getLogger('langchain').setLevel(logging.INFO)
        logging.getLogger('langgraph').setLevel(logging.INFO)


# Example usage and testing
if __name__ == "__main__":
    import json
    
    # Test configuration loading
    config_manager = get_config_manager()
    config = config_manager.get_config()
    
    print("Current configuration:")
    print(json.dumps(config_manager.to_dict(), indent=2))
    
    # Test configuration updates
    config_manager.update_mcp_config(url="http://localhost:9000")
    config_manager.update_agent_config(temperature=0.1)
    
    print("\nUpdated configuration:")
    print(json.dumps(config_manager.to_dict(), indent=2))
    
    # Test environment helpers
    print(f"\nEnvironment checks:")
    print(f"Is development: {is_development()}")
    print(f"Is production: {is_production()}")
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Configuration loaded successfully")