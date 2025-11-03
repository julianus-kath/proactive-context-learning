"""
Intent Parser for Answer-first Query Processing - Phase 7: Autonomous Discovery.

This module analyzes natural language queries to extract:
1. User's primary intent (SEARCH, AGGREGATE, JOIN, REPORT, FILTER, TREND)
2. Key entities (what the user is asking about)
3. Required operations (sorting, filtering, grouping)
4. Confidence score (0-1 indicating how clear the intent is)

The parser enables answer-first agent behavior: immediately invoke Scout Mode
discovery tools instead of asking clarifying questions about table names.

Intent Categories:
- SEARCH: Find specific records (e.g., "Show me all customers named...")
- AGGREGATE: Calculate metrics (e.g., "How many orders..." "Total sales...")
- JOIN: Combine multiple entities (e.g., "Show orders with customer details")
- REPORT: Generate summaries (e.g., "Top 10 products by revenue")
- FILTER: Apply complex conditions (e.g., "Orders above $1000 in Q4")
- TREND: Time-series analysis (e.g., "Sales trend over months")
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """Enumeration of user intent types."""
    SEARCH = "SEARCH"           # Find specific records
    AGGREGATE = "AGGREGATE"     # Calculate metrics
    JOIN = "JOIN"               # Combine multiple entities
    REPORT = "REPORT"           # Generate summary/ranking
    FILTER = "FILTER"           # Apply complex conditions
    TREND = "TREND"             # Time-series analysis
    UNKNOWN = "UNKNOWN"         # Could not determine intent


@dataclass
class ParsedIntent:
    """Result of intent parsing."""
    intent: IntentType
    confidence: float  # 0.0 to 1.0
    entities: List[str]  # What the query is about (nouns, measurements)
    operations: List[str]  # Actions needed (sort, group, count, etc.)
    keywords: List[str]  # Key phrases that triggered this intent
    original_query: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "intent": self.intent.value,
            "confidence": self.confidence,
            "entities": self.entities,
            "operations": self.operations,
            "keywords": self.keywords,
            "original_query": self.original_query
        }


class IntentParser:
    """
    Parses natural language queries to extract user intent.
    
    Enables answer-first behavior by immediately invoking discovery tools
    without clarifying table names.
    """
    
    # Intent patterns: (regex, intent_type, weight)
    INTENT_PATTERNS = [
        # AGGREGATE patterns
        (r'\b(how\s+many|count|total|sum|average|avg|max|min)\b', IntentType.AGGREGATE, 0.9),
        (r'\b(revenue|sales|profit|cost|spend)\b.*\b(total|sum|aggregate)', IntentType.AGGREGATE, 0.85),
        
        # TREND patterns
        (r'\b(trend|evolution|progress|growth|decline|over\s+time|by\s+month|by\s+quarter|by\s+year)\b', IntentType.TREND, 0.9),
        (r'\b(historical|time\s+series|year\s+over\s+year|monthly)\b', IntentType.TREND, 0.85),
        
        # REPORT patterns
        (r'\b(top|bottom|ranking|leaderboard|highest|lowest|sorted|sorted\s+by)\b', IntentType.REPORT, 0.9),
        (r'\b(by\s+\w+|grouped\s+by|breakdown)\b', IntentType.REPORT, 0.8),
        
        # JOIN patterns
        (r'\b(with|including|along\s+with|together\s+with)\b.*\b(detail|info|information)\b', IntentType.JOIN, 0.85),
        (r'\b(customer.*order|product.*sale|order.*detail)\b', IntentType.JOIN, 0.8),
        
        # FILTER patterns
        (r'\b(where|where\s+\w+\s*(is|equals|=|>|<|between|in))', IntentType.FILTER, 0.85),
        (r'\b(over|above|below|more\s+than|less\s+than|between)\b.*\b(and)\b', IntentType.FILTER, 0.8),
        
        # SEARCH patterns
        (r'\b(find|search|show|get|list|display)\b', IntentType.SEARCH, 0.7),
        (r'\b(give\s+me|can\s+you\s+show|i\s+need)\b', IntentType.SEARCH, 0.6),
    ]
    
    # Common operation keywords
    OPERATIONS = {
        'count', 'sum', 'average', 'avg', 'max', 'min', 'total',
        'sort', 'sorted', 'order', 'group', 'grouped', 'filter',
        'top', 'bottom', 'highest', 'lowest', 'rank', 'ranking',
        'distinct', 'unique', 'group_by', 'order_by'
    }
    
    # Common entity indicators (nouns that indicate what user wants)
    ENTITY_KEYWORDS = {
        'customer', 'order', 'product', 'sale', 'employee',
        'department', 'supplier', 'warehouse', 'inventory',
        'transaction', 'revenue', 'profit', 'cost', 'expense',
        'region', 'category', 'date', 'quarter', 'month', 'year'
    }
    
    def parse(self, query: str) -> ParsedIntent:
        """
        Parse a natural language query to extract intent.
        
        Args:
            query: Natural language query string
        
        Returns:
            ParsedIntent with intent type, confidence, entities, and operations
        """
        query_lower = query.lower()
        
        # Find matching intents and collect scores
        intent_scores: Dict[IntentType, float] = {}
        matched_keywords: List[str] = []
        
        for pattern, intent_type, weight in self.INTENT_PATTERNS:
            if re.search(pattern, query_lower, re.IGNORECASE):
                current_score = intent_scores.get(intent_type, 0)
                intent_scores[intent_type] = current_score + weight
                matched_keywords.append(re.findall(pattern, query_lower, re.IGNORECASE)[0])
        
        # Determine primary intent
        if intent_scores:
            primary_intent = max(intent_scores.items(), key=lambda x: x[1])
            intent_type = primary_intent[0]
            confidence = min(primary_intent[1] / 1.0, 1.0)  # Normalize to 0-1
        else:
            intent_type = IntentType.UNKNOWN
            confidence = 0.0
        
        # Extract entities
        entities = self._extract_entities(query_lower)
        
        # Extract operations
        operations = self._extract_operations(query_lower)
        
        return ParsedIntent(
            intent=intent_type,
            confidence=confidence,
            entities=entities,
            operations=operations,
            keywords=matched_keywords,
            original_query=query
        )
    
    def _extract_entities(self, query_lower: str) -> List[str]:
        """
        Extract entities (what the query is about) from query.
        
        Args:
            query_lower: Lowercase query string
        
        Returns:
            List of identified entities
        """
        entities = []
        
        # Look for entity keywords (handle plurals)
        words = query_lower.split()
        for i, word in enumerate(words):
            clean_word = word.strip(',.!?;:')
            # Check exact match
            if clean_word in self.ENTITY_KEYWORDS:
                entities.append(clean_word)
            # Check singular form (handle plurals like "customers" → "customer")
            elif clean_word.endswith('s') and clean_word[:-1] in self.ENTITY_KEYWORDS:
                entities.append(clean_word[:-1])  # Add singular form
            # Look for compound entities (e.g., "customer name", "order date")
            elif i < len(words) - 1:
                next_word = words[i + 1].strip(',.!?;:')
                if clean_word in self.ENTITY_KEYWORDS and next_word in self.ENTITY_KEYWORDS:
                    entities.append(f"{clean_word}_{next_word}")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_entities = []
        for e in entities:
            if e not in seen:
                unique_entities.append(e)
                seen.add(e)
        
        return unique_entities[:5]  # Limit to top 5 entities
    
    def _extract_operations(self, query_lower: str) -> List[str]:
        """
        Extract operations (actions needed) from query.
        
        Args:
            query_lower: Lowercase query string
        
        Returns:
            List of identified operations
        """
        operations = []
        
        words = query_lower.split()
        for word in words:
            clean_word = word.strip(',.!?;:')
            if clean_word in self.OPERATIONS:
                operations.append(clean_word)
        
        # Remove duplicates
        return list(set(operations))
    
    def determine_discovery_tools(self, parsed: ParsedIntent) -> List[str]:
        """
        Determine which Scout Mode discovery tools to invoke based on intent.
        
        Args:
            parsed: ParsedIntent from parse()
        
        Returns:
            List of tool names to invoke: ['list_tables', 'search_tables', 'get_table', 'get_column_stats']
        """
        tools = []
        
        if parsed.confidence < 0.3:
            # Low confidence - use basic listing
            tools.append('list_tables')
        elif parsed.intent == IntentType.SEARCH:
            # Search intent - use fuzzy matching on tables and columns
            tools.extend(['list_tables', 'search_tables'])
        elif parsed.intent == IntentType.AGGREGATE:
            # Need to find numeric columns
            tools.extend(['search_tables', 'get_column_stats'])
        elif parsed.intent == IntentType.TREND:
            # Need date columns and numeric columns
            tools.extend(['search_tables', 'get_column_stats'])
        elif parsed.intent == IntentType.REPORT:
            # Need to find and rank relevant tables
            tools.extend(['list_tables', 'search_tables'])
        elif parsed.intent == IntentType.JOIN:
            # Need to find related tables (with foreign keys)
            tools.extend(['list_tables', 'search_tables'])
        elif parsed.intent == IntentType.FILTER:
            # Need to understand available columns
            tools.extend(['search_tables', 'get_table'])
        else:
            # Unknown - use basic tools
            tools.extend(['list_tables', 'search_tables'])
        
        # Always include list_tables as fallback
        if 'list_tables' not in tools:
            tools.insert(0, 'list_tables')
        
        return tools


def parse_intent(query: str) -> ParsedIntent:
    """
    Convenience function to parse query intent.
    
    Args:
        query: Natural language query string
    
    Returns:
        ParsedIntent with analysis results
    """
    parser = IntentParser()
    return parser.parse(query)