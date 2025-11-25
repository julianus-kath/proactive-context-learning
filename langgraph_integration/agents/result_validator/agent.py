"""
Result Validator Agent - Phase 10a

Deterministic validation of execution results to catch:
1. Zero rows (distinguish real empty vs. wrong table)
2. Too many rows (truncated results)
3. Schema mismatches (unexpected columns)
4. All NULL values (likely join issues)
5. Suspicious patterns (all same value, etc.)

This is NOT an LLM agent - it's a deterministic checker.
"""

import logging
import re
from typing import Any, Dict, List, Literal, Optional, TypedDict
from dataclasses import dataclass

from pydantic import ValidationError

from langgraph_integration.contracts.response_envelope import ResponseEnvelope

logger = logging.getLogger(__name__)


class ValidationResult(TypedDict, total=False):
    """Result of validation check."""
    valid: bool  # Whether to pass to Answer agent
    issue: Optional[Literal[
        "zero_rows",
        "too_many_rows",
        "schema_mismatch",
        "all_nulls",
        "suspicious_values",
        "error"
    ]]
    issue_severity: Optional[Literal["warning", "error"]]
    suggestion: Optional[str]
    retry_action: Optional[Literal[
        "accept",
        "ask_user",
        "try_next_candidate",
        "replan_with_aggregation",
        "replan_with_filter"
    ]]
    clarification_question: Optional[str]


@dataclass
class ValidatorConfig:
    """Configuration for ResultValidator."""
    zero_row_confidence_threshold: float = 0.7
    too_many_row_threshold: int = 5000
    check_schema_mismatch: bool = True
    check_null_values: bool = True
    check_suspicious_patterns: bool = True


class ResultValidator:
    """
    Deterministic validation of execution results.
    
    Checks:
    1. Zero rows + low confidence intent = probably wrong table
    2. Too many rows = probably missing aggregation
    3. Schema mismatch = returned columns unexpected
    4. All NULLs = probably bad join
    5. Suspicious values = all same, NaN, etc.
    """
    
    def __init__(self, config: Optional[ValidatorConfig] = None):
        """Initialize validator with optional config."""
        self.config = config or ValidatorConfig()
        logger.info("🔍 ResultValidator initialized")
    
    def validate(
        self,
        user_query: str,
        intent: Dict[str, Any],
        discovery_results: List[str],
        sql_query: str,
        exec_result: Dict[str, Any],
    ) -> ValidationResult:
        """
        Validate execution result against intent.
        
        Args:
            user_query: Original user question
            intent: Parsed intent from IntentParser
            discovery_results: Tables discovered
            sql_query: SQL query that was executed
        exec_result: Result from execution {ok, data, row_count, truncated, error}
        
        Returns:
            ValidationResult with validity assessment and retry action (if needed)
        """
        logger.debug(f"🔍 [VALIDATE] Checking result for query: '{user_query[:50]}...'")
        
        # Extract useful data
        try:
            envelope = ResponseEnvelope.model_validate(exec_result)
            exec_result = envelope.model_dump(exclude_none=True)
        except ValidationError as exc:
            logger.warning(f"🔍 [VALIDATE] exec_result normalization failed: {exc}")
            exec_result = ResponseEnvelope(ok=False, data=[]).model_dump(exclude_none=True)

        ok = exec_result.get("ok", False)
        rows = exec_result.get("data") or []
        row_count = exec_result.get("row_count", len(rows))
        truncated = exec_result.get("truncated", False)
        error = exec_result.get("error")
        
        # Check 0: Execution error
        if not ok or error:
            logger.warning(f"🔍 [VALIDATE] Execution had error: {error}")
            return {
                "valid": False,
                "issue": "error",
                "issue_severity": "error",
                "suggestion": f"Query execution failed: {error}",
                "retry_action": "try_next_candidate"
            }
        
        # Check 1: Zero rows
        if row_count == 0:
            return self._check_zero_rows(intent, discovery_results, sql_query)
        
        # Check 2: Too many rows
        if truncated or row_count >= self.config.too_many_row_threshold:
            return self._check_too_many_rows(intent)
        
        # Check 3: All NULL values (check before schema to avoid false positives)
        if self.config.check_null_values and rows:
            null_check = self._check_all_nulls(rows)
            if not null_check.get("valid", True):
                return null_check
        
        # Check 4: Schema validation
        if self.config.check_schema_mismatch and rows:
            schema_check = self._check_schema_mismatch(intent, sql_query, rows)
            if not schema_check.get("valid", True):
                return schema_check
        
        # Check 5: Suspicious patterns
        if self.config.check_suspicious_patterns and rows:
            suspicious_check = self._check_suspicious_patterns(rows, intent)
            if not suspicious_check.get("valid", True):
                return suspicious_check
        
        # All checks passed
        logger.info(f"✅ [VALIDATE] Result is valid ({row_count} rows)")
        return {
            "valid": True,
            "issue": None,
            "suggestion": None,
            "retry_action": "accept"
        }
    
    def _check_zero_rows(
        self,
        intent: Dict[str, Any],
        discovery_results: List[str],
        sql_query: str,
    ) -> ValidationResult:
        """
        Check if zero rows is valid or indicates wrong table.
        
        Logic:
        - If intent confidence is low (<0.7) → probably wrong table
        - If metrics include count/sum/total/aggregate → suspicious (should have ≥1 row if table exists)
        - Otherwise → might be legitimately empty
        """
        intent_confidence = intent.get("confidence", 1.0)
        metrics = intent.get("metrics", [])
        
        logger.warning(f"🔍 [VALIDATE] Zero rows detected (confidence: {intent_confidence})")
        
        # Low confidence + zero rows = likely wrong table discovery
        if intent_confidence < self.config.zero_row_confidence_threshold:
            logger.warning(f"🔍 [VALIDATE] Low confidence ({intent_confidence}) + zero rows = try next candidate")
            return {
                "valid": False,
                "issue": "zero_rows",
                "issue_severity": "error",
                "suggestion": f"Zero rows returned, but intent confidence is low ({intent_confidence:.2f}). Likely wrong table was selected.",
                "retry_action": "try_next_candidate"
            }
        
        # Count/sum/total/aggregate metrics returning 0 is suspicious
        # (Should have ≥1 row, even if the count itself is 0 or empty sum)
        if any(m in ["count", "sum", "total", "aggregate"] for m in metrics):
            logger.warning(f"🔍 [VALIDATE] Zero rows for aggregate metric ({metrics}) = suspicious, likely wrong table")
            return {
                "valid": False,
                "issue": "zero_rows",
                "issue_severity": "error",
                "suggestion": f"Aggregate query (metrics: {metrics}) returned 0 rows. Likely wrong table was selected. (SELECT COUNT(*) should always return ≥1 row)",
                "retry_action": "try_next_candidate"
            }

        sql_lower = sql_query.lower()
        time_filter_keywords = [" between ", "date", "monat", "monat.", "jahr", "year", "month"]
        has_time_filter = any(keyword in sql_lower for keyword in time_filter_keywords)
        if has_time_filter:
            tables_preview = ", ".join(discovery_results[:3]) if discovery_results else "the current tables"
            question = (
                "I did not find any rows for the requested time window. "
                "Should I expand the timeframe or look at a different data source?"
            )
            logger.info("🔍 [VALIDATE] Zero rows with time filter → ask user for clarification")
            return {
                "valid": False,
                "issue": "zero_rows",
                "issue_severity": "warning",
                "suggestion": f"No rows matched the current filters. Discovered tables: {tables_preview}.",
                "retry_action": "ask_user",
                "clarification_question": question
            }
 
        # High confidence detail query with zero rows is OK (table exists but is empty or filtered)
        logger.info(f"🔍 [VALIDATE] Zero rows accepted (detail query with high confidence)")
        return {
            "valid": True,
            "issue": "zero_rows",
            "issue_severity": "warning",
            "suggestion": "Query returned 0 rows (table may be empty or filter excluded all rows)",
            "retry_action": "accept"
        }
    
    def _check_too_many_rows(self, intent: Dict[str, Any]) -> ValidationResult:
        """
        Check if truncated result indicates missing aggregation.
        
        Logic:
        - If user asked for count/aggregate → should have 1 row
        - If user asked for details but got truncated → need filter or aggregation
        """
        metrics = intent.get("metrics", [])
        
        logger.warning(f"🔍 [VALIDATE] Too many rows (>= {self.config.too_many_row_threshold})")
        
        # If user asked for count, should get 1 row
        if "count" in metrics or "aggregate" in metrics:
            logger.warning(f"🔍 [VALIDATE] Truncated result for count/aggregate query")
            return {
                "valid": False,
                "issue": "too_many_rows",
                "issue_severity": "error",
                "suggestion": "Expected aggregated result (1 row), but query returned many rows (truncated). SQL generator may have omitted GROUP BY.",
                "retry_action": "replan_with_aggregation"
            }
        
        # Otherwise, user wanted details but got too many
        logger.warning(f"🔍 [VALIDATE] Too many rows for detail query = need filter")
        return {
            "valid": False,
            "issue": "too_many_rows",
            "issue_severity": "warning",
            "suggestion": "Result was truncated (too many rows). Need to add filter or aggregation.",
            "retry_action": "replan_with_filter"
        }
    
    def _check_schema_mismatch(
        self,
        intent: Dict[str, Any],
        sql_query: str,
        rows: List[Dict[str, Any]]
    ) -> ValidationResult:
        """
        Check if returned columns match expected columns.
        
        Logic:
        - Extract expected columns from SQL (SELECT clause)
        - Get actual columns from result
        - If very little overlap → schema mismatch
        
        Note: This is a naive check. For complex queries with aliases,
        it may produce false positives/negatives.
        """
        if not rows:
            return {"valid": True}
        
        # Extract expected columns from SQL (naive parsing)
        expected_columns = self._extract_expected_columns_from_sql(sql_query)
        actual_columns = set(rows[0].keys())
        
        # If we have expected columns, validate
        if expected_columns and actual_columns:
            # Check overlap - allow some fuzziness for aliases
            # If > 30% of expected columns are missing, flag it
            overlap = expected_columns & actual_columns
            coverage = len(overlap) / len(expected_columns) if expected_columns else 1.0
            
            if coverage < 0.3 and len(actual_columns) > 0:  # At least check we got some columns
                logger.warning(f"🔍 [VALIDATE] Schema mismatch: expected {expected_columns}, got {actual_columns}, coverage={coverage:.2f}")
                return {
                    "valid": False,
                    "issue": "schema_mismatch",
                    "issue_severity": "error",
                    "suggestion": f"Expected columns {expected_columns}, but got {actual_columns}. Likely wrong table.",
                    "retry_action": "try_next_candidate"
                }
        
        return {"valid": True}
    
    def _check_all_nulls(self, rows: List[Dict[str, Any]]) -> ValidationResult:
        """
        Check if all values in ALL ROWS are NULL.
        
        This usually indicates a failed join or wrong column selection.
        """
        if not rows:
            return {"valid": True}
        
        # Check if ALL columns in ALL rows are NULL
        for row in rows:
            for v in row.values():
                if v is not None and v != "NULL":
                    # Found at least one non-NULL value
                    return {"valid": True}
        
        # All values are NULL across all rows
        logger.warning(f"🔍 [VALIDATE] All NULL values in result")
        return {
            "valid": False,
            "issue": "all_nulls",
            "issue_severity": "error",
            "suggestion": "Result contains only NULL values. Likely a failed join or wrong column selection.",
            "retry_action": "try_next_candidate"
        }
    
    def _check_suspicious_patterns(
        self,
        rows: List[Dict[str, Any]],
        intent: Dict[str, Any]
    ) -> ValidationResult:
        """
        Check for suspicious patterns that indicate data issues.
        
        Patterns:
        - All values are the same (except ID columns) AND
        - This pattern appears in ALL rows (not just some)
        
        Note: One unique value among many NULL values is NOT suspicious
        (e.g., Phone: NULL, NULL, "555-1234" is fine).
        """
        if len(rows) < 3:  # Need at least 3 rows to detect suspicious pattern
            return {"valid": True}
        
        # Check if all non-ID columns have same value across ALL rows
        for col_name in rows[0].keys():
            if col_name.lower() in ["id", "pk", "key"]:
                continue  # Skip ID columns
            
            # Get all non-NULL values for this column
            values = [row.get(col_name) for row in rows if row.get(col_name) is not None]
            
            # Only flag if:
            # 1. We have at least 2 non-NULL values (not mostly NULL)
            # 2. All non-NULL values are identical
            if len(values) >= 2 and len(set(str(v) for v in values)) == 1:
                required_action = (intent.get("required_action") or "").lower()
                if required_action in {
                    "topk_sum_by_customer",
                    "topk_sum_by_product",
                    "sum_by_customer",
                    "sum_by_product",
                    "growth_analysis",
                    "comparative_analysis",
                    "ranked_metrics",
                }:
                    continue
                logger.warning(f"🔍 [VALIDATE] Suspicious pattern: all {col_name} values are identical (out of {len(rows)} rows)")
                question = (
                    f"The column '{col_name}' contains the same value in all returned rows. "
                    "Should I refine the query (for example by adding a filter or choosing another metric)?"
                )
                return {
                    "valid": False,
                    "issue": "suspicious_values",
                    "issue_severity": "warning",
                    "suggestion": f"Column {col_name} has {len(values)} identical values across {len(rows)} rows. May indicate incomplete data or wrong table.",
                    "retry_action": "ask_user",
                    "clarification_question": question
                }
        
        return {"valid": True}
    
    @staticmethod
    def _extract_expected_columns_from_sql(sql_query: str) -> set:
        """
        Naive extraction of expected columns from SELECT statement.
        
        This is simple string matching, not full SQL parsing.
        Returns column names without table prefixes (e.g., "Name" not "c.Name").
        """
        try:
            # Find SELECT ... FROM
            sql_upper = sql_query.upper()
            select_idx = sql_upper.find("SELECT")
            from_idx = sql_upper.find("FROM")
            
            if select_idx == -1 or from_idx == -1:
                return set()
            
            select_clause = sql_query[select_idx + 6:from_idx]
            
            # Extract column names (simple: split by comma)
            columns = set()
            for raw_col in select_clause.split(","):
                col = raw_col.strip()
                upper_col = col.upper()
                alias = None

                # Strip leading modifiers (TOP, DISTINCT, ALL)
                if upper_col.startswith("TOP "):
                    col = re.sub(r"^\s*TOP\s+\(?\d+\)?\s+", "", col, flags=re.IGNORECASE)
                    upper_col = col.upper()
                if upper_col.startswith("DISTINCT "):
                    col = re.sub(r"^\s*DISTINCT\s+", "", col, flags=re.IGNORECASE)
                    upper_col = col.upper()
                if upper_col.startswith("ALL "):
                    col = re.sub(r"^\s*ALL\s+", "", col, flags=re.IGNORECASE)
                    upper_col = col.upper()

                if " AS " in upper_col:
                    alias_idx = upper_col.rfind(" AS ")
                    alias = col[alias_idx + 4 :].strip().strip("[]")
                    col = col[:alias_idx].strip()
                # Remove function calls (COUNT(), MAX(), etc.)
                if "(" in col:
                    col = col[col.rfind("(") + 1:col.rfind(")")]
                col = col.strip()
                # Remove table prefix (e.g., "c.Name" -> "Name")
                if "." in col:
                    col = col.split(".")[-1]
                col = col.strip(" []")
                if col and col != "*":
                    columns.add(col)
                if alias:
                    columns.add(alias.strip())
            
            return columns
        except Exception as e:
            logger.debug(f"Could not parse SQL columns: {e}")
            return set()


def build_result_validator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node for result validation.
    
    This is the wrapper that LangGraph calls.
    """
    validator = ResultValidator()
    
    validation = validator.validate(
        user_query=state.get("user_input", ""),
        intent=state.get("intent", {}),
        discovery_results=state.get("relevant_tables", []),
        sql_query=state.get("sql_query", ""),
        exec_result=state.get("exec_result", {})
    )
    
    if "is_valid" not in validation and "valid" in validation:
        validation["is_valid"] = bool(validation.get("valid"))
    
    logger.info(f"🔍 [RESULT_VALIDATOR] Valid={validation.get('valid')}, Action={validation.get('retry_action')}")
    
    state["validation_result"] = validation

    retry_action = validation.get("retry_action")
    if retry_action in {"try_next_candidate", "replan_with_aggregation", "replan_with_filter"}:
        state["error_info"] = None
        # Clear execution artifacts to avoid misleading downstream stages
        state["exec_result"] = {}

    if retry_action == "ask_user":
        intent = state.get("intent") or {}
        intent["operation"] = "clarify"
        intent["needs_clarification"] = True
        question = validation.get("clarification_question") or validation.get("suggestion") or "Could you clarify what you would like to see?"
        intent["clarification_question"] = question
        intent["ambiguity_reason"] = validation.get("suggestion")
        intent["suggested_options"] = state.get("relevant_tables", [])[:3]
        state["intent"] = intent
        logger.info("🔍 [RESULT_VALIDATOR] Escalating to clarification mode")

    return state