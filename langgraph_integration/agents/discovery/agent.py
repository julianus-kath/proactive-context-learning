"""
DiscoveryAgent - Finds and vets relevant tables/views for queries.

This agent orchestrates the discovery phase:
1. Search tables/views matching user intent
2. Rank candidates by relevance + role coverage + view preference
3. Filter to ≤3 most relevant entities
4. Describe selected entities to build schema snippet
5. Return selected tables + compact schema

Tool-driven (deterministic), with optional LLM tie-breaker.
"""

import json
import logging
import asyncio
import concurrent.futures
from typing import Any, Dict, List, Optional
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from langgraph_integration.contracts.state import BaseState, DiscoveryAgentOutput
from langgraph_integration.mcp_client import MCPDatabaseTool, get_column_index_mcp
from langgraph_integration.prompts.discovery import TABLE_FOCUS_PROMPT, VIEWS_FIRST_GUIDANCE

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Helper to run async functions synchronously for LangGraph node compatibility."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


class DiscoveryAgent:
    """
    Agent for discovering and vetting relevant tables/views.
    
    Input contract: {user_input, intent, session_described_tables}
    Output contract: {relevant_tables, schema_snippet, candidate_views, session_described_tables, error_info}
    """

    def __init__(self, llm_model: str = "gpt-4o", llm_temp: float = 0.0):
        """
        Initialize DiscoveryAgent.
        
        Args:
            llm_model: LLM model name for tie-breaking
            llm_temp: Temperature for LLM (0.0 = deterministic)
        """
        self.mcp = MCPDatabaseTool()
        self.llm = ChatOpenAI(model=llm_model, temperature=llm_temp)
        self.max_candidates_to_describe = 3  # Never describe more than 3 tables
        self.view_role_coverage_threshold = 0.70  # Views-first if coverage >= this
        
    def build_subgraph(self) -> StateGraph:
        """
        Build the LangGraph subgraph for discovery.
        
        Nodes:
        - search_candidates: Search tables/views by keyword
        - rank_candidates: Rank by relevance + role coverage + view preference
        - filter_to_limit: Keep only ≤3 candidates
        - describe_selected: Get detailed metadata for selected tables
        - explore_date_columns: (Optional) Autonomously discover date columns if needed
        - build_schema_snippet: Combine descriptions into compact schema
        - fetch_column_index: CRITICAL: Fetch indexed columns from catalog for each table
        
        Returns:
            Compiled LangGraph subgraph
        """
        from typing import Literal
        
        graph = StateGraph(BaseState)
        
        # Define nodes (wrap async nodes for sync .invoke() compatibility)
        graph.add_node("search_candidates", lambda state: _run_async(self._search_candidates_node(state)))
        graph.add_node("rank_candidates", lambda state: _run_async(self._rank_candidates_node(state)))
        graph.add_node("filter_to_limit", lambda state: _run_async(self._filter_to_limit_node(state)))
        graph.add_node("describe_selected", lambda state: _run_async(self._describe_selected_node(state)))
        graph.add_node("explore_date_columns", lambda state: _run_async(self._explore_date_columns_node(state)))
        graph.add_node("build_schema_snippet", lambda state: _run_async(self._build_schema_snippet_node(state)))
        # 🆕 PHASE 7.2: Fetch indexed columns from Scout Catalog to prevent hallucination
        graph.add_node("fetch_column_index", lambda state: _run_async(self._fetch_column_index_node(state)))
        
        # Define edges
        graph.add_edge("search_candidates", "rank_candidates")
        graph.add_edge("rank_candidates", "filter_to_limit")
        graph.add_edge("filter_to_limit", "describe_selected")
        
        # Conditional routing: explore date columns if needed, else build schema
        def route_to_exploration(state: BaseState) -> Literal["explore_date_columns", "build_schema_snippet"]:
            """Route to explore_date_columns or build_schema_snippet based on intent."""
            intent = state.get("intent", {})
            # Check if this query needs date column exploration
            needs_date_exploration = intent.get("needs_date_exploration", False)
            if needs_date_exploration and not state.get("date_columns_explored", False):
                return "explore_date_columns"
            return "build_schema_snippet"
        
        graph.add_conditional_edges(
            "describe_selected",
            route_to_exploration,
            {
                "explore_date_columns": "explore_date_columns",
                "build_schema_snippet": "build_schema_snippet",
            }
        )
        graph.add_edge("explore_date_columns", "build_schema_snippet")
        # 🆕 After schema snippet is built, ALWAYS fetch column index
        graph.add_edge("build_schema_snippet", "fetch_column_index")
        graph.add_edge("fetch_column_index", END)
        
        # Set entry point
        graph.set_entry_point("search_candidates")
        
        return graph.compile()
    
    async def _search_candidates_node(self, state: BaseState) -> BaseState:
        """
        Search for tables/views matching user intent.
        
        Builds search keywords from:
        - user_input (main query)
        - intent.entities (explicitly mentioned entities)
        
        Prefers views first (role_coverage >= 0.70).
        """
        logger.info("🔍 DiscoveryAgent: Searching candidates...")
        
        user_input = state.get("user_input", "")
        intent = state.get("intent", {})
        
        # Extract search keywords
        keywords = self._extract_keywords(user_input, intent)
        
        if not keywords:
            error = {
                "type": "DISCOVERY_ERROR",
                "message": "Could not extract search keywords from user input",
                "context": {"user_input": user_input}
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}
        
        try:
            # Search for matching tables/views
            candidates = []
            for keyword in keywords:
                logger.debug(f"  Searching for: '{keyword}'")
                try:
                    result = await self.mcp.search_tables(keyword, page=1, page_size=10)
                    parsed = self._parse_search_result(result)
                    candidates.extend(parsed)
                except Exception as e:
                    logger.warning(f"  Search for '{keyword}' failed: {e}")
                    continue
            
            # Deduplicate by table name
            seen = set()
            unique_candidates = []
            for c in candidates:
                table_name = c.get("table_name") or c.get("name") or c.get("full_name", "")
                if table_name not in seen and table_name:
                    seen.add(table_name)
                    unique_candidates.append(c)
            
            if not unique_candidates:
                error = {
                    "type": "NO_CANDIDATES",
                    "message": f"No tables/views found for keywords: {', '.join(keywords)}",
                    "context": {"keywords": keywords}
                }
                logger.warning(f"⚠️  {error['message']}")
                return {**state, "error_info": error}
            
            logger.info(f"✅ Found {len(unique_candidates)} candidate tables/views")
            
            # Store candidates in state for next node
            state["candidate_views"] = unique_candidates
            return state
            
        except Exception as e:
            error = {
                "type": "DISCOVERY_ERROR",
                "message": f"Search failed: {str(e)}",
                "context": {"keywords": keywords, "error": str(e)}
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}
    
    async def _rank_candidates_node(self, state: BaseState) -> BaseState:
        """
        Rank candidates by:
        1. Text similarity score (if available)
        2. Role coverage (views-first >= 0.70)
        3. Has rows (non-empty tables preferred)
        4. Is view bonus (views get +0.05)
        
        Formula: 0.45*text_sim + 0.25*role_coverage + 0.15*subject_match + 0.10*has_rows + 0.05*is_view
        """
        logger.info("📊 DiscoveryAgent: Ranking candidates...")
        
        candidates = state.get("candidate_views", [])
        intent = state.get("intent", {})
        
        if not candidates:
            logger.warning("No candidates to rank")
            return state
        
        try:
            # Score each candidate
            scored = []
            for cand in candidates:
                score = self._score_candidate(cand, intent)
                scored.append({**cand, "score": score})
            
            # Sort by score descending
            scored.sort(key=lambda x: x["score"], reverse=True)
            
            # Log top 3
            for i, c in enumerate(scored[:3]):
                logger.debug(f"  #{i+1}: {c.get('table_name', c.get('name', ''))} (score={c['score']:.3f})")
            
            state["candidate_views"] = scored
            return state
            
        except Exception as e:
            error = {
                "type": "RANKING_ERROR",
                "message": f"Failed to rank candidates: {str(e)}",
                "error": str(e)
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}
    
    async def _filter_to_limit_node(self, state: BaseState) -> BaseState:
        """
        Filter candidates to ≤3 most relevant.
        
        Also apply confidence threshold (score >= 0.30).
        If multiple candidates are tied (score diff < 0.05), optionally use LLM to break tie.
        """
        logger.info("🎯 DiscoveryAgent: Filtering to ≤3 candidates...")
        
        candidates = state.get("candidate_views", [])
        MIN_SCORE = 0.30
        
        if not candidates:
            return state
        
        try:
            # Filter by confidence threshold
            filtered = [c for c in candidates if c.get("score", 0) >= MIN_SCORE]
            
            if not filtered:
                error = {
                    "type": "LOW_CONFIDENCE",
                    "message": f"All candidates scored < {MIN_SCORE}. Top candidate: {candidates[0]}",
                    "context": {"top_candidate": candidates[0] if candidates else None}
                }
                logger.warning(f"⚠️  {error['message']}")
                # Still use the best candidate even if below threshold
                filtered = candidates[:1]
            
            # Limit to ≤3
            selected = filtered[:self.max_candidates_to_describe]
            
            logger.info(f"✅ Selected {len(selected)} candidate(s) for description")
            for i, c in enumerate(selected):
                logger.debug(f"  {i+1}: {c.get('table_name', c.get('name', ''))} (score={c.get('score', 0):.3f})")
            
            state["candidate_views"] = selected
            return state
            
        except Exception as e:
            error = {
                "type": "FILTER_ERROR",
                "message": f"Failed to filter candidates: {str(e)}",
                "error": str(e)
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}
    
    async def _describe_selected_node(self, state: BaseState) -> BaseState:
        """
        Get detailed metadata for each selected candidate.
        
        Calls describe_table for each candidate to get:
        - Columns with role hints
        - Foreign key relationships
        - Row count / has_rows
        - Views-specific: role_coverage, definition preview
        """
        logger.info("📖 DiscoveryAgent: Describing selected candidates...")
        
        candidates = state.get("candidate_views", [])
        session_cache = state.get("session_described_tables", {})
        
        if not candidates:
            logger.warning("No candidates to describe")
            return state
        
        try:
            described = []
            for cand in candidates:
                table_name = cand.get("table_name") or cand.get("name") or cand.get("full_name", "")
                
                # Check cache first
                if table_name in session_cache:
                    logger.debug(f"  {table_name} (cached)")
                    described.append(session_cache[table_name])
                    continue
                
                logger.debug(f"  Describing {table_name}...")
                try:
                    result = await self.mcp.describe_table(table_name, include_sample=False)
                    parsed = self._parse_describe_result(result, table_name)
                    described.append(parsed)
                    session_cache[table_name] = parsed
                except Exception as e:
                    logger.warning(f"  Failed to describe {table_name}: {e}")
                    # Still include the candidate even if describe fails
                    described.append(cand)
            
            logger.info(f"✅ Described {len(described)} table(s)")
            
            state["candidate_views"] = described
            state["session_described_tables"] = session_cache
            return state
            
        except Exception as e:
            error = {
                "type": "DESCRIBE_ERROR",
                "message": f"Failed to describe candidates: {str(e)}",
                "error": str(e)
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}
    
    async def _explore_date_columns_node(self, state: BaseState) -> BaseState:
        """
        Autonomously explore and document available date columns.
        
        Used when a query involves temporal operations (e.g., "when was entry created?")
        but the specific date column is unknown. Instead of asking the user to clarify,
        we autonomously discover what date columns exist in the relevant tables.
        
        This enables the agent to be self-sufficient rather than deferential.
        """
        logger.info("🔍 DiscoveryAgent: Exploring available date columns...")
        
        candidates = state.get("candidate_views", [])
        
        if not candidates:
            logger.info("  No candidates to explore for date columns")
            return state
        
        try:
            date_columns_info = []
            
            for cand in candidates:
                table_name = cand.get("table_name") or cand.get("name") or cand.get("full_name", "")
                columns = cand.get("columns", [])
                
                if not table_name:
                    continue
                
                # Find all date-related columns
                date_cols = []
                for col in columns:
                    col_name = col.get("name", "")
                    col_type = col.get("type", "").lower()
                    role_hint = col.get("role_hint", "").lower()
                    
                    # Check if column is date/time related
                    is_date_type = any(dt in col_type for dt in ["date", "time", "datetime", "timestamp"])
                    is_date_role = "date" in role_hint or "time" in role_hint
                    
                    if is_date_type or is_date_role:
                        date_cols.append({
                            "name": col_name,
                            "type": col.get("type", "unknown"),
                            "role": role_hint or "date/time field"
                        })
                
                if date_cols:
                    date_columns_info.append({
                        "table": table_name,
                        "date_columns": date_cols,
                        "count": len(date_cols)
                    })
            
            logger.info(f"✅ Explored date columns: found {len(date_columns_info)} table(s) with date fields")
            for info in date_columns_info:
                logger.debug(f"  {info['table']}: {len(info['date_columns'])} date column(s)")
                for dc in info['date_columns'][:3]:
                    logger.debug(f"    - {dc['name']} ({dc['type']})")
            
            # Store in state for SQL generation to use
            state["date_columns_available"] = date_columns_info
            state["date_columns_explored"] = True
            
            return state
            
        except Exception as e:
            logger.warning(f"⚠️  Date column exploration failed: {str(e)}")
            # Don't fail the flow, just mark as explored
            state["date_columns_explored"] = True
            return state
    
    async def _build_schema_snippet_node(self, state: BaseState) -> BaseState:
        """
        Build compact schema snippet from described tables.
        
        Format: Simple list of tables with column names and types.
        Includes date column highlights if they were explored.
        
        Example:
        
        dbo.sales_orders: order_id (int), customer_id (int FK), order_date (date), total (decimal)
          └─ Date columns: order_date (date)
        dbo.customers: customer_id (int), name (varchar), email (varchar)
        """
        logger.info("🛠️  DiscoveryAgent: Building schema snippet...")
        
        candidates = state.get("candidate_views", [])
        date_columns_available = state.get("date_columns_available", [])
        
        if not candidates:
            return state
        
        try:
            schema_lines = []
            relevant_tables = []
            
            # Build a quick lookup for date columns
            date_cols_by_table = {}
            for info in date_columns_available:
                table = info.get("table", "")
                date_cols_by_table[table] = info.get("date_columns", [])
            
            for cand in candidates:
                table_name = cand.get("table_name") or cand.get("name") or cand.get("full_name", "")
                columns = cand.get("columns", [])
                
                if not table_name:
                    continue
                
                relevant_tables.append(table_name)
                
                # Build column list: name (type) [role hints]
                col_strs = []
                for col in columns[:10]:  # Limit to 10 columns in snippet
                    col_name = col.get("name", "unknown")
                    col_type = col.get("type", "varchar").lower()
                    role = col.get("role_hint", "")
                    
                    if role:
                        col_strs.append(f"{col_name} ({col_type}, {role})")
                    else:
                        col_strs.append(f"{col_name} ({col_type})")
                
                # Add "..." if more than 10 columns
                if len(columns) > 10:
                    col_strs.append(f"... and {len(columns) - 10} more columns")
                
                schema_line = f"{table_name}: {', '.join(col_strs)}"
                
                # Add date column highlights if explored
                if table_name in date_cols_by_table and date_cols_by_table[table_name]:
                    date_cols = date_cols_by_table[table_name]
                    date_col_names = ", ".join([f"{dc['name']} ({dc['type']})" for dc in date_cols[:3]])
                    schema_line += f"\n  └─ Date columns: {date_col_names}"
                    if len(date_cols) > 3:
                        schema_line += f" (+ {len(date_cols) - 3} more)"
                
                schema_lines.append(schema_line)
            
            schema_snippet = "\n".join(schema_lines)
            
            logger.info(f"✅ Built schema snippet with {len(relevant_tables)} table(s)")
            logger.debug(f"Schema:\n{schema_snippet}")
            
            state["relevant_tables"] = relevant_tables
            state["schema_snippet"] = schema_snippet
            return state
            
        except Exception as e:
            error = {
                "type": "SCHEMA_BUILD_ERROR",
                "message": f"Failed to build schema snippet: {str(e)}",
                "error": str(e)
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}
    
    async def _fetch_column_index_node(self, state: BaseState) -> BaseState:
        """
        🆕 PHASE 7.2: CRITICAL NODE - Fetch indexed columns from Scout Catalog.
        
        This node MUST run after discovery to ensure Planning Agent gets exact columns.
        
        Flow:
        1. Get relevant_tables from state (set by _build_schema_snippet_node)
        2. Call get_column_index_mcp() to fetch structured column mappings
        3. Store in state["column_index"] for Planning Agent to use
        4. Ensures Planning Agent has GUARANTEED access to indexed columns
        
        This prevents hallucination at the root: the LLM gets a hard constraint
        on what columns actually exist, not just hints or suggestions.
        """
        logger.info("🔑 DiscoveryAgent: Fetching column index from catalog...")
        
        relevant_tables = state.get("relevant_tables", [])
        
        if not relevant_tables:
            logger.warning("⚠️  No relevant tables to fetch columns for")
            state["column_index"] = {}
            return state
        
        try:
            logger.info(f"  Fetching columns for: {relevant_tables}")
            
            # 🔑 CRITICAL: Call MCP tool to get indexed columns from Scout Catalog
            column_index = await get_column_index_mcp(relevant_tables)
            
            if not column_index:
                logger.warning("⚠️  Column index fetch returned empty, continuing without it")
                state["column_index"] = {}
                return state
            
            logger.info(f"✅ Successfully fetched column index:")
            for table, columns in column_index.items():
                col_count = len(columns) if isinstance(columns, list) else 0
                logger.info(f"  {table}: {col_count} column(s)")
                if col_count <= 5:
                    logger.debug(f"    Columns: {columns}")
            
            # 🔑 Store in state for Planning Agent to use
            state["column_index"] = column_index
            return state
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch column index: {str(e)}")
            logger.warning("⚠️  Continuing without column index (Planning Agent will fall back)")
            # Don't fail the flow - let Planning Agent handle the fetch if needed
            state["column_index"] = {}
            return state
    
    # Helper methods
    
    def _extract_keywords(self, user_input: str, intent: Dict[str, Any]) -> List[str]:
        """
        Extract search keywords from ParsedIntent (Phase 9).
        
        🆕 CRITICAL FIX (Phase 9):
        - BEFORE: Re-extracted from both intent.entities AND user_input → double extraction, spam
        - AFTER: Uses ONLY intent.keywords_for_discovery (pre-cleaned by IntentParserAgent)
        
        This prevents the "per-word discovery spam" problem where:
        Query "Which products have inventory below 100?" → Used to search: "Which", "products", "inventory", "below"
        Now: Uses only ["products", "inventory"] from intent parser's semantic analysis
        
        Args:
            user_input: Original query (NOT re-parsed, kept for reference only)
            intent: ParsedIntent with keywords_for_discovery (clean, semantic)
            
        Returns:
            List of clean keywords for discovery (no function words)
        """
        
        # 🆕 Phase 9: Use ONLY the clean keywords from ParsedIntent
        # The IntentParserAgent already did semantic analysis and filtering
        # DO NOT re-extract from user_input (that causes double extraction)
        
        keywords = intent.get("keywords_for_discovery", [])
        
        if not keywords:
            # Fallback: if intent parser failed to provide keywords, do minimal fallback
            logger.warning(f"⚠️  No keywords in intent, using fallback extraction")
            keywords = self._fallback_keyword_extraction(user_input)
        
        # Ensure we have valid keywords
        keywords = [k for k in keywords if k and len(k) > 1]
        
        logger.info(f"📌 Using keywords from ParsedIntent: {keywords}")
        return keywords[:5]  # Limit to 5 keywords
    
    def _fallback_keyword_extraction(self, user_input: str) -> List[str]:
        """
        Fallback extraction if intent parser didn't provide keywords.
        
        This should rarely happen, but provides graceful degradation.
        """
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "by", "of", "for", "to", "and", "or", "in", "on", "at",
            "how", "many", "show", "me", "please", "get", "list", "find", "search", "what",
            "have", "has", "had", "do", "does", "did", "with", "from", "as", "it",
            "we", "you", "they", "he", "she", "this", "that", "there",
            "where", "when", "why", "which", "who"
        }
        
        words = user_input.lower().split()
        keywords = []
        for word in words:
            word = word.strip("?,.!;:")
            if word not in stop_words and len(word) > 2:
                keywords.append(word)
        
        return list(dict.fromkeys(keywords))[:5]
    
    def _parse_search_result(self, result: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse MCP search_tables result."""
        if not result or len(result) == 0:
            return []
        
        try:
            content = result[0].get("text", "")
            data = json.loads(content) if isinstance(content, str) else content
            
            # Handle different response formats
            if isinstance(data, dict):
                # Format 1: {results: [...]} or {tables: [...]}
                tables = data.get("results") or data.get("tables", [])
            elif isinstance(data, list):
                tables = data
            else:
                return []
            
            # Normalize table format
            normalized = []
            for t in tables:
                if isinstance(t, dict):
                    normalized.append({
                        "table_name": t.get("table_name") or t.get("name") or t.get("full_name", ""),
                        "score": float(t.get("score", t.get("relevance", 0))),
                        "is_view": t.get("is_view", False),
                        "role_coverage": float(t.get("role_coverage", 0)),
                        "has_rows": t.get("has_rows", True)
                    })
            
            return normalized
        except Exception as e:
            logger.warning(f"Failed to parse search result: {e}")
            return []
    
    def _parse_describe_result(self, result: List[Dict[str, Any]], table_name: str) -> Dict[str, Any]:
        """Parse MCP describe_table result."""
        if not result or len(result) == 0:
            return {"table_name": table_name, "columns": []}
        
        try:
            content = result[0].get("text", "")
            data = json.loads(content) if isinstance(content, str) else content
            
            return {
                "table_name": table_name,
                "columns": data.get("columns", []),
                "row_count": data.get("row_count", 0),
                "has_rows": data.get("has_rows", True),
                "is_view": data.get("is_view", False),
                "role_coverage": float(data.get("role_coverage", 0)),
                "relationships": data.get("relationships", [])
            }
        except Exception as e:
            logger.warning(f"Failed to parse describe result for {table_name}: {e}")
            return {"table_name": table_name, "columns": []}
    
    def _score_candidate(self, candidate: Dict[str, Any], intent: Dict[str, Any]) -> float:
        """
        Score a candidate using hybrid ranking formula.
        
        score = 0.45*text_sim + 0.25*role_coverage + 0.15*subject_match + 0.10*has_rows + 0.05*is_view
        """
        text_sim = float(candidate.get("score", 0)) / 100.0  # Normalize to [0,1]
        role_coverage = float(candidate.get("role_coverage", 0))
        
        # Views-first bonus
        is_view = 1.0 if candidate.get("is_view", False) else 0.0
        
        # Has rows bonus
        has_rows = 1.0 if candidate.get("has_rows", True) else 0.0
        
        # Subject match (TODO: could be enhanced with semantic similarity)
        subject_match = 0.5  # Default neutral
        
        score = (
            0.45 * text_sim
            + 0.25 * role_coverage
            + 0.15 * subject_match
            + 0.10 * has_rows
            + 0.05 * is_view
        )
        
        return min(1.0, score)  # Clamp to [0, 1]


# Exported function to create and run the agent
async def create_discovery_agent(llm_model: str = "gpt-4o") -> DiscoveryAgent:
    """Factory function to create a DiscoveryAgent instance."""
    return DiscoveryAgent(llm_model=llm_model)


# Sync wrapper for LangGraph Studio
def build_discovery_graph():
    """
    Build and return the discovery agent graph for LangGraph Studio.
    
    This is a synchronous function that can be called by langgraph dev CLI.
    All node functions remain async and will be properly awaited by LangGraph at runtime.
    
    Returns:
        Compiled StateGraph for the discovery agent
    """
    agent = DiscoveryAgent()
    return agent.build_subgraph()