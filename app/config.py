"""
Configuration management for the agent system
Handles environment variable loading and validation
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def load_env_file(env_file_path: str) -> Dict[str, str]:
    """
    Load environment variables from a .env file.
    
    Args:
        env_file_path: Path to the .env file
        
    Returns:
        Dictionary of environment variables
    """
    env_vars = {}
    
    if not os.path.exists(env_file_path):
        logger.warning(f"Environment file not found: {env_file_path}")
        return env_vars
    
    try:
        with open(env_file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Parse key=value pairs
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    env_vars[key] = value
                else:
                    logger.warning(f"Invalid line in {env_file_path}:{line_num}: {line}")
    
    except Exception as e:
        logger.error(f"Error reading environment file {env_file_path}: {e}")
    
    return env_vars


def load_agent_config(config_file: Optional[str] = None) -> None:
    """
    Load agent configuration from environment file.
    
    Args:
        config_file: Path to config file (defaults to .env.agent.mac)
    """
    if config_file is None:
        # Try to find the appropriate config file
        project_root = Path(__file__).parent.parent
        config_file = project_root / ".env.agent.mac"
    
    if os.path.exists(config_file):
        env_vars = load_env_file(str(config_file))
        
        # Set environment variables
        for key, value in env_vars.items():
            os.environ[key] = value
            
        logger.info(f"Loaded {len(env_vars)} environment variables from {config_file}")
    else:
        logger.info(f"No config file found at {config_file}, using existing environment variables")


def validate_proxy_config() -> bool:
    """
    Validate that required proxy configuration is present.
    
    Returns:
        True if configuration is valid, False otherwise
    """
    required_vars = ["PROXY_BASE_URL", "PROXY_API_KEY"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required proxy configuration: {', '.join(missing_vars)}")
        return False
    
    return True


def get_config_summary() -> Dict[str, Any]:
    """
    Get a summary of current configuration (without sensitive values).
    
    Returns:
        Dictionary with configuration summary
    """
    return {
        "db_mode": os.getenv("DB_MODE", "proxy"),
        "proxy_base_url": os.getenv("PROXY_BASE_URL", "not_set"),
        "proxy_api_key_set": bool(os.getenv("PROXY_API_KEY")),
        "proxy_tls_verify": os.getenv("PROXY_TLS_VERIFY", "true"),
        "proxy_ca_bundle": os.getenv("PROXY_CA_BUNDLE", "not_set"),
        "proxy_default_conn": os.getenv("PROXY_DEFAULT_CONN", "not_set"),
        "proxy_timeout": os.getenv("PROXY_TIMEOUT", "30"),
        "proxy_max_retries": os.getenv("PROXY_MAX_RETRIES", "3"),
    }


def print_config_status():
    """Print current configuration status for debugging."""
    config = get_config_summary()
    
    print("🔧 Agent Configuration Status")
    print("=" * 40)
    print(f"Database Mode: {config['db_mode']}")
    
    if config['db_mode'] == 'proxy':
        print(f"Proxy URL: {config['proxy_base_url']}")
        print(f"API Key Set: {'✅' if config['proxy_api_key_set'] else '❌'}")
        print(f"TLS Verify: {config['proxy_tls_verify']}")
        print(f"CA Bundle: {config['proxy_ca_bundle']}")
        print(f"Default Connection: {config['proxy_default_conn']}")
        print(f"Timeout: {config['proxy_timeout']}s")
        print(f"Max Retries: {config['proxy_max_retries']}")
        
        if validate_proxy_config():
            print("Status: ✅ Proxy configuration is valid")
        else:
            print("Status: ❌ Proxy configuration is incomplete")
    else:
        print("Status: ✅ Direct mode (development)")


if __name__ == "__main__":
    # Test configuration loading
    load_agent_config()
    print_config_status()