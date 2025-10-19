"""
Query Blueprint Generator for Answer-first Execution - Phase 7: Autonomous Discovery.

This module generates parameterized SQL query templates based on user intent.
Blueprints are customized query patterns that can be rapidly executed without
requiring the agent to compose SQL from scratch.

Blueprints support:
- SEARCH: Simple SELECT with WHERE filters
- AGGREGATE: GROUP BY with HAVING, common metrics (COUNT, SUM, AVG)
- TREND: Time-series analysis with DATE_TRUNC/DATEPART
- REPORT: Ranking with TOP/LIMIT and sorting
- JOIN: Multi-table queries connecting related entities
- FILTER: Complex WHERE conditions with multiple predicates

Benefits:
- Faster query execution (pre-validated templates)
- Consistent query style
- Type-safe parameter binding
- Dialect adaptation (PostgreSQL vs SQL Server)
"""

import logging
from typing import Dict, List, Optional
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class AggregateFunction(str, Enum):
    """Supported aggregate functions."""
    COUNT = "COUNT"
    SUM = "SUM"
    AVG = "AVG"
    MIN = "MIN"
    MAX = "MAX"


@dataclass
class QueryBlueprint:
    """A parameterized SQL query template."""
    template: str
    parameters: Dict[str, str]  # param_name -> SQL type
    description: str
    intent: str
    dialect: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "template": self.template,
            "parameters": self.parameters,
            "description": self.description,
            "intent": self.intent,
            "dialect": self.dialect
        }


class QueryBlueprintGenerator:
    """
    Generates parameterized SQL query blueprints based on user intent.
    
    Enables rapid query execution without requiring agent to compose SQL.
    """
    
    def __init__(self, dialect: str = "mssql"):
        """
        Initialize generator.
        
        Args:
            dialect: SQL dialect (mssql or postgres)
        """
        self.dialect = dialect
    
    def generate_search_blueprint(self,
                                 table: str,
                                 schema: str = "dbo",
                                 filter_column: Optional[str] = None) -> QueryBlueprint:
        """
        Generate blueprint for SEARCH intent (find specific records).
        
        Args:
            table: Table name to search
            schema: Schema name
            filter_column: Optional column to filter on
        
        Returns:
            QueryBlueprint for search query
        """
        full_table = f"{schema}.{table}"
        
        if filter_column:
            template = f"SELECT TOP 100 * FROM {full_table} WHERE [{filter_column}] = @value"
            parameters = {"@value": "NVARCHAR(MAX)"}
            description = f"Search {table} by {filter_column}"
        else:
            template = f"SELECT TOP 100 * FROM {full_table}"
            parameters = {}
            description = f"List all records in {table}"
        
        return QueryBlueprint(
            template=template,
            parameters=parameters,
            description=description,
            intent="SEARCH",
            dialect=self.dialect
        )
    
    def generate_aggregate_blueprint(self,
                                    table: str,
                                    aggregate_col: str,
                                    aggregate_func: AggregateFunction,
                                    group_by_col: Optional[str] = None,
                                    schema: str = "dbo") -> QueryBlueprint:
        """
        Generate blueprint for AGGREGATE intent (calculate metrics).
        
        Args:
            table: Table name
            aggregate_col: Column to aggregate
            aggregate_func: Aggregation function (COUNT, SUM, AVG, etc.)
            group_by_col: Optional column to group by
            schema: Schema name
        
        Returns:
            QueryBlueprint for aggregate query
        """
        full_table = f"{schema}.{table}"
        safe_agg_col = f"[{aggregate_col}]"
        
        if group_by_col:
            safe_group_col = f"[{group_by_col}]"
            if self.dialect == "postgres":
                template = f"""
                    SELECT {safe_group_col}, {aggregate_func.value}({safe_agg_col}) as aggregated
                    FROM {full_table}
                    WHERE {safe_agg_col} IS NOT NULL
                    GROUP BY {safe_group_col}
                    ORDER BY aggregated DESC
                    LIMIT 100
                """
            else:  # mssql
                template = f"""
                    SELECT TOP 100 {safe_group_col}, {aggregate_func.value}({safe_agg_col}) as aggregated
                    FROM {full_table}
                    WHERE {safe_agg_col} IS NOT NULL
                    GROUP BY {safe_group_col}
                    ORDER BY aggregated DESC
                """
            description = f"{aggregate_func.value}({aggregate_col}) grouped by {group_by_col}"
        else:
            if self.dialect == "postgres":
                template = f"SELECT {aggregate_func.value}({safe_agg_col}) as result FROM {full_table}"
            else:  # mssql
                template = f"SELECT {aggregate_func.value}({safe_agg_col}) as result FROM {full_table}"
            description = f"{aggregate_func.value}({aggregate_col})"
        
        return QueryBlueprint(
            template=template,
            parameters={},
            description=description,
            intent="AGGREGATE",
            dialect=self.dialect
        )
    
    def generate_trend_blueprint(self,
                                table: str,
                                date_col: str,
                                value_col: str,
                                time_unit: str = "MONTH",
                                schema: str = "dbo") -> QueryBlueprint:
        """
        Generate blueprint for TREND intent (time-series analysis).
        
        Args:
            table: Table name
            date_col: Date column for grouping
            value_col: Numeric column to aggregate
            time_unit: Time unit for grouping (YEAR, QUARTER, MONTH, DAY)
            schema: Schema name
        
        Returns:
            QueryBlueprint for trend query
        """
        full_table = f"{schema}.{table}"
        safe_date_col = f"[{date_col}]"
        safe_value_col = f"[{value_col}]"
        
        if self.dialect == "postgres":
            template = f"""
                SELECT 
                    DATE_TRUNC('{time_unit.lower()}', {safe_date_col}) as period,
                    SUM({safe_value_col}) as total,
                    COUNT(*) as count
                FROM {full_table}
                WHERE {safe_date_col} IS NOT NULL
                GROUP BY DATE_TRUNC('{time_unit.lower()}', {safe_date_col})
                ORDER BY period ASC
            """
        else:  # mssql
            if time_unit == "YEAR":
                date_func = f"YEAR({safe_date_col})"
            elif time_unit == "QUARTER":
                date_func = f"DATEPART(QUARTER, {safe_date_col})"
            elif time_unit == "MONTH":
                date_func = f"FORMAT({safe_date_col}, 'yyyy-MM')"
            else:  # DAY
                date_func = f"CAST({safe_date_col} AS DATE)"
            
            template = f"""
                SELECT TOP 1000
                    {date_func} as period,
                    SUM({safe_value_col}) as total,
                    COUNT(*) as count
                FROM {full_table}
                WHERE {safe_date_col} IS NOT NULL
                GROUP BY {date_func}
                ORDER BY period ASC
            """
        
        return QueryBlueprint(
            template=template,
            parameters={},
            description=f"{value_col} trend over {time_unit.lower()}",
            intent="TREND",
            dialect=self.dialect
        )
    
    def generate_report_blueprint(self,
                                 table: str,
                                 rank_col: str,
                                 value_col: str,
                                 limit: int = 10,
                                 schema: str = "dbo") -> QueryBlueprint:
        """
        Generate blueprint for REPORT intent (ranking/top items).
        
        Args:
            table: Table name
            rank_col: Column to rank by
            value_col: Column to display (usually same as rank_col)
            limit: Number of top items
            schema: Schema name
        
        Returns:
            QueryBlueprint for report query
        """
        full_table = f"{schema}.{table}"
        safe_rank_col = f"[{rank_col}]"
        
        if self.dialect == "postgres":
            template = f"""
                SELECT * FROM {full_table}
                ORDER BY {safe_rank_col} DESC
                LIMIT {limit}
            """
        else:  # mssql
            template = f"""
                SELECT TOP {limit} * FROM {full_table}
                ORDER BY {safe_rank_col} DESC
            """
        
        return QueryBlueprint(
            template=template,
            parameters={},
            description=f"Top {limit} by {rank_col}",
            intent="REPORT",
            dialect=self.dialect
        )
    
    def generate_join_blueprint(self,
                               main_table: str,
                               join_table: str,
                               join_condition: str,
                               main_schema: str = "dbo",
                               join_schema: str = "dbo") -> QueryBlueprint:
        """
        Generate blueprint for JOIN intent (combine entities).
        
        Args:
            main_table: Primary table
            join_table: Table to join
            join_condition: Join condition (e.g., "m.id = j.main_id")
            main_schema: Schema of main table
            join_schema: Schema of join table
        
        Returns:
            QueryBlueprint for join query
        """
        main_full = f"{main_schema}.{main_table}"
        join_full = f"{join_schema}.{join_table}"
        
        template = f"""
            SELECT TOP 100
                m.*,
                j.*
            FROM {main_full} m
            INNER JOIN {join_full} j
                ON {join_condition}
            ORDER BY m.id DESC
        """
        
        return QueryBlueprint(
            template=template,
            parameters={},
            description=f"{main_table} with {join_table} details",
            intent="JOIN",
            dialect=self.dialect
        )
    
    def generate_filter_blueprint(self,
                                 table: str,
                                 filter_col: str,
                                 filter_operator: str = "=",
                                 schema: str = "dbo") -> QueryBlueprint:
        """
        Generate blueprint for FILTER intent (apply complex conditions).
        
        Args:
            table: Table name
            filter_col: Column to filter on
            filter_operator: Operator (=, >, <, >=, <=, LIKE, IN, BETWEEN)
            schema: Schema name
        
        Returns:
            QueryBlueprint for filter query
        """
        full_table = f"{schema}.{table}"
        safe_col = f"[{filter_col}]"
        
        if filter_operator == "BETWEEN":
            template = f"SELECT TOP 100 * FROM {full_table} WHERE {safe_col} BETWEEN @min AND @max"
            parameters = {"@min": "NVARCHAR(MAX)", "@max": "NVARCHAR(MAX)"}
        elif filter_operator == "IN":
            template = f"SELECT TOP 100 * FROM {full_table} WHERE {safe_col} IN (@values)"
            parameters = {"@values": "NVARCHAR(MAX)"}
        elif filter_operator == "LIKE":
            template = f"SELECT TOP 100 * FROM {full_table} WHERE {safe_col} LIKE @pattern"
            parameters = {"@pattern": "NVARCHAR(MAX)"}
        else:
            template = f"SELECT TOP 100 * FROM {full_table} WHERE {safe_col} {filter_operator} @value"
            parameters = {"@value": "NVARCHAR(MAX)"}
        
        return QueryBlueprint(
            template=template,
            parameters=parameters,
            description=f"Filter by {filter_col} {filter_operator}",
            intent="FILTER",
            dialect=self.dialect
        )


def generate_blueprint(intent: str,
                      dialect: str = "mssql",
                      **kwargs) -> Optional[QueryBlueprint]:
    """
    Convenience function to generate blueprint based on intent.
    
    Args:
        intent: Intent type (SEARCH, AGGREGATE, TREND, REPORT, JOIN, FILTER)
        dialect: SQL dialect
        **kwargs: Intent-specific parameters
    
    Returns:
        QueryBlueprint or None if intent not recognized
    """
    generator = QueryBlueprintGenerator(dialect=dialect)
    
    if intent == "SEARCH":
        return generator.generate_search_blueprint(**kwargs)
    elif intent == "AGGREGATE":
        return generator.generate_aggregate_blueprint(**kwargs)
    elif intent == "TREND":
        return generator.generate_trend_blueprint(**kwargs)
    elif intent == "REPORT":
        return generator.generate_report_blueprint(**kwargs)
    elif intent == "JOIN":
        return generator.generate_join_blueprint(**kwargs)
    elif intent == "FILTER":
        return generator.generate_filter_blueprint(**kwargs)
    else:
        logger.warning(f"Unknown intent: {intent}")
        return None