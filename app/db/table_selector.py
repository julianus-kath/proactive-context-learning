"""
Table Relevance Selector - Heuristic-Based Table Selection

This module implements intelligent table selection to reduce schema size in LLM prompts.
Instead of sending the full database schema, it selects only the 1-3 most relevant tables
based on the user's query.

Design Decisions:
-----------------
1. **Heuristic-Based (Not Embeddings)**: Uses keyword matching and pattern recognition
   - PRO: Fast, deterministic, no ML dependencies
   - CON: Less sophisticated than semantic search
   - DECISION: Start simple; embeddings can be added later if needed

2. **Top 1-3 Tables**: Limits selection to maximize relevance while minimizing prompt size
   - PRO: Keeps prompts small, focuses LLM attention
   - CON: May miss relevant tables in complex queries
   - DECISION: 1-3 is optimal based on ERP query patterns

3. **Fallback Strategy**: Uses session history and domain defaults when no match
   - PRO: Graceful degradation, always returns something useful
   - CON: May return irrelevant tables in edge cases
   - DECISION: Better than failing or returning full schema

4. **Scoring System**: Combines multiple signals (keywords, columns, intent)
   - PRO: More robust than single-signal matching
   - CON: Requires tuning of weights
   - DECISION: Weights based on empirical testing with ERP queries

Scoring Algorithm:
------------------
Each table gets a relevance score based on:
- Table name match: 10 points (exact), 5 points (partial)
- Column name match: 3 points per column
- Keyword match: 2 points per keyword
- Intent hints: 5 points (e.g., "sales" query → sales tables)
- Session history: 1 point (recently used tables)

Usage:
------
    from app.db.table_selector import select_relevant_tables, build_schema_snippet
    
    # Select tables
    relevant_tables = select_relevant_tables(
        query="Show me recent sales",
        schema_index=schema_index,
        session_tables=['dbo.customers'],
        top_k=3
    )
    
    # Build compact schema
    schema_snippet = build_schema_snippet(relevant_tables, schema_index)
"""

import re
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass

from .schema_cache import TableInfo
from ..config.domain_keywords import DOMAIN_KEYWORDS, INTENT_PATTERNS

logger = logging.getLogger(__name__)


@dataclass
class TableScore:
    """Relevance score for a table."""
    table_name: str
    score: float
    reasons: List[str]  # Human-readable reasons for the score
    
    def __lt__(self, other):
        """Enable sorting by score (descending)."""
        return self.score > other.score  # Reverse for descending sort


def select_relevant_tables(
    query: str,
    schema_index: Dict[str, TableInfo],
    session_tables: Optional[List[str]] = None,
    top_k: int = 3
) -> List[str]:
    """
    Select the most relevant tables for a given query.
    
    Args:
        query: User's natural language query
        schema_index: Dictionary mapping table names to TableInfo objects
        session_tables: List of tables used in recent queries (for context)
        top_k: Maximum number of tables to return (default: 3)
    
    Returns:
        List of table names (schema-qualified) sorted by relevance
    
    Example:
        >>> select_relevant_tables(
        ...     "Show me sales from last month",
        ...     schema_index,
        ...     session_tables=['dbo.customers'],
        ...     top_k=2
        ... )
        ['dbo.sales', 'dbo.order_items']
    """
    if not schema_index:
        logger.warning("Empty schema index, cannot select tables")
        return []
    
    # Normalize query for matching
    query_lower = query.lower()
    query_words = set(re.findall(r'\b\w+\b', query_lower))
    
    # Detect intent
    detected_intents = _detect_intent(query_lower)
    
    # Score each table
    table_scores: List[TableScore] = []
    
    for table_name, table_info in schema_index.items():
        score, reasons = _score_table(
            table_name=table_name,
            table_info=table_info,
            query_words=query_words,
            detected_intents=detected_intents,
            session_tables=session_tables or []
        )
        
        if score > 0:
            table_scores.append(TableScore(
                table_name=table_name,
                score=score,
                reasons=reasons
            ))
    
    # Sort by score (descending)
    table_scores.sort()
    
    # Take top K
    selected = table_scores[:top_k]
    
    # Log selection for debugging
    if selected:
        logger.info(f"Selected {len(selected)} tables for query: '{query[:50]}...'")
        for ts in selected:
            logger.debug(f"  - {ts.table_name} (score={ts.score:.1f}): {', '.join(ts.reasons)}")
    else:
        logger.warning(f"No tables matched query: '{query[:50]}...'")
        # Fallback: return session tables or domain defaults
        return _get_fallback_tables(schema_index, session_tables)
    
    return [ts.table_name for ts in selected]


def _detect_intent(query: str) -> Set[str]:
    """
    Detect query intent using pattern matching.
    
    Args:
        query: Normalized query string (lowercase)
    
    Returns:
        Set of detected intent categories (e.g., {'sales', 'customers'})
    """
    intents = set()
    
    for pattern, intent in INTENT_PATTERNS:
        if re.search(pattern, query, re.IGNORECASE):
            intents.add(intent)
    
    return intents


def _score_table(
    table_name: str,
    table_info: TableInfo,
    query_words: Set[str],
    detected_intents: Set[str],
    session_tables: List[str]
) -> Tuple[float, List[str]]:
    """
    Calculate relevance score for a single table.
    
    Returns:
        Tuple of (score, reasons) where reasons is a list of human-readable explanations
    """
    score = 0.0
    reasons = []
    
    # Extract table name without schema prefix
    if '.' in table_name:
        _, simple_table_name = table_name.rsplit('.', 1)
    else:
        simple_table_name = table_name
    
    simple_table_lower = simple_table_name.lower()
    
    # 1. Table name exact match (10 points)
    if simple_table_lower in query_words:
        score += 10.0
        reasons.append(f"table name '{simple_table_name}' in query")
    
    # 2. Table name partial match (5 points)
    else:
        for word in query_words:
            if len(word) > 3 and (word in simple_table_lower or simple_table_lower in word):
                score += 5.0
                reasons.append(f"table name contains '{word}'")
                break
    
    # 3. Column name matches (3 points per column)
    column_matches = 0
    for col in table_info.columns:
        col_name_lower = col['column_name'].lower()
        if col_name_lower in query_words:
            column_matches += 1
            score += 3.0
    
    if column_matches > 0:
        reasons.append(f"{column_matches} column(s) match query")
    
    # 4. Intent-based matching (5 points per intent)
    for intent in detected_intents:
        if intent in DOMAIN_KEYWORDS:
            for keyword in DOMAIN_KEYWORDS[intent]:
                if keyword in simple_table_lower:
                    score += 5.0
                    reasons.append(f"matches intent '{intent}'")
                    break
    
    # 5. Keyword matching (2 points per keyword)
    keyword_matches = 0
    for word in query_words:
        if len(word) > 3:  # Skip short words
            # Check if keyword appears in any column name
            for col in table_info.columns:
                if word in col['column_name'].lower():
                    keyword_matches += 1
                    score += 2.0
                    break
    
    if keyword_matches > 0 and keyword_matches not in [column_matches]:
        reasons.append(f"{keyword_matches} keyword(s) in columns")
    
    # 6. Session history bonus (1 point)
    if table_name in session_tables:
        score += 1.0
        reasons.append("used in recent queries")
    
    return score, reasons


def _get_fallback_tables(
    schema_index: Dict[str, TableInfo],
    session_tables: Optional[List[str]] = None
) -> List[str]:
    """
    Get fallback tables when no good matches are found.
    
    Priority:
    1. Session tables (recently used)
    2. Domain defaults (sales, customers, products)
    3. First 3 tables in schema
    
    Args:
        schema_index: Dictionary of table information
        session_tables: Recently used tables
    
    Returns:
        List of fallback table names
    """
    # Try session tables first
    if session_tables:
        valid_session = [t for t in session_tables if t in schema_index]
        if valid_session:
            logger.info(f"Using session tables as fallback: {valid_session[:3]}")
            return valid_session[:3]
    
    # Try domain defaults
    domain_defaults = ['sales', 'customers', 'products', 'orders', 'invoices']
    fallback = []
    
    for default in domain_defaults:
        for table_name in schema_index.keys():
            if default in table_name.lower():
                fallback.append(table_name)
                if len(fallback) >= 3:
                    break
        if len(fallback) >= 3:
            break
    
    if fallback:
        logger.info(f"Using domain defaults as fallback: {fallback}")
        return fallback
    
    # Last resort: first 3 tables
    all_tables = list(schema_index.keys())[:3]
    logger.warning(f"Using first {len(all_tables)} tables as fallback: {all_tables}")
    return all_tables


def build_schema_snippet(
    table_names: List[str],
    schema_index: Dict[str, TableInfo]
) -> str:
    """
    Build a compact schema snippet for selected tables.
    
    This generates a minimal schema representation suitable for LLM prompts,
    containing only the essential information about the selected tables.
    
    Args:
        table_names: List of table names to include
        schema_index: Dictionary mapping table names to TableInfo objects
    
    Returns:
        Formatted schema snippet as a string
    
    Example output:
        ```
        Table: dbo.sales
        Columns:
          - sale_id (int) PRIMARY KEY
          - customer_id (int) FOREIGN KEY → customers.customer_id
          - sale_date (date)
          - total_amount (decimal)
        
        Table: dbo.customers
        Columns:
          - customer_id (int) PRIMARY KEY
          - customer_name (varchar)
          - email (varchar)
        ```
    """
    if not table_names:
        return ""
    
    snippet_parts = []
    
    for table_name in table_names:
        table_info = schema_index.get(table_name)
        
        if not table_info:
            logger.warning(f"Table '{table_name}' not found in schema index")
            continue
        
        # Table header
        snippet_parts.append(f"Table: {table_name}")
        
        # Add table type if not a base table
        if table_info.table_type != 'BASE TABLE':
            snippet_parts.append(f"Type: {table_info.table_type}")
        
        # Columns
        snippet_parts.append("Columns:")
        
        for col in table_info.columns:
            col_name = col['column_name']
            data_type = col['data_type']
            
            # Build column description
            col_desc = f"  - {col_name} ({data_type}"
            
            # Add length for string types
            if 'character_maximum_length' in col and col['character_maximum_length']:
                col_desc += f"({col['character_maximum_length']})"
            
            col_desc += ")"
            
            # Add constraints
            constraints = []
            
            if col_name in table_info.primary_keys:
                constraints.append("PRIMARY KEY")
            
            if col.get('is_nullable') == 'NO':
                constraints.append("NOT NULL")
            
            # Check for foreign keys
            for fk in table_info.foreign_keys:
                if fk.get('column_name') == col_name:
                    ref_table = fk.get('referenced_table', 'unknown')
                    ref_col = fk.get('referenced_column', 'unknown')
                    constraints.append(f"FOREIGN KEY → {ref_table}.{ref_col}")
            
            if constraints:
                col_desc += " " + " ".join(constraints)
            
            snippet_parts.append(col_desc)
        
        # Add row count if available
        if table_info.row_count is not None:
            snippet_parts.append(f"Approximate rows: {table_info.row_count:,}")
        
        snippet_parts.append("")  # Empty line between tables
    
    return "\n".join(snippet_parts)


def get_table_keywords(table_info: TableInfo) -> Set[str]:
    """
    Extract searchable keywords from a table.
    
    Useful for building search indexes or debugging.
    
    Args:
        table_info: TableInfo object
    
    Returns:
        Set of lowercase keywords
    """
    keywords = set()
    
    # Add table name
    if '.' in table_info.table_name:
        _, simple_name = table_info.table_name.rsplit('.', 1)
        keywords.add(simple_name.lower())
    else:
        keywords.add(table_info.table_name.lower())
    
    # Add column names
    for col in table_info.columns:
        keywords.add(col['column_name'].lower())
    
    return keywords