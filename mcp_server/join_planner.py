"""
Join Planner for Complex Query Resolution
Phase 5: Automatic multi-table join planning using Scout catalog relationships.

Analyzes foreign key relationships to find optimal join paths between tables,
generating executable SQL for complex business queries that require multiple tables.
"""

import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class JoinPlanner:
    """
    Intelligent join planner using Scout catalog foreign key relationships.

    Features:
    - Graph-based relationship analysis
    - Shortest path join planning
    - Multiple join strategy support
    - SQL generation from join plans
    - Complexity and performance optimization
    """

    def __init__(self, catalog_data: Dict[str, Any]):
        """
        Initialize join planner with Scout catalog data.

        Args:
            catalog_data: Scout catalog containing tables and relationships
        """
        self.catalog = catalog_data
        self.relationships = catalog_data.get("relationships", [])

        # Build relationship graph for efficient path finding
        self._build_relationship_graph()

        logger.info(f"✅ JoinPlanner initialized with {len(self.relationships)} relationships")

    def _build_relationship_graph(self):
        """
        Build bidirectional graph of table relationships for path finding.
        """
        self.graph = defaultdict(list)
        self.reverse_graph = defaultdict(list)

        for rel in self.relationships:
            from_table = rel["from_table"]
            to_table = rel["to_table"]
            from_col = rel["from_column"]
            to_col = rel["to_column"]

            # Add bidirectional edges
            self.graph[from_table].append({
                "to_table": to_table,
                "from_col": from_col,
                "to_col": to_col,
                "type": "FK"
            })

            self.reverse_graph[to_table].append({
                "to_table": from_table,
                "from_col": to_col,
                "to_col": from_col,
                "type": "FK"
            })

    def find_join_path(self, start_tables: List[str], target_entities: List[str], max_hops: int = 3) -> Optional[Dict[str, Any]]:
        """
        Find optimal join path connecting start tables to target entities.

        Args:
            start_tables: Tables we already have access to
            target_entities: Entities we need to reach
            max_hops: Maximum join depth

        Returns:
            Join plan dict or None if no path found
        """
        if not start_tables or not target_entities:
            return None

        logger.debug(f"Finding join path from {start_tables} to reach {target_entities}")

        # Find target tables that contain the entities
        target_tables = self._find_tables_containing_entities(target_entities)

        if not target_tables:
            logger.debug(f"No tables found containing entities: {target_entities}")
            return None

        # Try to find shortest path from any start table to any target table
        best_plan = None
        min_cost = float('inf')

        for start_table in start_tables:
            for target_table in target_tables:
                if start_table == target_table:
                    # Already have the table, no join needed
                    continue

                plan = self._find_shortest_path(start_table, target_table, max_hops)
                if plan and plan["cost"] < min_cost:
                    best_plan = plan
                    min_cost = plan["cost"]

        if best_plan:
            logger.info(f"Found join plan: {best_plan['path']} (cost: {best_plan['cost']})")
            return self._generate_join_plan(best_plan, target_entities)
        else:
            logger.debug(f"No join path found within {max_hops} hops")
            return None

    def _find_tables_containing_entities(self, entities: List[str]) -> List[str]:
        """
        Find tables that contain the specified entities in their names or columns.
        """
        matching_tables = []
        tables = self.catalog.get("tables", {})

        for table_name, table_data in tables.items():
            # Check table name
            table_name_lower = table_name.lower()
            if any(entity.lower() in table_name_lower for entity in entities):
                matching_tables.append(table_name)
                continue

            # Check column names
            columns = table_data.get("columns", [])
            for col in columns:
                col_name = col.get("name", "").lower()
                if any(entity.lower() in col_name for entity in entities):
                    matching_tables.append(table_name)
                    break

        return list(set(matching_tables))  # Remove duplicates

    def _find_shortest_path(self, start_table: str, target_table: str, max_hops: int) -> Optional[Dict[str, Any]]:
        """
        Find shortest path between two tables using BFS.
        """
        if start_table not in self.graph and start_table not in self.reverse_graph:
            return None
        if target_table not in self.graph and target_table not in self.reverse_graph:
            return None

        # BFS with path tracking
        visited = set()
        queue = deque([(start_table, [], 0)])  # (current_table, path, cost)

        while queue:
            current_table, path, cost = queue.popleft()

            if current_table in visited:
                continue
            visited.add(current_table)

            current_path = path + [current_table]

            if current_table == target_table:
                return {
                    "path": current_path,
                    "cost": cost,
                    "hops": len(current_path) - 1
                }

            if cost >= max_hops:
                continue

            # Explore neighbors
            for neighbor in self.graph.get(current_table, []):
                next_table = neighbor["to_table"]
                if next_table not in visited:
                    queue.append((next_table, current_path, cost + 1))

            # Also check reverse relationships
            for neighbor in self.reverse_graph.get(current_table, []):
                next_table = neighbor["to_table"]
                if next_table not in visited:
                    queue.append((next_table, current_path, cost + 1))

        return None

    def _generate_join_plan(self, path_plan: Dict[str, Any], target_entities: List[str]) -> Dict[str, Any]:
        """
        Generate detailed join plan from path information.
        """
        path = path_plan["path"]
        tables = self.catalog.get("tables", {})

        join_plan = {
            "strategy": "multi_table_join",
            "tables": [],
            "joins": [],
            "target_entities": target_entities,
            "estimated_complexity": path_plan["cost"],
            "path": path
        }

        # Add table information
        for i, table_name in enumerate(path):
            table_data = tables.get(table_name, {})
            join_plan["tables"].append({
                "name": table_name,
                "alias": f"t{i}",
                "schema": table_data.get("schema", ""),
                "estimated_rows": table_data.get("estimated_rows", 0)
            })

        # Generate join conditions
        for i in range(len(path) - 1):
            from_table = path[i]
            to_table = path[i + 1]

            # Find relationship between these tables
            join_condition = self._find_join_condition(from_table, to_table)
            if join_condition:
                join_plan["joins"].append({
                    "left_table": f"t{i}",
                    "right_table": f"t{i+1}",
                    "left_column": join_condition["left_col"],
                    "right_column": join_condition["right_col"],
                    "type": "INNER JOIN"
                })

        return join_plan

    def _find_join_condition(self, table1: str, table2: str) -> Optional[Dict[str, str]]:
        """
        Find the join condition between two tables.
        """
        # Check forward relationship
        for rel in self.relationships:
            if rel["from_table"] == table1 and rel["to_table"] == table2:
                return {
                    "left_col": rel["from_column"],
                    "right_col": rel["to_column"]
                }
            elif rel["from_table"] == table2 and rel["to_table"] == table1:
                return {
                    "left_col": rel["to_column"],
                    "right_col": rel["from_column"]
                }

        # No direct relationship found
        return None

    def generate_sql_from_plan(self, join_plan: Dict[str, Any], query_intent: Dict[str, Any]) -> str:
        """
        Generate SQL from join plan and query intent.

        Args:
            join_plan: Join plan from find_join_path
            query_intent: Query intent with metrics, filters, etc.

        Returns:
            Generated SQL string
        """
        tables = join_plan["tables"]
        joins = join_plan["joins"]

        if not tables:
            return ""

        # Build FROM clause with first table
        first_table = tables[0]
        sql = f"SELECT TOP 10 * FROM {first_table['schema']}.{first_table['name']} {first_table['alias']}"

        # Add JOINs
        for join in joins:
            left_table = next(t for t in tables if t["alias"] == join["left_table"])
            right_table = next(t for t in tables if t["alias"] == join["right_table"])

            left_full = f"{left_table['schema']}.{left_table['name']}"
            right_full = f"{right_table['schema']}.{right_table['name']}"

            sql += f"\n{join['type']} {right_full} {join['right_table']} ON "
            sql += f"{join['left_table']}.{join['left_column']} = {join['right_table']}.{join['right_column']}"

        # Add WHERE clause if needed (basic implementation)
        metrics = query_intent.get("metrics", [])
        if "count" in metrics or "total" in metrics:
            # For count queries, just return the count
            sql = sql.replace("SELECT TOP 10 *", "SELECT COUNT(*) as total_count")
        # For other queries, we could add more sophisticated WHERE clauses
        # based on filters in query_intent

        logger.info(f"Generated join SQL: {sql[:100]}...")
        return sql

    def estimate_join_complexity(self, join_plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Estimate the complexity and performance impact of a join plan.
        """
        tables = join_plan["tables"]
        joins = join_plan["joins"]

        complexity = {
            "table_count": len(tables),
            "join_count": len(joins),
            "estimated_rows": 1,
            "performance_rating": "good"
        }

        # Estimate result set size (very rough approximation)
        for table in tables:
            estimated_rows = table.get("estimated_rows", 1000)
            complexity["estimated_rows"] *= max(estimated_rows, 1)

        # Adjust for joins (each join can reduce or expand result set)
        for join in joins:
            # Assume INNER JOIN typically reduces result set
            complexity["estimated_rows"] *= 0.7

        # Performance rating based on complexity
        if len(tables) <= 2:
            complexity["performance_rating"] = "excellent"
        elif len(tables) <= 4:
            complexity["performance_rating"] = "good"
        elif len(tables) <= 6:
            complexity["performance_rating"] = "fair"
        else:
            complexity["performance_rating"] = "poor"

        return complexity
