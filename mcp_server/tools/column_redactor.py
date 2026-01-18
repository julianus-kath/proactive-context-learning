"""
Column redaction module for sensitive data protection.

This module provides pattern-based column redaction to protect sensitive
information in query results (e.g., passwords, SSNs, credit cards).

Features:
- Pattern-based column name matching
- Configurable redaction patterns
- Preserves data structure (replaces values with "[REDACTED]")
- Case-insensitive matching
- Regex pattern support
"""

import re
import logging
from typing import List, Dict, Any, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RedactionConfig:
    """Configuration for column redaction."""
    
    # Default sensitive column patterns
    DEFAULT_PATTERNS = [
        r'.*password.*',
        r'.*passwd.*',
        r'.*pwd.*',
        r'.*secret.*',
        r'.*token.*',
        r'.*api[_-]?key.*',
        r'.*ssn.*',
        r'.*social[_-]?security.*',
        r'.*credit[_-]?card.*',
        r'.*card[_-]?number.*',
        r'.*cvv.*',
        r'.*pin.*',
        r'.*private[_-]?key.*',
        r'.*auth.*',
        r'.*salt.*',
        r'.*hash.*',
    ]
    
    patterns: List[str] = None
    enabled: bool = True
    redaction_text: str = "[REDACTED]"
    
    def __post_init__(self):
        """Initialize with default patterns if none provided."""
        if self.patterns is None:
            self.patterns = self.DEFAULT_PATTERNS.copy()


class ColumnRedactor:
    """
    Column redactor for protecting sensitive data in query results.
    
    This class identifies sensitive columns by pattern matching and
    replaces their values with a redaction marker.
    """
    
    def __init__(self, config: RedactionConfig = None):
        """
        Initialize column redactor.
        
        Args:
            config: Redaction configuration (uses defaults if None)
        """
        self.config = config or RedactionConfig()
        
        # Compile regex patterns for efficiency
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.config.patterns
        ]
        
        logger.info(f"ColumnRedactor initialized with {len(self.config.patterns)} patterns")
    
    def identify_sensitive_columns(self, columns: List[str]) -> Set[str]:
        """
        Identify sensitive columns by pattern matching.
        
        Args:
            columns: List of column names
        
        Returns:
            Set of column names that match sensitive patterns
        """
        if not self.config.enabled:
            return set()
        
        sensitive = set()
        
        for column in columns:
            for pattern in self._compiled_patterns:
                if pattern.match(column):
                    sensitive.add(column)
                    logger.debug(f"Identified sensitive column: {column}")
                    break
        
        return sensitive
    
    def redact_rows(self, rows: List[Dict[str, Any]], columns: List[str] = None) -> tuple[List[Dict[str, Any]], Set[str]]:
        """
        Redact sensitive columns in query results.
        
        Args:
            rows: List of row dictionaries
            columns: Optional list of column names (extracted from rows if not provided)
        
        Returns:
            Tuple of (redacted_rows, set_of_redacted_columns)
        """
        if not self.config.enabled or not rows:
            return rows, set()
        
        # Extract column names if not provided
        if columns is None:
            columns = list(rows[0].keys()) if rows else []
        
        # Identify sensitive columns
        sensitive_columns = self.identify_sensitive_columns(columns)
        
        if not sensitive_columns:
            return rows, set()
        
        # Redact sensitive values
        redacted_rows = []
        for row in rows:
            redacted_row = row.copy()
            for col in sensitive_columns:
                if col in redacted_row:
                    redacted_row[col] = self.config.redaction_text
            redacted_rows.append(redacted_row)
        
        logger.info(f"Redacted {len(sensitive_columns)} columns in {len(rows)} rows")
        return redacted_rows, sensitive_columns
    
    def add_pattern(self, pattern: str):
        """
        Add a new redaction pattern.
        
        Args:
            pattern: Regex pattern to match column names
        """
        self.config.patterns.append(pattern)
        self._compiled_patterns.append(re.compile(pattern, re.IGNORECASE))
        logger.info(f"Added redaction pattern: {pattern}")
    
    def remove_pattern(self, pattern: str):
        """
        Remove a redaction pattern.
        
        Args:
            pattern: Pattern to remove
        """
        if pattern in self.config.patterns:
            idx = self.config.patterns.index(pattern)
            self.config.patterns.pop(idx)
            self._compiled_patterns.pop(idx)
            logger.info(f"Removed redaction pattern: {pattern}")


def redact_sensitive_data(rows: List[Dict[str, Any]], 
                         patterns: List[str] = None,
                         enabled: bool = True) -> tuple[List[Dict[str, Any]], Set[str]]:
    """
    Convenience function for redacting sensitive data.
    
    Args:
        rows: List of row dictionaries
        patterns: Optional custom patterns (uses defaults if None)
        enabled: Whether redaction is enabled
    
    Returns:
        Tuple of (redacted_rows, set_of_redacted_columns)
    """
    config = RedactionConfig(patterns=patterns, enabled=enabled)
    redactor = ColumnRedactor(config)
    return redactor.redact_rows(rows)