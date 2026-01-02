"""
Answer-first Query Orchestrator - Phase 7.1: Scout Mode Integration.

This module orchestrates the complete answer-first query execution pipeline:
1. Parse user intent (extract entities, operations)
2. Load cached tables from Scout Mode (O(1) disk read)
3. Rank tables by relevance (uses Scout Mode semantic metadata)
4. Generate query blueprint
5. Execute query
6. Format results as natural language answer

Phase 7.1 Enhancement:
- Loads Scout Mode cached catalog instead of querying database
- Eliminates discovery_tools dependency for performance
- All 943 tables ranked in ~50ms (vs 10+ seconds with DB discovery)
- Scales horizontally with table count without performance degradation

This replaces the interactive "clarify questions" flow with immediate
autonomous table discovery and execution.
"""

import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from mcp_server.yellow.intent_parser import parse_intent, IntentType, ParsedIntent
from mcp_server.tools.table_ranker import rank_tables, RankedTable
from mcp_server.green.query_blueprints import generate_blueprint
from mcp_server.green.query_formatter import QueryFormatter
from mcp_server.server.observability import (
    AnswerFirstExecutionMetrics,
    IntentParsingMetrics,
    TableRankingMetrics,
    QueryBlueprintMetrics,
    answer_first_obs
)

logger = logging.getLogger(__name__)


@dataclass
class AnswerFirstResult:
    """Result of answer-first query execution."""
    success: bool
    answer: str  # Natural language answer
    data: Optional[List[Dict[str, Any]]] = None
    intent: Optional[str] = None
    tables_used: Optional[List[str]] = None
    execution_time_ms: float = 0.0
    error_message: Optional[str] = None
    debug_info: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "answer": self.answer,
            "data": self.data,
            "intent": self.intent,
            "tables_used": self.tables_used,
            "execution_time_ms": self.execution_time_ms,
            "error_message": self.error_message,
            "debug_info": self.debug_info
        }


class AnswerFirstOrchestrator:
    """
    Orchestrates answer-first query execution pipeline.
    
    Eliminates interactive clarification by autonomously:
    1. Parsing user intent from natural language
    2. Discovering relevant tables from database schema
    3. Selecting best table(s) for query execution
    4. Generating optimized SQL from blueprints
    5. Formatting results as natural language
    """
    
    def __init__(self,
                 scout_mode=None,
                 db_adapter=None,
                 catalog=None,
                 dialect: str = "mssql",
                 discovery_tools=None):  # Deprecated, kept for backwards compatibility
        """
        Initialize orchestrator.
        
        Phase 7.1: Uses Scout Mode for table discovery (replaces discovery_tools).
        
        Args:
            scout_mode: Scout Mode instance for cached table discovery (primary)
            db_adapter: Database adapter for query execution
            catalog: Catalog instance for table metadata
            dialect: SQL dialect (mssql or postgres)
            discovery_tools: (DEPRECATED) Use scout_mode instead
        """
        self.scout_mode = scout_mode
        self.discovery_tools = discovery_tools  # Deprecated, kept for fallback
        self.db_adapter = db_adapter
        self.catalog = catalog
        self.dialect = dialect
        # Metrics flags for acceptance criteria
        self._attempts: int = 0
        self._needed_clarification: bool = False

    def _normalize_exec_error(self, error_code: Optional[str], error_message: str) -> Dict[str, Any]:
        """Map raw execution errors into normalized hints for targeted clarification."""
        msg = (error_message or "").lower()
        hints: list[str] = []
        code = error_code or "EXECUTION_FAILED"

        if any(k in msg for k in ["column", "does not exist", "invalid column", "unknown column", "invalid identifier"]):
            code = "UNKNOWN_COLUMN"
            hints.append("Which column should be used for this measure or filter?")
        if any(k in msg for k in ["table", "object", "does not exist", "invalid object", "unknown table"]):
            code = "UNKNOWN_TABLE" if code == "EXECUTION_FAILED" else code
            hints.append("Can you confirm the correct table name?")
        if any(k in msg for k in ["convert", "cast", "type", "varchar", "int", "numeric", "date"]):
            code = "TYPE_MISMATCH" if code == "EXECUTION_FAILED" else code
            hints.append("Should we cast the column to a compatible type (e.g., date or numeric)?")
        if not hints:
            hints.append("Please verify involved table/column names.")

        return {"code": code, "message": error_message, "hints": hints[:3]}
    
    async def execute_answer_first(self, query: str) -> AnswerFirstResult:
        """
        Execute query using answer-first pipeline.
        
        Args:
            query: Natural language query from user
        
        Returns:
            AnswerFirstResult with answer and supporting data
        """
        start_time = time.time()
        debug_info = {}
        
        try:
            # Step 1: Parse intent
            logger.info(f"Parsing intent for query: {query[:100]}...")
            intent_start = time.time()
            parsed_intent = parse_intent(query)
            intent_duration = (time.time() - intent_start) * 1000
            
            debug_info["parsed_intent"] = {
                "intent": parsed_intent.intent.value,
                "confidence": parsed_intent.confidence,
                "entities": parsed_intent.entities,
                "operations": parsed_intent.operations
            }
            
            # Log intent parsing
            answer_first_obs.log_intent_parsing(IntentParsingMetrics(
                query_length=len(query),
                intent_detected=parsed_intent.intent.value,
                confidence=parsed_intent.confidence,
                entities_found=len(parsed_intent.entities),
                operations_found=len(parsed_intent.operations),
                duration_ms=intent_duration
            ))
            
            # Step 2: Discover tables (Phase 7.1: Load from Scout Mode cache)
            logger.info(f"Loading tables from Scout Mode cache for intent: {parsed_intent.intent.value}")
            discovery_start = time.time()
            
            # 🆕 Phase 7.1: Try Scout Mode first (O(1) disk read)
            all_tables = []
            cache_used = False
            
            if self.scout_mode:
                try:
                    scout_catalog = self.scout_mode._load_cached_catalog()
                    if scout_catalog:
                        all_tables = scout_catalog.get("tables", [])
                        cache_used = True
                        logger.info(f"✅ Loaded {len(all_tables)} tables from Scout Mode cache")
                except Exception as e:
                    logger.warning(f"Scout Mode cache load failed: {e}, falling back to discovery_tools")
            
            # Fallback to discovery_tools if Scout Mode unavailable
            if not all_tables and self.discovery_tools:
                logger.info("Falling back to discovery_tools for table discovery")
                discovery_result = await self.discovery_tools.list_tables()
                all_tables = discovery_result.get("tables", []) if discovery_result else []
            
            if not all_tables:
                return AnswerFirstResult(
                    success=False,
                    answer="No tables found - Scout Mode cache unavailable and discovery tools not configured",
                    error_message="Unable to discover tables from either Scout Mode or discovery_tools"
                )
            
            discovery_duration = (time.time() - discovery_start) * 1000
            
            debug_info["discovery"] = {
                "total_tables": len(all_tables),
                "discovery_duration_ms": round(discovery_duration, 2),
                "cache_used": cache_used
            }
            
            # Step 3: Rank tables
            logger.info(f"Ranking {len(all_tables)} tables by relevance")
            ranking_start = time.time()
            
            ranked_tables = rank_tables(
                all_tables,
                parsed_intent.entities,
                parsed_intent.operations,
                self.catalog
            )
            ranking_duration = (time.time() - ranking_start) * 1000
            
            # Select top tables
            selected_tables = ranked_tables[:3] if ranked_tables else []
            
            debug_info["ranking"] = {
                "ranked_count": len(ranked_tables),
                "selected_count": len(selected_tables),
                "top_score": ranked_tables[0].score if ranked_tables else 0,
                "ranking_duration_ms": round(ranking_duration, 2)
            }
            
            # Log table ranking
            answer_first_obs.log_table_ranking(TableRankingMetrics(
                total_tables_evaluated=len(all_tables),
                tables_scored_above_threshold=len([t for t in ranked_tables if t.score > 0.3]),
                top_table_score=ranked_tables[0].score if ranked_tables else 0,
                tables_selected=len(selected_tables),
                ranking_duration_ms=ranking_duration
            ))
            
            if not selected_tables:
                return AnswerFirstResult(
                    success=False,
                    answer="No relevant tables found for your query",
                    error_message="Query intent could not be matched to any database tables",
                    debug_info=debug_info
                )
            
            # =========================
            # Reflexion-style loop (Approach 1): plan → sql → validate → (repair?) → validate
            # =========================
            try:
                # Build schema snippet for up to 3 tables using catalog-only describe_table
                schema_snippet = await self._get_schema_snippet([t.full_name for t in selected_tables[:3]])
                debug_info["schema_snippet_tables"] = [t.get("full_name") for t in schema_snippet]

                # Plan blueprint JSON from snippet
                reflex_blueprint = self._plan_blueprint_json(
                    user_query=query,
                    parsed_intent=parsed_intent,
                    selected_tables=selected_tables,
                    schema_snippet=schema_snippet,
                    dialect=self.dialect
                )
                debug_info["reflex_blueprint"] = reflex_blueprint

                if reflex_blueprint and self.db_adapter:
                    # Generate SQL from blueprint
                    sql_1 = self._generate_sql_from_blueprint(reflex_blueprint, schema_snippet)
                    debug_info["sql_initial"] = sql_1

                    # Validate (preflight limit=1)
                    from mcp_server.tools.bounded_query import execute_bounded_query
                    preflight_1 = await execute_bounded_query(
                        query=sql_1,
                        db_adapter=self.db_adapter,
                        dialect=self.dialect,
                        max_rows=1,
                        requested_limit=1,
                        enable_redaction=True
                    )
                    attempts = 1
                    critic_error_code = None

                    if not preflight_1.ok:
                        # One repair attempt
                        norm1 = self._normalize_exec_error(preflight_1.error_code, preflight_1.error_message or "")
                        critic_error_code = norm1.get("code")
                        debug_info["critic_preflight_1"] = norm1
                        sql_2 = self._repair_sql_with_error(sql_1, norm1, schema_snippet, reflex_blueprint)
                        debug_info["sql_repaired"] = sql_2
                        attempts = 2
                        preflight_2 = await execute_bounded_query(
                            query=sql_2,
                            db_adapter=self.db_adapter,
                            dialect=self.dialect,
                            max_rows=1,
                            requested_limit=1,
                            enable_redaction=True
                        )
                        if not preflight_2.ok:
                            # Ask one concise clarification based on hints
                            norm2 = self._normalize_exec_error(preflight_2.error_code, preflight_2.error_message or "")
                            debug_info["critic_preflight_2"] = norm2
                            hint = (norm2.get("hints") or ["Please verify involved table/column names."])[0]
                            self._attempts = attempts
                            self._needed_clarification = True
                            return AnswerFirstResult(
                                success=False,
                                answer=f"Need a quick clarification: {hint}",
                                error_message=f"Validation failed after repair: {norm2.get('message')}",
                                tables_used=[t.full_name for t in selected_tables],
                                debug_info={**debug_info, "attempts": attempts, "critic_error_code": critic_error_code, "needed_clarification": True}
                            )
                        # Preflight 2 OK → execute full SQL
                        rows = await self.db_adapter.fetch(sql_2)
                        exec_duration = (time.time() - intent_start) * 1000  # reuse timing window for simplicity
                        formatter = QueryFormatter(intent=parsed_intent.intent.value)
                        columns = list(rows[0].keys()) if rows else []
                        formatted_result = formatter.format_results(rows, columns, exec_duration, query)
                        total_duration = (time.time() - start_time) * 1000
                        self._attempts = attempts
                        self._needed_clarification = False
                        return AnswerFirstResult(
                            success=True,
                            answer=formatted_result.get("summary", "Query executed successfully"),
                            data=formatted_result.get("data", []),
                            intent=parsed_intent.intent.value,
                            tables_used=[t.full_name for t in selected_tables],
                            execution_time_ms=round(total_duration, 2),
                            debug_info={**debug_info, "attempts": attempts, "needed_clarification": False, "total_duration_ms": round(total_duration, 2)}
                        )
                    else:
                        # Preflight 1 OK → execute full SQL
                        rows = await self.db_adapter.fetch(sql_1)
                        exec_duration = (time.time() - intent_start) * 1000
                        formatter = QueryFormatter(intent=parsed_intent.intent.value)
                        columns = list(rows[0].keys()) if rows else []
                        formatted_result = formatter.format_results(rows, columns, exec_duration, query)
                        total_duration = (time.time() - start_time) * 1000
                        self._attempts = attempts
                        self._needed_clarification = False
                        return AnswerFirstResult(
                            success=True,
                            answer=formatted_result.get("summary", "Query executed successfully"),
                            data=formatted_result.get("data", []),
                            intent=parsed_intent.intent.value,
                            tables_used=[t.full_name for t in selected_tables],
                            execution_time_ms=round(total_duration, 2),
                            debug_info={**debug_info, "attempts": attempts, "needed_clarification": False, "total_duration_ms": round(total_duration, 2)}
                        )
            except Exception as reflex_err:
                logger.info(f"Reflexion loop skipped due to: {reflex_err}")

            # CRITICAL CHECK: If schema_snippet is empty, we CANNOT safely generate SQL
            # because we don't have the actual column names from the database.
            # Fall back to asking user for clarification instead of guessing columns.
            if not schema_snippet:
                logger.error("❌ Cannot proceed: schema_snippet is empty")
                logger.error("   This means describe_table failed for all selected tables")
                logger.error("   Cannot safely generate SQL without knowing actual column names")
                return AnswerFirstResult(
                    success=False,
                    answer="I found matching tables but couldn't retrieve their column information. "
                           "Could you be more specific about which columns or metrics you're looking for?",
                    error_message="Schema metadata retrieval failed for selected tables",
                    tables_used=[t.full_name for t in selected_tables],
                    debug_info={**debug_info, "schema_fetch_failed": True, "selected_table_count": len(selected_tables)}
                )

            # Step 4: Generate query blueprint (fallback legacy path)
            # NOTE: Only reached if schema_snippet WAS successfully fetched
            logger.info(f"Generating query blueprint for intent: {parsed_intent.intent.value}")
            blueprint_start = time.time()
            
            primary_table = selected_tables[0]
            blueprint = self._generate_blueprint_for_intent(
                parsed_intent,
                primary_table,
                selected_tables,
                schema_snippet  # ← PASS schema_snippet to use ACTUAL column names
            )
            blueprint_duration = (time.time() - blueprint_start) * 1000
            
            debug_info["blueprint"] = {
                "intent": parsed_intent.intent.value,
                "table": primary_table.full_name,
                "blueprint_generated": blueprint is not None,
                "blueprint_duration_ms": round(blueprint_duration, 2)
            }
            
            # Log blueprint generation
            answer_first_obs.log_blueprint_generation(QueryBlueprintMetrics(
                intent_type=parsed_intent.intent.value,
                tables_involved=len(selected_tables),
                blueprint_generated=blueprint is not None,
                blueprint_type=blueprint.intent if blueprint else "UNKNOWN",
                generation_duration_ms=blueprint_duration
            ))
            
            if not blueprint:
                return AnswerFirstResult(
                    success=False,
                    answer="Could not generate query for this intent",
                    error_message="Blueprint generation failed",
                    debug_info=debug_info
                )
            
            # Step 5: Execute query with preflight validation (bounded limit=1)
            logger.info(f"Executing query blueprint: {blueprint.description}")
            exec_start = time.time()

            if not self.db_adapter:
                return AnswerFirstResult(
                    success=False,
                    answer="Database not configured",
                    error_message="Database adapter not provided"
                )

            # Preflight validation using bounded query (LIMIT/TOP 1)
            try:
                from mcp_server.tools.bounded_query import execute_bounded_query
            except Exception:
                execute_bounded_query = None

            if execute_bounded_query is not None:
                try:
                    preflight = await execute_bounded_query(
                        query=blueprint.template,
                        db_adapter=self.db_adapter,
                        dialect=self.dialect,
                        max_rows=1,
                        requested_limit=1,
                        enable_redaction=True
                    )
                    if not preflight.ok:
                        # Normalize error for concise clarification
                        norm = self._normalize_exec_error(
                            error_code=preflight.error_code,
                            error_message=preflight.error_message or ""
                        )
                        debug_info["preflight_error"] = norm
                        # Ask a targeted one-line clarification instead of generic fallback
                        hint = norm.get("hints", ["Please verify involved table/column names."])[0]
                        return AnswerFirstResult(
                            success=False,
                            answer=f"Need a quick clarification: {hint}",
                            error_message=f"Preflight validation failed: {norm.get('message')}",
                            tables_used=[t.full_name for t in selected_tables],
                            debug_info=debug_info
                        )
                except Exception as e:
                    # If preflight infrastructure fails, proceed to normal execution path
                    logger.warning(f"Preflight validation skipped due to error: {e}")

            # Execute the blueprint template (full)
            try:
                rows = await self.db_adapter.fetch(blueprint.template)
            except Exception as e:
                # Normalize runtime error too
                norm = self._normalize_exec_error(error_code="EXECUTION_FAILED", error_message=str(e))
                logger.error(f"Query execution failed: {e}")
                return AnswerFirstResult(
                    success=False,
                    answer=f"Execution error: {norm.get('message')}",
                    error_message=str(e),
                    tables_used=[t.full_name for t in selected_tables],
                    debug_info={**debug_info, "execution_error": norm}
                )

            exec_duration = (time.time() - exec_start) * 1000
            
            # Step 6: Format results
            logger.info(f"Formatting {len(rows)} result rows")
            formatter = QueryFormatter(intent=parsed_intent.intent.value)
            columns = list(rows[0].keys()) if rows else []
            formatted_result = formatter.format_results(rows, columns, exec_duration, query)
            
            # Calculate total duration
            total_duration = (time.time() - start_time) * 1000
            
            # Log end-to-end execution
            answer_first_obs.log_execution(AnswerFirstExecutionMetrics(
                user_query=query,
                intent_parsing_ms=intent_duration,
                table_discovery_ms=discovery_duration,
                table_ranking_ms=ranking_duration,
                blueprint_generation_ms=blueprint_duration,
                query_execution_ms=exec_duration,
                total_duration_ms=total_duration,
                result_row_count=len(rows),
                intent_confidence=parsed_intent.confidence,
                selected_tables=len(selected_tables)
            ))
            
            return AnswerFirstResult(
                success=True,
                answer=formatted_result.get("summary", "Query executed successfully"),
                data=formatted_result.get("data", []),
                intent=parsed_intent.intent.value,
                tables_used=[t.full_name for t in selected_tables],
                execution_time_ms=round(total_duration, 2),
                debug_info={
                    **debug_info,
                    "formatted_result": formatted_result,
                    "total_duration_ms": round(total_duration, 2)
                }
            )
            
        except Exception as e:
            logger.error(f"Answer-first execution failed: {e}", exc_info=True)
            total_duration = (time.time() - start_time) * 1000
            
            return AnswerFirstResult(
                success=False,
                answer=f"Error executing query: {str(e)}",
                error_message=str(e),
                execution_time_ms=round(total_duration, 2),
                debug_info=debug_info
            )
    
    def _generate_blueprint_for_intent(self,
                                      intent: ParsedIntent,
                                      primary_table: RankedTable,
                                      all_tables: List[RankedTable],
                                      schema_snippet: List[Dict[str, Any]]) -> Optional[Dict]:
        """
        Generate appropriate query blueprint based on intent.
        
        CRITICAL: Uses schema_snippet to find ACTUAL column names from the database,
        not assumptions. schema_snippet must be provided and populated.
        
        Args:
            intent: ParsedIntent from parsing
            primary_table: Primary table for query
            all_tables: All selected tables
            schema_snippet: Table descriptions with actual columns and role_hints
        
        Returns:
            QueryBlueprint or None if generation fails
        """
        try:
            # Find the table info for primary_table
            primary_table_info = next(
                (t for t in schema_snippet if t.get("full_name") == primary_table.full_name),
                None
            )
            
            if not primary_table_info:
                logger.warning(f"⚠️ Could not find schema for {primary_table.full_name} in snippet")
                return None
            
            if intent.intent == IntentType.AGGREGATE:
                # Look for numeric column using ACTUAL columns from schema
                numeric_col = self._find_numeric_column(primary_table, primary_table_info)
                if numeric_col:
                    # Look for grouping column if available
                    group_col = self._find_grouping_column(primary_table, intent.entities, primary_table_info)
                    return generate_blueprint(
                        intent="AGGREGATE",
                        dialect=self.dialect,
                        table=primary_table.name,
                        aggregate_col=numeric_col,
                        aggregate_func="SUM",
                        group_by_col=group_col,
                        schema=primary_table.schema
                    )
            
            elif intent.intent == IntentType.TREND:
                # Look for date and numeric columns using ACTUAL columns
                date_col = self._find_date_column(primary_table, primary_table_info)
                numeric_col = self._find_numeric_column(primary_table, primary_table_info)
                if date_col and numeric_col:
                    return generate_blueprint(
                        intent="TREND",
                        dialect=self.dialect,
                        table=primary_table.name,
                        date_col=date_col,
                        value_col=numeric_col,
                        time_unit="MONTH",
                        schema=primary_table.schema
                    )
            
            elif intent.intent == IntentType.REPORT:
                # Look for numeric column to sort by
                numeric_col = self._find_numeric_column(primary_table, primary_table_info)
                if numeric_col:
                    return generate_blueprint(
                        intent="REPORT",
                        dialect=self.dialect,
                        table=primary_table.name,
                        rank_col=numeric_col,
                        value_col=numeric_col,
                        limit=10,
                        schema=primary_table.schema
                    )
            
            elif intent.intent == IntentType.JOIN and len(all_tables) > 1:
                # Use multiple tables
                return generate_blueprint(
                    intent="JOIN",
                    dialect=self.dialect,
                    main_table=all_tables[0].name,
                    join_table=all_tables[1].name,
                    join_condition=f"{all_tables[0].name}.id = {all_tables[1].name}.{all_tables[0].name}_id",
                    main_schema=all_tables[0].schema,
                    join_schema=all_tables[1].schema
                )
            
            else:
                # Default to SEARCH
                return generate_blueprint(
                    intent="SEARCH",
                    dialect=self.dialect,
                    table=primary_table.name,
                    schema=primary_table.schema
                )
        
        except Exception as e:
            logger.warning(f"❌ Blueprint generation failed for {intent.intent}: {e}")
            return None
    
    def _find_numeric_column(self, table: RankedTable, table_info: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Find numeric column for aggregation.
        
        Uses role_hints from schema if available (Phase 1 Scout Mode).
        Falls back to type inspection, then heuristics.
        
        Args:
            table: RankedTable metadata
            table_info: Table description from describe_table() with columns + role_hints
        
        Returns:
            First found numeric column name, or None
        """
        if not table_info:
            return None
        
        columns = table_info.get("columns", [])
        
        # Priority 1: Look for columns with "amount" role hint
        for col in columns:
            if col.get("role_hints") and "amount" in col.get("role_hints", []):
                return col.get("name")
        
        # Priority 2: Look for numeric types (int, float, decimal, etc.)
        numeric_types = ['int', 'bigint', 'float', 'double', 'decimal', 'numeric', 'money']
        for col in columns:
            col_type_lower = (col.get("type") or "").lower()
            if any(t in col_type_lower for t in numeric_types):
                return col.get("name")
        
        # Priority 3: Heuristic - look for column names with amount/price/quantity
        numeric_indicators = ['amount', 'price', 'quantity', 'count', 'total', 'revenue', 'sales', 'betrag', 'menge']
        for col in columns:
            col_name_lower = (col.get("name") or "").lower()
            if any(ind in col_name_lower for ind in numeric_indicators):
                return col.get("name")
        
        return None
    
    def _find_date_column(self, table: RankedTable, table_info: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Find date column for time-based queries.
        
        Uses role_hints from schema if available (Phase 1 Scout Mode).
        Falls back to type inspection, then heuristics.
        
        Args:
            table: RankedTable metadata
            table_info: Table description from describe_table() with columns + role_hints
        
        Returns:
            First found date column name, or None
        """
        if not table_info:
            return None
        
        columns = table_info.get("columns", [])
        
        # Priority 1: Look for columns with "date" role hint
        for col in columns:
            if col.get("role_hints") and "date" in col.get("role_hints", []):
                return col.get("name")
        
        # Priority 2: Look for datetime/date types
        date_types = ['date', 'datetime', 'timestamp', 'datetime2', 'smalldatetime']
        for col in columns:
            col_type_lower = (col.get("type") or "").lower()
            if any(t in col_type_lower for t in date_types):
                return col.get("name")
        
        # Priority 3: Heuristic - look for column names with date indicators
        date_indicators = ['datum', 'date', 'created', 'modified', 'updated', 'timestamp', 'lieferdatum', 'bestelldatum']
        for col in columns:
            col_name_lower = (col.get("name") or "").lower()
            if any(ind in col_name_lower for ind in date_indicators):
                return col.get("name")
        
        return None
    
    def _find_grouping_column(self, table: RankedTable, entities: List[str], table_info: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Find grouping column for GROUP BY.
        
        Uses role_hints from schema if available (Phase 1 Scout Mode).
        Falls back to heuristics.
        
        Args:
            table: RankedTable metadata
            entities: User-mentioned entities to match against
            table_info: Table description from describe_table() with columns + role_hints
        
        Returns:
            Grouping column name, or None
        """
        if not table_info:
            return None
        
        columns = table_info.get("columns", [])
        
        # Priority 1: Look for columns with "status" or "category" role hints
        category_roles = ['status', 'category', 'type', 'code']
        for col in columns:
            if col.get("role_hints"):
                for role in col.get("role_hints", []):
                    if any(cat in role for cat in category_roles):
                        return col.get("name")
        
        # Priority 2: Look for columns matching user entities
        for entity in entities:
            entity_lower = entity.lower()
            for col in columns:
                col_name_lower = (col.get("name") or "").lower()
                if entity_lower in col_name_lower or col_name_lower in entity_lower:
                    return col.get("name")
        
        # Priority 3: Heuristic - look for status/category-like columns
        grouping_indicators = ['status', 'type', 'category', 'region', 'department', 'zustand', 'typ']
        for col in columns:
            col_name_lower = (col.get("name") or "").lower()
            if any(ind in col_name_lower for ind in grouping_indicators):
                return col.get("name")
        
        return None

    async def _get_schema_snippet(self, table_full_names: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch describe_table snippets (catalog-only) for up to 3 tables.
        
        CRITICAL: This must succeed for correct SQL generation. If it fails,
        we cannot generate SQL with actual column names from the schema.
        """
        snippet: List[Dict[str, Any]] = []
        if not table_full_names:
            return snippet
        try:
            from mcp_server.tools.discovery_tools import DiscoveryTools
            for full in table_full_names[:3]:
                try:
                    resp = await DiscoveryTools.describe_table(
                        db_adapter=self.db_adapter,
                        table_name=full,
                        include_sample=False
                    )
                    if getattr(resp, "ok", False) and resp.data:
                        snippet.append(resp.data)
                        logger.info(f"✅ Schema fetched for {full}: {len(resp.data.get('columns', []))} columns")
                    else:
                        logger.warning(f"⚠️ describe_table returned ok=False for {full}: {getattr(resp, 'error', 'unknown')}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to describe {full}: {e}")
        except Exception as e:
            logger.error(f"❌ Schema snippet fetch failed completely: {e}")
        
        if not snippet:
            logger.error(f"❌ CRITICAL: No schema snippets retrieved for tables: {table_full_names}")
        
        return snippet

    def _plan_blueprint_json(self,
                             user_query: str,
                             parsed_intent: ParsedIntent,
                             selected_tables: List[RankedTable],
                             schema_snippet: List[Dict[str, Any]],
                             dialect: str) -> Optional[Dict[str, Any]]:
        """
        Deterministic planner that emits Blueprint JSON using only snippet columns.
        Obeys: use only identifiers present; single fact_table; joins from FKs.
        """
        if not schema_snippet:
            return None
        # Choose fact table: prefer one with measure_suggestions and a date candidate
        def table_score(t: Dict[str, Any]) -> int:
            score = 0
            if t.get("measure_suggestions"): score += 2
            if t.get("time_col_candidates"): score += 1
            return score
        snippet_sorted = sorted(schema_snippet, key=table_score, reverse=True)
        fact = snippet_sorted[0]
        fact_full = fact.get("full_name")
        # Dimensions are the other tables in snippet
        dims = [t.get("full_name") for t in snippet_sorted[1:]]
        # Build joins from foreign keys pointing between snippet tables
        joins: List[Dict[str, str]] = []
        snippet_fulls = {t.get("full_name"): t for t in schema_snippet}
        for t in schema_snippet:
            for fk in t.get("foreign_keys", []) or []:
                ref_full = fk.get("referenced_full_name")
                if ref_full in snippet_fulls:
                    left = f"{t.get('full_name')}.{fk.get('column')}"
                    right = f"{ref_full}.{fk.get('referenced_column')}"
                    joins.append({"left": left, "right": right})
        # Measures
        measures = []
        ms = fact.get("measure_suggestions") or []
        if ms:
            measures.append({
                "name": ms[0].get("name", "metric"),
                "expr": ms[0].get("expr"),
                "agg": ms[0].get("agg", "SUM")
            })
        # Filters: last quarter if date candidate available and intent implies ranking/aggregate
        filters: List[Dict[str, str]] = []
        if fact.get("time_col_candidates"):
            time_col = fact["time_col_candidates"][0]
            filters.append({"expr": self._last_quarter_expr(dialect, time_col, fact_full)})
        # Order and limit
        order_by = []
        if measures:
            order_by = [{"expr": measures[0]["name"], "dir": "DESC"}]
        limit = 5 if "top" in user_query.lower() or parsed_intent.intent.value in ("REPORT", "AGGREGATE") else 10
        return {
            "entities": parsed_intent.entities,
            "fact_table": fact_full,
            "dimensions": dims,
            "joins": joins,
            "measures": measures,
            "filters": filters,
            "order_by": order_by,
            "limit": limit,
            "dialect": dialect
        }

    def _last_quarter_expr(self, dialect: str, time_col: str, fact_full: str) -> str:
        """Return dialect-specific last-quarter filter expression."""
        col = f"{fact_full}.{time_col}"
        if dialect == "postgres":
            return f"{col} >= DATE_TRUNC('quarter', CURRENT_DATE) - INTERVAL '3 months'"
        # mssql default
        return (
            "(" 
            f"{col} >= DATEADD(quarter,-1,DATEFROMPARTS(YEAR(GETDATE()),((DATEPART(quarter,GETDATE())-1)*3)+1,1))"
            ")"
        )

    def _generate_sql_from_blueprint(self, bp: Dict[str, Any], snippet: List[Dict[str, Any]]) -> str:
        """Translate Blueprint JSON into runnable SQL (dialect-aware)."""
        dialect = bp.get("dialect", self.dialect)
        fact = bp["fact_table"]
        dims = bp.get("dimensions", []) or []
        joins = bp.get("joins", []) or []
        measures = bp.get("measures", []) or []
        filters = bp.get("filters", []) or []
        order_by = bp.get("order_by", []) or []
        limit = int(bp.get("limit", 10))
        # Aliases
        alias_map: Dict[str, str] = {fact: "f"}
        for i, d in enumerate(dims):
            alias_map[d] = f"d{i+1}"
        # Build SELECT list
        select_parts: List[str] = []
        if measures:
            m = measures[0]
            select_parts.append(f"{m['agg']}({m['expr']}) AS {m['name']}")
        else:
            select_parts.append("COUNT(*) AS count")
        # FROM and JOINs
        from_clause = f"FROM {fact} f"
        join_clauses: List[str] = []
        for j in joins:
            ltbl = j['left'].rsplit('.', 1)[0]
            rtbl = j['right'].rsplit('.', 1)[0]
            if ltbl in alias_map and rtbl in alias_map:
                lcol = j['left'].split('.')[-1]
                rcol = j['right'].split('.')[-1]
                # Join the non-fact side to the fact when possible
                if ltbl == fact:
                    join_clauses.append(f"INNER JOIN {rtbl} {alias_map[rtbl]} ON f.{lcol} = {alias_map[rtbl]}.{rcol}")
                elif rtbl == fact:
                    join_clauses.append(f"INNER JOIN {ltbl} {alias_map[ltbl]} ON {alias_map[ltbl]}.{lcol} = f.{rcol}")
        # WHERE
        where_parts = [f["expr"] for f in filters if f.get("expr")]
        where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        # ORDER/LIMIT
        order_clause = ""
        if order_by:
            order_expr = order_by[0]["expr"]
            direction = order_by[0].get("dir", "DESC")
            order_clause = f"ORDER BY {order_expr} {direction}"
        if dialect == "postgres":
            limit_clause = f"LIMIT {limit}"
            sql = f"SELECT {', '.join(select_parts)} {from_clause} {' '.join(join_clauses)} {where_clause} {order_clause} {limit_clause}".strip()
        else:  # mssql
            top_prefix = f"TOP {limit} " if measures else f"TOP {limit} "
            # For MSSQL, TOP is part of SELECT
            sql = f"SELECT {top_prefix}{', '.join(select_parts)} {from_clause} {' '.join(join_clauses)} {where_clause} {order_clause}".strip()
        return " ".join(sql.split())

    def _repair_sql_with_error(self,
                               sql: str,
                               norm_error: Dict[str, Any],
                               snippet: List[Dict[str, Any]],
                               bp: Dict[str, Any]) -> str:
        """Attempt a single repair based on normalized error."""
        code = (norm_error.get("code") or "").upper()
        bp2 = dict(bp)
        # If unknown column, try switching time column candidate (if filter used)
        if code == "UNKNOWN_COLUMN":
            fact_full = bp2.get("fact_table")
            fact = next((t for t in snippet if t.get("full_name") == fact_full), None)
            candidates = (fact or {}).get("time_col_candidates") or []
            if len(candidates) > 1:
                # rotate to next candidate
                new_time = candidates[1]
                # Replace filter expr
                bp2["filters"] = [{"expr": self._last_quarter_expr(bp2.get("dialect", self.dialect), new_time, fact_full)}]
                return self._generate_sql_from_blueprint(bp2, snippet)
        if code == "UNKNOWN_TABLE":
            # Ensure fully qualified names are present (already are in blueprint); no-op fallback re-generate
            return self._generate_sql_from_blueprint(bp2, snippet)
        if code == "TYPE_MISMATCH":
            # Try simple CAST around measure expr for safety
            measures = bp2.get("measures") or []
            if measures:
                m = dict(measures[0])
                m["expr"] = f"TRY_CAST({m['expr']} AS FLOAT)"
                bp2["measures"] = [m]
                return self._generate_sql_from_blueprint(bp2, snippet)
        # Default: return original SQL
        return sql