"""
Configuration settings for the synthetic data service.
"""

import os
from dataclasses import dataclass


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    # Default to SQLite for simplicity, but can be changed to other databases
    db_type: str = "sqlite"
    db_name: str = "synthetic_data.db"
    db_host: str = ""
    db_port: int = 0
    db_user: str = ""
    db_password: str = ""
    
    @property
    def connection_string(self) -> str:
        """Generate the database connection string based on the configuration."""
        if self.db_type == "sqlite":
            return f"sqlite:///{self.db_name}"
        elif self.db_type == "postgresql":
            return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        elif self.db_type == "mysql":
            return f"mysql+pymysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")


@dataclass
class GeneratorConfig:
    """Configuration for synthetic data generation."""
    # Default seed for reproducibility
    random_seed: int = 42
    
    # Date range for generated data
    start_date: str = "2020-01-01"
    end_date: str = "2023-12-31"
    
    # Regions for customer distribution
    regions: list[str] = None
    
    def __post_init__(self):
        if self.regions is None:
            self.regions = ["North", "South", "East", "West", "Central"]


# Default configurations
db_config = DatabaseConfig()
generator_config = GeneratorConfig()


def configure_from_env():
    """
    Configure the application from environment variables.
    This allows for easy configuration in different environments.
    """
    # Database configuration
    if os.environ.get("DB_TYPE"):
        db_config.db_type = os.environ.get("DB_TYPE")
    if os.environ.get("DB_NAME"):
        db_config.db_name = os.environ.get("DB_NAME")
    if os.environ.get("DB_HOST"):
        db_config.db_host = os.environ.get("DB_HOST")
    if os.environ.get("DB_PORT"):
        db_config.db_port = int(os.environ.get("DB_PORT"))
    if os.environ.get("DB_USER"):
        db_config.db_user = os.environ.get("DB_USER")
    if os.environ.get("DB_PASSWORD"):
        db_config.db_password = os.environ.get("DB_PASSWORD")
    
    # Generator configuration
    if os.environ.get("RANDOM_SEED"):
        generator_config.random_seed = int(os.environ.get("RANDOM_SEED"))
    if os.environ.get("START_DATE"):
        generator_config.start_date = os.environ.get("START_DATE")
    if os.environ.get("END_DATE"):
        generator_config.end_date = os.environ.get("END_DATE")
    if os.environ.get("REGIONS"):
        generator_config.regions = os.environ.get("REGIONS").split(",")