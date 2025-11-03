# Add view ranking functionality to the existing table_ranker.py

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from functools import lru_cache
import re

# Table ranking dataclass
@dataclass
class RankedTable:
    """A table with its relevance score and metadata."""
    schema: str
    name: str
    full_name: str
    score: float  # 0.0 to 1.0
    reasons: List[str]  # Why this table was ranked high
    estimated_rows: Optional[int] = None
    column_count: Optional[int] = None
    fk_count: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
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
    Semantic table ranking system for MCP discovery.

    Implements multi-dimensional scoring as described in ADR-0015.
    """

    def __init__(self):
        """Initialize the table ranker with default weights."""
        self.weights = {
            'entity_match': 1.0,
            'fuzzy_match': 0.4,
            'type_compatibility': 0.3,
            'size_bonus': 0.05,
            'fk_bonus': 0.1
        }

    def rank_tables(
        self,
        tables: List[Dict[str, Any]],
        entities: List[str],
        intent_operations: List[str],
        catalog_adapter=None,
    ) -> List[RankedTable]:
        """
        Rank tables based on relevance to query entities and operations.

        Args:
            tables: List of table metadata dicts
            entities: Query entities (e.g., ["customer", "order"])
            intent_operations: Query operations (e.g., ["count", "sum"])
            catalog_adapter: Optional catalog adapter for additional metadata

        Returns:
            List of RankedTable objects sorted by score desc
        """
        ranked_tables = []

        for table in tables:
            score = 0.0
            reasons = []

            # Extract table info
            schema = table.get('schema', 'dbo')
            name = table.get('name', table.get('table_name', ''))
            full_name = table.get('full_name', f"{schema}.{name}")
            estimated_rows = table.get('estimated_rows', 0)
            column_count = table.get('column_count', 0)

            # 1. Entity matching (highest weight)
            entity_score = self._score_entity_match(name, full_name, entities)
            if entity_score > 0:
                score += entity_score * self.weights['entity_match']
                reasons.append(f"Entity match: {entity_score:.2f}")

            # 2. Fuzzy matching for partial matches
            fuzzy_score = self._score_fuzzy_match(name, full_name, entities)
            if fuzzy_score > 0:
                score += fuzzy_score * self.weights['fuzzy_match']
                reasons.append(f"Fuzzy match: {fuzzy_score:.2f}")

            # 3. Type compatibility based on operations
            type_score = self._score_type_compatibility(table, intent_operations)
            if type_score > 0:
                score += type_score * self.weights['type_compatibility']
                reasons.append(f"Type compatibility: {type_score:.2f}")

            # 4. Size bonus for larger tables (more likely to be important)
            if estimated_rows and estimated_rows > 1000:
                size_score = min(estimated_rows / 100000, 1.0)  # Cap at 100k rows
                score += size_score * self.weights['size_bonus']
                reasons.append(f"Size bonus: {size_score:.2f}")

            # 5. FK bonus for well-connected tables
            fk_count = table.get('fk_count', 0)
            if fk_count > 0:
                fk_score = min(fk_count / 5, 1.0)  # Cap at 5 FKs
                score += fk_score * self.weights['fk_bonus']
                reasons.append(f"FK connectivity: {fk_score:.2f}")

            # Cap score at 1.0
            score = min(score, 1.0)

            # Only include tables with meaningful scores
            if score > 0.0:
                ranked_table = RankedTable(
                    schema=schema,
                    name=name,
                    full_name=full_name,
                    score=score,
                    reasons=reasons,
                    estimated_rows=estimated_rows,
                    column_count=column_count,
                    fk_count=fk_count
                )
                ranked_tables.append(ranked_table)

        # Sort by score descending
        ranked_tables.sort(key=lambda x: x.score, reverse=True)
        return ranked_tables

    def _score_entity_match(self, name: str, full_name: str, entities: List[str]) -> float:
        """Score based on exact entity matches in table name."""
        if not entities:
            return 0.0

        name_lower = name.lower()
        full_name_lower = full_name.lower()

        max_score = 0.0
        for entity in entities:
            entity_lower = entity.lower()
            if entity_lower in name_lower or entity_lower in full_name_lower:
                # Exact substring match gets full score
                max_score = max(max_score, 1.0)
            elif any(part in name_lower for part in entity_lower.split('_')):
                # Partial match on underscore-separated parts
                max_score = max(max_score, 0.8)

        return max_score

    def _score_fuzzy_match(self, name: str, full_name: str, entities: List[str]) -> float:
        """Score based on fuzzy/partial matches."""
        if not entities:
            return 0.0

        name_lower = name.lower()
        full_name_lower = full_name.lower()

        max_score = 0.0
        for entity in entities:
            entity_lower = entity.lower()
            # Simple fuzzy matching - could be enhanced with proper fuzzy libraries
            if len(entity_lower) > 3:  # Only for meaningful entities
                # Check for substring matches with some tolerance
                if entity_lower in name_lower:
                    max_score = max(max_score, 0.6)
                elif any(entity_lower.startswith(name_lower[:i]) for i in range(3, len(name_lower))):
                    max_score = max(max_score, 0.3)

        return max_score

    def _score_type_compatibility(self, table: Dict[str, Any], operations: List[str]) -> float:
        """Score based on table's compatibility with query operations."""
        if not operations:
            return 0.0

        score = 0.0

        # Check for aggregation operations
        agg_ops = ['count', 'sum', 'avg', 'min', 'max']
        if any(op in operations for op in agg_ops):
            # Tables with numeric columns are good for aggregation
            numeric_cols = table.get('numeric_columns', [])
            if numeric_cols:
                score += 0.5
            # Tables with many rows suggest they contain data to aggregate
            if table.get('estimated_rows', 0) > 100:
                score += 0.3

        # Check for temporal operations
        temporal_ops = ['trend', 'monthly', 'yearly', 'date', 'time']
        if any(op in operations for op in temporal_ops):
            # Tables with date columns are good for temporal queries
            date_cols = table.get('date_columns', [])
            if date_cols:
                score += 0.6

        return min(score, 1.0)  # Cap at 1.0

# Extend the existing RankedTable class for views
@dataclass
class RankedView:
    """A view with its relevance score and business analysis."""
    schema: str
    name: str
    full_name: str
    score: float  # 0.0 to 1.0
    reasons: List[str]  # Why this view was ranked high
    role_coverage: Dict[str, float]  # Business role scores
    business_analysis: Dict[str, Any]  # Business logic analysis
    complexity: Dict[str, Any]  # Complexity metrics
    estimated_rows: Optional[int] = None
    column_count: Optional[int] = None
    has_rows: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": self.schema,
            "name": self.name,
            "full_name": self.full_name,
            "score": self.score,
            "reasons": self.reasons,
            "role_coverage": self.role_coverage,
            "business_analysis": self.business_analysis,
            "complexity": self.complexity,
            "estimated_rows": self.estimated_rows,
            "column_count": self.column_count,
            "has_rows": self.has_rows,
            "type": "view"
        }


class ViewsRanker:
    """
    Advanced ranker for database views based on business relevance and query intent.

    Prioritizes views that:
    - Match query intent (reporting, analytical, operational)
    - Have appropriate complexity for the use case
    - Contain pre-joined business data
    - Have good data quality indicators
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def rank_views(
        self,
        views: Dict[str, Dict[str, Any]],
        entities: List[str],
        intent_operations: List[str],
        query_context: Dict[str, Any] = None
    ) -> List[RankedView]:
        """
        Rank views by relevance to query intent and entities.

        Args:
            views: Dict of view_name -> view_metadata
            entities: Query entities (customer, product, sales, etc.)
            intent_operations: Query operations (count, sum, aggregate, etc.)
            query_context: Additional query context

        Returns:
            List of RankedView objects sorted by score
        """
        ranked_views: List[RankedView] = []

        for view_name, view_data in views.items():
            score = 0.0
            reasons: List[str] = []

            # Extract view metadata
            schema = view_data.get("schema", "")
            name = view_data.get("name", "")
            full_name = view_data.get("full_name", view_name)
            role_coverage = view_data.get("role_coverage", {})
            business_analysis = view_data.get("business_analysis", {})
            complexity = view_data.get("complexity", {})
            estimated_rows = view_data.get("estimated_rows")
            column_count = view_data.get("column_count")
            has_rows = view_data.get("has_rows", False)

            # 1. Business role alignment
            query_intent = self._infer_query_intent(entities, intent_operations, query_context)
            role_score = self._calculate_role_alignment(role_coverage, query_intent)
            if role_score > 0:
                score += role_score * 0.4  # 40% weight for role alignment
                reasons.append(f"Business role alignment ({query_intent}): {role_score:.2f}")

            # 2. Entity keyword matching in view name and business indicators
            entity_score = self._calculate_entity_match(entities, view_name, business_analysis)
            if entity_score > 0:
                score += entity_score * 0.3  # 30% weight for entity matching
                reasons.append(f"Entity keyword match: {entity_score:.2f}")

            # 3. Data quality and availability
            quality_score = self._calculate_data_quality(view_data)
            score += quality_score * 0.15  # 15% weight for data quality
            if quality_score > 0.5:
                reasons.append("Good data quality indicators")

            # 4. Complexity appropriateness
            complexity_score = self._calculate_complexity_appropriateness(complexity, query_intent)
            score += complexity_score * 0.15  # 15% weight for complexity fit

            # Only include views with meaningful scores
            if score > 0.1:
                ranked_views.append(RankedView(
                    schema=schema,
                    name=name,
                    full_name=full_name,
                    score=min(score, 1.0),  # Cap at 1.0
                    reasons=reasons,
                    role_coverage=role_coverage,
                    business_analysis=business_analysis,
                    complexity=complexity,
                    estimated_rows=estimated_rows,
                    column_count=column_count,
                    has_rows=has_rows
                ))

        # Sort by score descending
        ranked_views.sort(key=lambda x: x.score, reverse=True)

        self.logger.debug(f"Ranked {len(ranked_views)} views for query with entities: {entities}")
        return ranked_views

    def _infer_query_intent(self, entities: List[str], operations: List[str], context: Dict[str, Any] = None) -> str:
        """
        Infer the primary query intent from entities and operations.

        Returns:
            Primary intent: 'reporting', 'analytical', 'operational', or 'general'
        """
        entities_lower = [e.lower() for e in entities or []]
        operations_lower = [op.lower() for op in operations or []]

        # Analytical indicators
        if any(op in operations_lower for op in ['sum', 'avg', 'aggregate', 'analytics']):
            return 'analytical'
        if any(e in entities_lower for e in ['sales', 'revenue', 'profit', 'performance']):
            return 'analytical'

        # Reporting indicators
        if any(op in operations_lower for op in ['report', 'summary', 'dashboard']):
            return 'reporting'
        if len(entities) >= 2 and any(e in entities_lower for e in ['customer', 'product', 'order']):
            return 'reporting'

        # Operational indicators
        if len(entities) == 1 and any(e in entities_lower for e in ['customer', 'product', 'item']):
            return 'operational'

        return 'general'

    def _calculate_role_alignment(self, role_coverage: Dict[str, float], query_intent: str) -> float:
        """
        Calculate how well the view's role coverage matches query intent.
        """
        if not role_coverage:
            return 0.0

        # Direct intent match
        if query_intent in role_coverage:
            return role_coverage[query_intent]

        # Fallback mappings
        intent_mapping = {
            'analytical': ['analytical', 'reporting'],
            'reporting': ['reporting', 'analytical', 'operational'],
            'operational': ['operational', 'reporting'],
            'general': ['reporting', 'operational']
        }

        fallback_roles = intent_mapping.get(query_intent, [])
        best_score = 0.0

        for role in fallback_roles:
            if role in role_coverage:
                best_score = max(best_score, role_coverage[role])

        return best_score

    def _calculate_entity_match(self, entities: List[str], view_name: str, business_analysis: Dict[str, Any]) -> float:
        """
        Calculate entity keyword matching score.
        """
        if not entities:
            return 0.0

        entities_lower = [e.lower() for e in entities]
        view_name_lower = view_name.lower()

        score = 0.0

        # Direct name matching
        for entity in entities_lower:
            if entity in view_name_lower:
                score += 0.6  # Strong match for entity in view name
                break

        # Business indicator matching
        business_indicators = business_analysis.get("business_indicators", [])
        for entity in entities_lower:
            if entity in business_indicators:
                score += 0.4  # Good match for business alignment

        return min(score, 1.0)

    def _calculate_data_quality(self, view_data: Dict[str, Any]) -> float:
        """
        Calculate data quality score based on metadata.
        """
        score = 0.0

        # Has data
        if view_data.get("has_rows", False):
            score += 0.3

        # Reasonable row count (not empty, not too large)
        estimated_rows = view_data.get("estimated_rows", 0)
        if 10 <= estimated_rows <= 1000000:
            score += 0.2

        # Has columns
        if view_data.get("column_count", 0) > 0:
            score += 0.2

        # Recently modified (indicates maintenance)
        if view_data.get("modify_date"):
            score += 0.1

        # Not overly complex (lower maintenance burden)
        complexity = view_data.get("complexity", {})
        if complexity.get("estimated_maintenance_cost") != "high":
            score += 0.2

        return min(score, 1.0)

    def _calculate_complexity_appropriateness(self, complexity: Dict[str, Any], query_intent: str) -> float:
        """
        Calculate if view complexity is appropriate for query intent.
        """
        if not complexity:
            return 0.5  # Neutral score if no complexity data

        maintenance_cost = complexity.get("estimated_maintenance_cost", "low")

        # For analytical queries, prefer more complex views
        if query_intent == 'analytical':
            if maintenance_cost == "high":
                return 0.8  # Complex views good for analytics
            elif maintenance_cost == "medium":
                return 0.6
            else:
                return 0.3  # Simple views may not have enough business logic

        # For operational queries, prefer simpler views
        elif query_intent == 'operational':
            if maintenance_cost == "low":
                return 0.8  # Simple views good for operations
            elif maintenance_cost == "medium":
                return 0.5
            else:
                return 0.2  # Complex views too heavy for operations

        # For reporting, medium complexity is ideal
        elif query_intent == 'reporting':
            if maintenance_cost == "medium":
                return 0.8
            elif maintenance_cost == "low":
                return 0.6
            else:
                return 0.4

        # Default neutral score
        return 0.5


def rank_views(
    views: Dict[str, Dict[str, Any]],
    entities: List[str],
    operations: List[str] | None = None,
    catalog_adapter=None,
) -> List[RankedView]:
    """
    Convenience function to rank views.

    Args:
        views: Dict of view_name -> view_metadata
        entities: Query entities
        operations: Query operations
        catalog_adapter: Optional catalog adapter

    Returns:
        List of RankedView objects
    """
    ranker = ViewsRanker()
    return ranker.rank_views(views, entities, operations or [], {"catalog_adapter": catalog_adapter})