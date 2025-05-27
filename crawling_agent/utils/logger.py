"""
Logger utility for the Crawling Agent.
"""
import logging
import os
import sys
from datetime import datetime
from typing import Optional


def get_logger(name: str, log_level: Optional[int] = None) -> logging.Logger:
    """
    Get a configured logger instance.
    
    Args:
        name: The name of the logger (typically __name__)
        log_level: The logging level (defaults to INFO or value from environment)
        
    Returns:
        A configured logger instance
    """
    # Get log level from environment or use default
    if log_level is None:
        log_level_str = os.environ.get("CRAWLING_AGENT_LOG_LEVEL", "INFO")
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Only add handlers if they don't exist yet
    if not logger.handlers:
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        
        # Format
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(console_handler)
        
        # File handler (optional, based on environment variable)
        log_to_file = os.environ.get("CRAWLING_AGENT_LOG_TO_FILE", "false").lower() == "true"
        if log_to_file:
            log_dir = os.environ.get("CRAWLING_AGENT_LOG_DIR", "logs")
            os.makedirs(log_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(log_dir, f"crawling_agent_{timestamp}.log")
            
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
    
    return logger


class TaskLogger:
    """
    Specialized logger for tracking task execution with structured data.
    """
    
    def __init__(self, task_id: str):
        """
        Initialize the TaskLogger.
        
        Args:
            task_id: The ID of the task being logged
        """
        self.task_id = task_id
        self.logger = get_logger(f"task.{task_id}")
        
    def log_task_start(self, original_query: str, task_instruction: dict) -> None:
        """
        Log the start of a task.
        
        Args:
            original_query: The original natural language query
            task_instruction: The structured task instruction
        """
        self.logger.info(f"Task {self.task_id} started")
        self.logger.info(f"Original query: {original_query}")
        self.logger.debug(f"Task instruction: {task_instruction}")
    
    def log_task_end(self, status: str, result_summary: dict) -> None:
        """
        Log the end of a task.
        
        Args:
            status: The status of the task (success, error, etc.)
            result_summary: A summary of the task results
        """
        self.logger.info(f"Task {self.task_id} ended with status: {status}")
        self.logger.debug(f"Result summary: {result_summary}")
    
    def log_query_execution(self, source_type: str, query: str, duration_ms: float) -> None:
        """
        Log the execution of a query.
        
        Args:
            source_type: The type of data source
            query: The query that was executed
            duration_ms: The duration of the query execution in milliseconds
        """
        self.logger.info(f"Executed {source_type} query in {duration_ms:.2f}ms")
        self.logger.debug(f"Query: {query}")
    
    def log_error(self, source_type: str, error_message: str, query: Optional[str] = None) -> None:
        """
        Log an error during task execution.
        
        Args:
            source_type: The type of data source
            error_message: The error message
            query: The query that caused the error (optional)
        """
        self.logger.error(f"Error in {source_type}: {error_message}")
        if query:
            self.logger.debug(f"Failed query: {query}")