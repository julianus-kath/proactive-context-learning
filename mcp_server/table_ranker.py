"""
Table Ranker for Semantic Relevance Scoring - Phase 7: Autonomous Discovery.

This module ranks database tables by relevance to user queries using:
1. Entity matching (does table/column name match query entities?)
2. Type compatibility (numeric for AGGREGATE, date for TREND, etc.)
3. Semantic similarity (fuzzy matching on names)
4. Table metadata (row count, foreign key count indicates connectedness)
5. Column availability (does table have needed column types?)

Ranking enables agent to autonomously select tables without clarification.
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


@dataclass
class RankedTable:
    """A table with its relevance score."""
    schema: str
    name: str
    full_name: str
    score: float  # 0.0 to 1.0
    reasons: List[str]  # Why this table was ranked high
    estimated_rows: Optional[int] = None
    column_count: Optional[int] = None
    fk_count: Optional[int] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "schema": self.schema,
            "name": self.name,
            "full_name": self.full_name,
            "score": self.score,
            "reasons": self.reasons,
            "estimated_rows": self.estimated_rows,
            "column_count": self.column_count,
            "fk_count": self.fk_count
        }


class TableRanker:
    """
    Ranks database tables by relevance to user queries.
    
    Uses multiple scoring dimensions:
    - Exact name matches (highest weight)
    - Fuzzy/substring matches
    - Entity keywords in column names
    - Type compatibility with query intent
    - Table connectedness (foreign keys, row volume)
    """
    
    # Scoring weights
    EXACT_MATCH_WEIGHT = 1.0
    ENTITY_MATCH_WEIGHT = 0.8
    COLUMN_MATCH_WEIGHT = 0.6
    FUZZY_MATCH_WEIGHT = 0.4
    FK_BONUS = 0.1  # Bonus for tables with foreign keys
    SIZE_FACTOR = 0.05  # Small bonus for larger tables
    
    # Column type indicators
    NUMERIC_TYPES = {'int', 'float', 'decimal', 'numeric', 'bigint', 'smallint', 'money', 'real'}
    DATE_TYPES = {'date', 'datetime', 'datetime2', 'timestamp', 'time'}
    TEXT_TYPES = {'varchar', 'text', 'nvarchar', 'char', 'string'}
    
    def rank_tables(self,
                   tables: List[Dict],
                   entities: List[str],
                   intent_operations: List[str],
                   catalog_adapter=None) -> List[RankedTable]:
        """
        Rank tables by relevance to query entities and operations.
        
        Args:
            tables: List of table dicts from Scout Mode catalog
            entities: Entities from intent parser (e.g., ['customer', 'order'])
            intent_operations: Operations from intent parser (e.g., ['count', 'sum'])
            catalog_adapter: Optional adapter to fetch column details
        
        Returns:
            List of RankedTable sorted by score (highest first)
        """
        ranked: List[RankedTable] = []
        
        for table in tables:
            score = 0.0
            reasons: List[str] = []
            
            # Extract table info (handle both dict and object formats)
            schema = table.get('schema') if isinstance(table, dict) else getattr(table, 'schema', '')
            name = table.get('name') if isinstance(table, dict) else getattr(table, 'name', '')
            full_name = table.get('full_name') if isinstance(table, dict) else getattr(table, 'full_name', '')
            estimated_rows = table.get('estimated_rows') if isinstance(table, dict) else getattr(table, 'estimated_rows', None)
            column_count = table.get('column_count') if isinstance(table, dict) else getattr(table, 'column_count', None)
            fk_count = table.get('fk_count') if isinstance(table, dict) else getattr(table, 'fk_count', None)
            
            # 1. Score based on entity matches in table name
            for entity in entities:
                if entity.lower() in name.lower():
                    if entity.lower() == name.lower():
                        # Exact match
                        score += self.EXACT_MATCH_WEIGHT
                        reasons.append(f"Exact match for entity: {entity}")
                    elif entity.lower() in name.lower().split('_'):
                        # Full word match
                        score += self.ENTITY_MATCH_WEIGHT
                        reasons.append(f"Entity match in table name: {entity}")
                    else:
                        # Substring match
                        score += self.COLUMN_MATCH_WEIGHT
                        reasons.append(f"Substring match for entity: {entity}")
            
            # 2. Score based on fuzzy matching
            for entity in entities:
                fuzzy_score = self._fuzzy_match(entity, name)
                if fuzzy_score > 0.6:
                    score += fuzzy_score * self.FUZZY_MATCH_WEIGHT
                    reasons.append(f"Fuzzy match ({fuzzy_score:.2f}): {entity} ~ {name}")
            
            # 3. Score based on type compatibility
            type_score = self._score_type_compatibility(name, intent_operations, catalog_adapter, table)
            if type_score > 0:
                score += type_score
                reasons.append(f"Type compatible for operations: {', '.join(intent_operations)}")
            
            # 4. Bonus for connectedness (foreign keys)
            if fk_count and fk_count > 0:
                score += self.FK_BONUS * min(fk_count / 5, 1.0)  # Cap at 5 FKs
                reasons.append(f"Well-connected ({fk_count} foreign keys)")
            
            # 5. Small bonus for larger tables (more likely to be central)
            if estimated_rows and estimated_rows > 1000:
                size_bonus = min(estimated_rows / 100000, 1.0) * self.SIZE_FACTOR
                score += size_bonus
                reasons.append(f"Sizeable table ({estimated_rows} rows)")
            
            # Only include tables with some relevance
            if score > 0 or not entities:
                ranked.append(RankedTable(
                    schema=schema,
                    name=name,
                    full_name=full_name,
                    score=min(score, 1.0),  # Cap at 1.0
                    reasons=reasons,
                    estimated_rows=estimated_rows,
                    column_count=column_count,
                    fk_count=fk_count
                ))
        
        # Sort by score (highest first), then by table name for consistency
        ranked.sort(key=lambda t: (-t.score, t.name))
        
        return ranked
    
    def _fuzzy_match(self, entity: str, table_name: str) -> float:
        """
        Calculate fuzzy match score between entity and table name.
        
        Args:
            entity: User's entity keyword
            table_name: Database table name
        
        Returns:
            Score from 0 to 1, where 1 is perfect match
        """
        entity_lower = entity.lower()
        table_lower = table_name.lower()
        
        # Direct substring match
        if entity_lower in table_lower or table_lower in entity_lower:
            return 0.9
        
        # Use sequence matcher for fuzzy similarity
        matcher = SequenceMatcher(None, entity_lower, table_lower)
        return matcher.ratio()
    
    def _score_type_compatibility(self,
                                 table_name: str,
                                 operations: List[str],
                                 catalog_adapter,
                                 table: Dict) -> float:
        """
        Score how well table matches required operations.
        
        Args:
            table_name: Name of table to score
            operations: Operations needed (e.g., ['sum', 'count'])
            catalog_adapter: Optional adapter to fetch column types
            table: Table dict from catalog
        
        Returns:
            Compatibility score
        """
        if not operations:
            return 0.2  # Small baseline for no specific operations
        
        score = 0.0
        
        # Check for operations that need numeric columns
        if any(op in ['sum', 'avg', 'average', 'max', 'min', 'total'] for op in operations):
            # Heuristically detect numeric tables by name or try to fetch columns
            if self._has_numeric_indicator(table_name):
                score += 0.3
            elif catalog_adapter:
                try:
                    columns = catalog_adapter.get_table(table['schema'], table['name']).get('columns', [])
                    numeric_cols = sum(1 for c in columns if self._is_numeric_type(c.get('type', '')))
                    if numeric_cols > 0:
                        score += 0.3 * (numeric_cols / max(len(columns), 1))
                except:
                    pass
        
        # Check for operations that need date columns
        if any(op in ['trend', 'trend_over_time', 'monthly', 'yearly'] for op in operations):
            if self._has_date_indicator(table_name):
                score += 0.3
            elif catalog_adapter:
                try:
                    columns = catalog_adapter.get_table(table['schema'], table['name']).get('columns', [])
                    date_cols = sum(1 for c in columns if self._is_date_type(c.get('type', '')))
                    if date_cols > 0:
                        score += 0.3
                except:
                    pass
        
        # General compatibility
        if operations:
            score += 0.1
        
        return min(score, 1.0)
    
    def _has_numeric_indicator(self, table_name: str) -> bool:
        """Check if table name suggests numeric data."""
        indicators = ['sales', 'revenue', 'profit', 'cost', 'amount', 'price', 'quantity', 'count']
        return any(indicator in table_name.lower() for indicator in indicators)
    
    def _has_date_indicator(self, table_name: str) -> bool:
        """Check if table name suggests time-series data."""
        indicators = ['sales', 'order', 'transaction', 'event', 'log', 'history']
        return any(indicator in table_name.lower() for indicator in indicators)
    
    def _is_numeric_type(self, col_type: str) -> bool:
        """Check if column type is numeric."""
        col_type_lower = col_type.lower()
        return any(num_type in col_type_lower for num_type in self.NUMERIC_TYPES)
    
    def _is_date_type(self, col_type: str) -> bool:
        """Check if column type is date/time."""
        col_type_lower = col_type.lower()
        return any(date_type in col_type_lower for date_type in self.DATE_TYPES)
    
    def select_best_tables(self,
                          ranked_tables: List[RankedTable],
                          max_tables: int = 3,
                          min_score: float = 0.3) -> List[RankedTable]:
        """
        Select best tables for query execution.
        
        Args:
            ranked_tables: Pre-ranked tables
            max_tables: Maximum number of tables to select
            min_score: Minimum score threshold
        
        Returns:
            List of best tables meeting criteria
        """
        # Filter by minimum score
        qualified = [t for t in ranked_tables if t.score >= min_score]
        
        # Return top N
        return qualified[:max_tables]


def rank_tables(tables: List[Dict],
               entities: List[str],
               operations: List[str] = None,
               catalog_adapter=None) -> List[RankedTable]:
    """
    Convenience function to rank tables.
    
    Args:
        tables: List of table dicts
        entities: Entity keywords from query
        operations: Operations from query
        catalog_adapter: Optional catalog adapter
    
    Returns:
        List of ranked tables
    """
    ranker = TableRanker()
    return ranker.rank_tables(tables, entities, operations or [], catalog_adapter)