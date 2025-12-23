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
import difflib
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from langgraph_integration.contracts.state import BaseState, DiscoveryAgentOutput, merge_error_info
from langgraph_integration.contracts.discovery_models import (
    DiscoveryCandidate,
    DiscoveryOutput,
    DiscoveryRoleHints,
    RoleHintDimension,
    RoleHintFact,
)
from langgraph_integration.mcp_client import get_shared_mcp_tool, get_column_index_mcp, _extract_json_from_text
from langgraph_integration.prompts.discovery import TABLE_FOCUS_PROMPT, VIEWS_FIRST_GUIDANCE
from langgraph_integration.utils.canonical_names import (
    canonical_table_name,
    canonicalize_table_list,
)
from langgraph_integration.utils.runtime_config import (
    get_db_dialect,
    get_db_default_schema,
)

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Helper to run async functions synchronously for LangGraph node compatibility."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a task in the current running loop
            import concurrent.futures
            future = concurrent.futures.Future()

            async def run_and_set():
                try:
                    result = await coro
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)

            # Schedule the task
            asyncio.create_task(run_and_set())
            return future.result()  # This will block until the task completes
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
        self.mcp = get_shared_mcp_tool()
        self.llm = ChatOpenAI(model=llm_model, temperature=llm_temp)
        self.max_candidates_to_describe = 3  # Never describe more than 3 tables
        self.view_role_coverage_threshold = 0.70  # Views-first if coverage >= this

        # Token dictionaries to help infer semantic roles from catalog metadata.
        # These operate on actual table/column identifiers (not fallback keywords).
        self.date_signal_tokens: Set[str] = {
            "date",
            "datum",
            "day",
            "monat",
            "month",
            "jahr",
            "year",
            "woche",
            "week",
            "quarter",
            "quartal",
            "zeit",
            "timestamp",
            "erstellt",
            "created",
            "updated",
            "modified",
        }
        self.id_signal_tokens: Set[str] = {
            "id",
            "nr",
            "nummer",
            "no",
            "key",
            "ident",
            "code",
            "guid",
        }
        self.label_signal_tokens: Set[str] = {
            "name",
            "bezeichnung",
            "beschreibung",
            "desc",
            "title",
            "label",
            "anzeige",
        }

        # Canonical entity mapping to ensure downstream templates can rely on stable keys.
        self.entity_canonical_map = {
            "customer": "customer",
            "customers": "customer",
            "kunde": "customer",
            "kunden": "customer",
            "adress": "customer",
            "adressen": "customer",
            "contact": "customer",
            "contacts": "customer",
            "product": "product",
            "products": "product",
            "produkt": "product",
            "produkte": "product",
            "artikel": "product",
            "artikelstamm": "product",
            "project": "project",
            "projects": "project",
            "projekt": "project",
            "projekte": "project",
        }
        
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
        graph.add_node("search_candidates", self._search_candidates_node)
        graph.add_node("rank_candidates", self._rank_candidates_node)
        graph.add_node("filter_to_limit", self._filter_to_limit_node)
        graph.add_node("describe_selected", self._describe_selected_node)
        graph.add_node("explore_date_columns", self._explore_date_columns_node)
        graph.add_node("build_schema_snippet", self._build_schema_snippet_node)
        # 🆕 PHASE 7.2: Fetch indexed columns from Scout Catalog to prevent hallucination
        graph.add_node("fetch_column_index", self._fetch_column_index_node)
        
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
        logger.critical("🚨🚨🚨 SEARCH_CANDIDATES_NODE IS RUNNING 🚨🚨🚨")
        
        user_input = state.get("user_input", "")
        intent = state.get("intent", {})
        forced_tables = state.get("forced_tables", [])
        seed_tables = state.get("seed_tables", []) or []
        discovery_log = self._get_discovery_log(state)
        
        # 🔄 Check for refinement: If forced_tables are specified, use them directly
        if forced_tables:
            logger.info(f"🔍 [REFINEMENT] Using forced_tables: {forced_tables}")
            # Directly use these tables as candidates instead of searching
            candidates = [{"table_name": t, "full_name": t, "is_forced": True} for t in forced_tables]
            state["relevant_tables"] = candidates
            state["candidate_views"] = []
            
            # Still need to fetch column index and schema for these tables
            try:
                schema_snippets = []
                for table_name in forced_tables:
                    desc = await self.mcp.describe_table(table_name)
                    if desc:
                        schema_snippets.append(f"**{table_name}**: {desc[:200]}...")
                state["schema_snippet"] = "\n".join(schema_snippets) or f"Table(s): {', '.join(forced_tables)}"
                
                # Fetch column index
                column_index = {}
                for table_name in forced_tables:
                    try:
                        cols = await self.mcp.get_columns(table_name)
                        if cols:
                            column_index[table_name] = cols
                    except Exception:
                        pass
                state["column_index"] = column_index
            except Exception as e:
                logger.warning(f"🔍 [REFINEMENT] Could not fetch schema for forced tables: {e}")
                state["schema_snippet"] = f"Table(s): {', '.join(forced_tables)}"
            
            logger.info(f"🔍 [REFINEMENT] ✅ Using {len(forced_tables)} forced table(s)")
            return state
        
        # Extract search keywords
        primary_tokens = self._extract_keywords(user_input, intent)
        discovery_log["search_keywords"] = primary_tokens
        discovery_log.setdefault("events", []).append({
            "stage": "keyword_extraction",
            "tokens": primary_tokens,
        })
        
        if not primary_tokens:
            error = {
                "type": "DISCOVERY_ERROR",
                "message": "Could not extract search keywords from user input",
                "context": {"user_input": user_input}
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}
        
        try:
            # PHASE 5: Use strategic discovery for complex queries
            required_action = intent.get("required_action", "")
            strategic_actions = ["growth_analysis", "department_productivity", "comparative_analysis"]

            candidates: List[Dict[str, Any]] = []
            query_str = user_input
            if required_action in strategic_actions:
                logger.info(f"🔍 [STRATEGIC] Using strategic discovery for {required_action}")
                strategic_candidates = await self._strategic_query_discovery(user_input, intent)
                candidates.extend(strategic_candidates)
            else:
                # Standard search for simple queries
                query_str = " ".join(primary_tokens).strip() or user_input
                if not query_str:
                    query_str = user_input
            logger.debug(f"  Searching primary keywords: '{query_str}'")
            try:
                result = await self.mcp.search_tables(query_str, page=1, page_size=10, intent_data=intent)
                parsed = self._parse_search_result(result)

                # Log raw search results
                logger.info(f"🔍 SEARCH RESULTS for '{query_str}': {len(parsed)} tables found")
                for i, table in enumerate(parsed[:8]):  # Log first 8 results
                    name = table.get('table_name', table.get('name', 'unknown'))
                    score = table.get('relevance_score', 0)
                    rows = table.get('estimated_rows', 0)
                    logger.info(f"  {i+1}. {name} | score={score:.3f} | rows={rows}")

                candidates.extend(parsed)
            except Exception as e:
                logger.warning(f"  Joined search (tables) failed: {e}")
            # Also search views-first and merge results
            try:
                vres = await self.mcp.search_views(query_str, page=1, page_size=10, include_empty=False)
                vparsed = self._parse_search_result(vres)
                for v in vparsed:
                    v["is_view"] = True
                candidates.extend(vparsed)
            except Exception as e:
                logger.warning(f"  Joined search (views) failed: {e}")

            # Intent-driven enrichment (very limited to avoid noise)
            try:
                enrichment_terms = self._enrichment_queries(intent)
                for term in enrichment_terms[:4]:
                    if not term or term.lower() == query_str.lower():
                        continue
                    try:
                        logger.debug(f"  Enrichment search: '{term}'")
                        eres = await self.mcp.search_tables(term, page=1, page_size=5, intent_data=intent)
                        eparsed = self._parse_search_result(eres)
                        candidates.extend(eparsed)
                    except Exception as ee:
                        logger.debug(f"  Enrichment search failed for '{term}': {ee}")
            except Exception as enrich_exc:
                logger.debug(f"  Skipping enrichment search due to error: {enrich_exc}")

            # Deduplicate by table name
            seen = set()
            unique_candidates = []
            for c in candidates:
                table_name = c.get("full_name") or c.get("table_name") or c.get("name") or ""
                if table_name and table_name not in seen:
                    seen.add(table_name)
                    unique_candidates.append(c)
            
            if seed_tables:
                seed_candidates = self._build_seed_candidates(seed_tables, state)
                injected = []
                for cand in seed_candidates:
                    name = cand.get("full_name") or cand.get("table_name") or ""
                    if name and name not in seen:
                        seen.add(name)
                        unique_candidates.append(cand)
                        injected.append(name)
                if injected:
                    logger.info(f"🔍 Added {len(injected)} concept seed tables to candidates")
                    discovery_log.setdefault("events", []).append({
                        "stage": "seed_injection",
                        "tables": injected,
                    })

            # Minimal targeted enrichment: ensure customer master candidate is present for customer + sum intents
            try:
                entities = [e.lower() for e in (intent.get("primary_entities") or [])]
                metrics = [m.lower() for m in (intent.get("metrics") or [])]
                wants_sum = any(m in ["sum", "total"] for m in metrics)
                wants_customers = any(e in ["customer", "customers", "kunde", "kunden"] for e in entities)
                if wants_sum and wants_customers:
                    if all("khkadressen" not in (c.get("table_name","") or "").lower() for c in unique_candidates):
                        logger.debug("  Enriching candidates with explicit 'KHKAdressen' lookup")
                        try:
                            enr = await self.mcp.search_tables("KHKAdressen", page=1, page_size=3, intent_data=intent)
                            eparsed = self._parse_search_result(enr)
                            for ec in eparsed:
                                tname = ec.get("table_name") or ec.get("name")
                                if tname and tname not in seen:
                                    seen.add(tname)
                                    unique_candidates.append(ec)
                        except Exception as ee:
                            logger.debug(f"  KHKAdressen enrichment failed: {ee}")
                if wants_sum and any("umsatz" in k for k in (intent.get("keywords_for_discovery") or [])):
                    try:
                        enr = await self.mcp.search_tables("Umsatz", page=1, page_size=5, intent_data=intent)
                        eparsed = self._parse_search_result(enr)
                        for ec in eparsed:
                            tname = ec.get("table_name") or ec.get("name")
                            if tname and tname not in seen:
                                seen.add(tname)
                                unique_candidates.append(ec)
                    except Exception as ee:
                        logger.debug(f"  Umsatz enrichment failed: {ee}")
            except Exception:
                pass

            # Business-pattern fallback DISABLED; rely on primary joined search only
            logger.info(f"✅ Using primary joined search only: {len(unique_candidates)} candidate(s)")

            # Check if we have meaningful semantic matches (not just size-based ranking)
            semantic_candidates = [c for c in unique_candidates if c.get("relevance_score", 0) > 0.05]
            has_meaningful_matches = len(semantic_candidates) > 0

            if not unique_candidates or not has_meaningful_matches:
                logger.warning(f"⚠️  No semantically relevant tables/views found for keywords: {', '.join(primary_tokens)}")
                logger.info(f"   Found {len(unique_candidates)} candidates, but none with semantic relevance > 0.05")
                fallback_candidates, fallback_source = self._fallback_candidates_from_concepts(state, seen)
                if fallback_candidates:
                    unique_candidates = fallback_candidates
                    logger.info(f"🔄 Using fallback candidates from {fallback_source}")
                    discovery_log.setdefault("events", []).append({
                        "stage": "fallback_candidates",
                        "source": fallback_source,
                        "tables": [c.get("full_name") or c.get("table_name") for c in fallback_candidates],
                    })
                else:
                    discovery_log.setdefault("events", []).append({
                        "stage": "fallback_candidates",
                        "source": "none",
                    })
                    state["candidate_views"] = []
                    return state
            
            logger.info(f"✅ Found {len(unique_candidates)} candidate tables/views")

            # Log all candidates found for debugging
            logger.info("📋 ALL CANDIDATES FOUND:")
            for i, cand in enumerate(unique_candidates[:15]):  # Log first 15 to avoid spam
                name = cand.get('table_name', cand.get('name', 'unknown'))
                score = cand.get('relevance_score', 0)
                rows = cand.get('estimated_rows', 0)
                logger.info(f"  {i+1:2d}. {name} | score={score:.3f} | rows={rows}")
            discovery_log.setdefault("events", []).append({
                "stage": "search_results",
                "count": len(unique_candidates),
            })

            # Store candidates in state for next node
            state["candidate_views"] = unique_candidates
            return state
            
        except Exception as e:
            error = {
                "type": "DISCOVERY_ERROR",
                "message": f"Search failed: {str(e)}",
                "context": {"keywords": primary_tokens, "error": str(e)}
            }
            logger.error(f"❌ {error['message']}")
            return {**state, "error_info": error}

    def _all_candidates_low_relevance(self, candidates: List[Dict[str, Any]]) -> bool:
        """Check if all candidates have low relevance scores."""
        if not candidates:
            return True
        return all(c.get("relevance_score", 0) < 0.4 for c in candidates)

    async def _fallback_business_table_discovery(self) -> List[Dict[str, Any]]:
        """Intelligent, intent-aware fallback discovery for business-relevant tables when semantic search fails."""
        logger.info("🔍 Trying intelligent fallback: searching for tables with relevant data patterns...")

        # Test if MCP search is working at all first
        try:
            logger.debug("🔍 Testing MCP search connectivity...")
            test_result = await self.mcp.search_tables("customer", page=1, page_size=3)
            test_parsed = self._parse_search_result(test_result)
            logger.debug(f"🔍 MCP test search returned {len(test_parsed)} results")
        except Exception as e:
            logger.warning(f"🔍 MCP search test failed: {e}")

        # Intent-aware patterns (prefer entity-focused synonyms if present)
        intent = getattr(self, "_last_intent", None)
        product_synonyms = [
            # German
            "artikel", "artikelstamm", "artikelstammdaten", "artikelliste", "artikelnummer",
            # English
            "product", "products", "item", "items", "material", "inventory"
        ]
        customer_synonyms = [
            "kunde", "kunden", "khkadressen", "customer", "customers", "address"
        ]
        revenue_synonyms = [
            # German sales/revenue domain
            "umsatz", "verkauf", "vk", "vkbeleg", "vkbelege", "vkposition", "vkpositionen",
            "rechnung", "rechnungen", "rechnungsposition", "rechnungspositionen", "beleg", "belege",
            # English
            "revenue", "sales", "invoice", "invoices", "order", "orders", "orderline", "orderlines"
        ]
        project_synonyms = [
            # German/English projects
            "projekt", "projekte", "projekten", "projektliste", "projektstamm", "projects", "project"
        ]
        generic_patterns = []
        # Always seed with core product synonyms to avoid missing German article masters
        seed_patterns = ["artikel", "artikelstamm", "product", "products"]
        generic_patterns.extend(seed_patterns)
        if intent and any(ent.lower().startswith("product") or ent.lower().startswith("artikel") for ent in intent.get("primary_entities", [])):
            generic_patterns.extend([p for p in product_synonyms if p not in generic_patterns])
        elif intent and any(ent.lower().startswith("customer") or ent.lower().startswith("kunde") for ent in intent.get("primary_entities", [])):
            generic_patterns.extend([p for p in customer_synonyms if p not in generic_patterns])
            # If metrics indicate revenue/sum, prepend revenue patterns to bias towards sales data sources
            metrics = [m.lower() for m in (intent.get("metrics") or [])]
            if any(m in ["sum", "total"] for m in metrics) or any(k in (intent.get("keywords_for_discovery") or []) for k in ["revenue", "sales", "umsatz"]):
                generic_patterns = [p for p in revenue_synonyms if p not in generic_patterns] + generic_patterns
        elif intent and any(ent.lower().startswith("project") or ent.lower().startswith("projekt") for ent in intent.get("primary_entities", [])):
            generic_patterns.extend([p for p in project_synonyms if p not in generic_patterns])
        else:
            # Fallback to broad business entities
            generic_patterns.extend(["customer", "order", "transaction", "invoice", "item"]) 

        try:
            logger.debug(f"🔍 Fallback discovery intent: entities={intent.get('primary_entities') if intent else None}, metrics={intent.get('metrics') if intent else None}")
            logger.debug(f"🔍 Fallback discovery patterns: {generic_patterns}")
        except Exception:
            pass

        candidates = []
        for pattern in generic_patterns[:8]:  # Limit searches to avoid overload but broaden slightly
            try:
                logger.debug(f"🔍 Searching for generic pattern: '{pattern}'")
                result = await self.mcp.search_tables(pattern, page=1, page_size=10)
                parsed = self._parse_search_result(result)
                if parsed:
                    logger.debug(f"🔍 Pattern '{pattern}' returned {len(parsed)} results")
                    candidates.extend(parsed)
            except Exception as e:
                logger.debug(f"🔍 Search for '{pattern}' failed: {e}")
                continue

        # Deduplicate and score intelligently
        seen = set()
        unique_candidates = []
        for c in candidates:
            table_name = c.get("full_name") or c.get("table_name") or c.get("name") or ""
            if table_name not in seen and table_name:
                seen.add(table_name)

                # Calculate intelligent relevance score
                base_score = c.get("relevance_score", 0)

                # Bonus for tables with actual data
                data_bonus = 0.3 if c.get("estimated_rows", 0) > 10 else 0

                # Bonus for tables with many columns (more likely to be main tables)
                column_bonus = min(c.get("column_count", 0) / 50, 0.2)

                # Bonus for well-connected tables (FK relationships)
                fk_bonus = min(c.get("fk_count", 0) / 5, 0.2)

                # Penalty for empty tables
                empty_penalty = -0.5 if c.get("estimated_rows", 0) == 0 else 0

                # Intent-aware name bonus/penalty
                name = (c.get("table_name") or c.get("name") or c.get("full_name") or "").lower()
                keyword_bonus = 0.0
                if generic_patterns == product_synonyms:
                    if any(k in name for k in product_synonyms):
                        keyword_bonus += 0.6
                    # De-emphasize obviously unrelated domains
                    if any(x in name for x in ["projekt", "project", "crm", "archiv", "archive"]):
                        keyword_bonus -= 0.4
                elif generic_patterns == customer_synonyms:
                    if any(k in name for k in customer_synonyms + ["adresse", "adressen"]):
                        keyword_bonus += 0.6
                elif generic_patterns == project_synonyms:
                    if any(k in name for k in project_synonyms + ["projektstamm", "projektliste", "projectlist"]):
                        keyword_bonus += 0.6
                
                c["relevance_score"] = base_score + data_bonus + column_bonus + fk_bonus + empty_penalty + keyword_bonus
                c["fallback_discovered"] = True
                unique_candidates.append(c)

        # Sort by intelligent relevance score
        unique_candidates.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        # Filter out very low scoring tables
        good_candidates = [c for c in unique_candidates if c.get("relevance_score", 0) > 0.1]

        # Intent-specific pruning: for product counts, drop project/archive/CRM lists outright
        try:
            if intent and any(ent.lower().startswith(("product", "artikel")) for ent in intent.get("primary_entities", [])):
                filtered = []
                for c in good_candidates:
                    n = (c.get("table_name") or c.get("name") or c.get("full_name") or "").lower()
                    if any(b in n for b in ["projekt", "projektliste", "project", "crm", "archiv", "archive"]):
                        continue
                    filtered.append(c)
                good_candidates = filtered
            # For revenue/sum intents, strongly down-rank archive tables/views
            metrics = [m.lower() for m in (intent.get("metrics") or [])]
            if any(m in ["sum", "total"] for m in metrics) or any(k in (intent.get("keywords_for_discovery") or []) for k in ["revenue", "sales", "umsatz"]):
                filtered = []
                archives = []
                for c in good_candidates:
                    n = (c.get("table_name") or c.get("name") or c.get("full_name") or "").lower()
                    if "archiv" in n or "archive" in n:
                        archives.append(c)
                    else:
                        filtered.append(c)
                # Keep archives only if nothing else remains
                good_candidates = filtered or archives
        except Exception:
            pass

        logger.info(f"📊 Intelligent fallback found {len(good_candidates)} relevant tables:")
        for i, c in enumerate(good_candidates[:8]):
            score = c.get("relevance_score", 0)
            rows = c.get("estimated_rows", 0)
            cols = c.get("column_count", 0)
            logger.info(f"  {i+1}. {c.get('full_name')} (score: {score:.3f}, rows: {rows}, cols: {cols})")

        # Return top candidates (more than before to give better selection)
        return good_candidates[:12]

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
            log_payload = self._get_discovery_log(state)
            log_payload.setdefault("events", []).append({
                "stage": "rank",
                "count": len(scored),
                "top": [
                    {
                        "table": c.get("table_name") or c.get("name"),
                        "score": round(float(c.get("score", 0)), 3),
                    }
                    for c in scored[:5]
                ],
            })
            
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
        MIN_SCORE = 0.0
        
        if not candidates:
            return state

        try:
            def _val(c, key, default=None):
                if isinstance(c, dict):
                    return c.get(key, default)
                if hasattr(c, key):
                    return getattr(c, key)
                return default

            preview = []
            for cand in candidates[:8]:
                name = (
                    _val(cand, "table_name")
                    or _val(cand, "name")
                    or _val(cand, "full_name")
                    or ""
                )
                score = _val(cand, "score", 0.0)
                rows = _val(cand, "estimated_rows")
                preview.append(f"{name} (score={score:.3f}, rows={rows})")
            if preview:
                logger.info("📋 Candidates before filtering: " + "; ".join(preview))
        except Exception as exc:
            logger.info(f"Unable to log candidate preview: {exc}")
        
        try:
            # 🆕 Filter out candidates that have already been tried
            skip_tables = set(state.get("skip_tables", []) or [])
            
            def candidate_name(c: dict) -> str:
                return (
                    c.get("full_name")
                    or c.get("table_name")
                    or c.get("name")
                    or ""
                )
            
            if skip_tables:
                before_skip = len(candidates)
                candidates = [
                    c for c in candidates
                    if candidate_name(c) not in skip_tables
                ]
                after_skip = len(candidates)
                logger.info(
                    f"🔍 [DISCOVERY] Filtering candidates: "
                    f"{before_skip} → {after_skip} "
                    f"(skipping {len(skip_tables)} tried: {list(skip_tables)})"
                )
            
            # Filter by confidence threshold
            filtered = [c for c in candidates if c.get("score", 0) >= MIN_SCORE]
            
            if not filtered:
                error = {
                    "type": "LOW_CONFIDENCE",
                    "message": f"All candidates scored < {MIN_SCORE}. Top candidate: {candidates[0]}",
                    "context": {"top_candidate": candidates[0] if candidates else None}
                }
                logger.warning(f"⚠️  {error['message']}")
                # Targeted fallback: try business-pattern discovery and merge, then re-rank
                try:
                    # Make intent available to fallback discovery
                    try:
                        self._last_intent = intent
                    except Exception:
                        pass
                    alt = await self._fallback_business_table_discovery()
                    if alt:
                        logger.info(f"🔄 Merging {len(alt)} fallback candidate(s) and re-ranking")
                        merged = candidates + alt
                        # Re-score merged
                        re_scored = []
                        for cand in merged:
                            s = self._score_candidate(cand, intent)
                            cand2 = dict(cand)
                            cand2["score"] = s
                            re_scored.append(cand2)
                        # Replace candidates and use threshold
                        candidates = re_scored
                        filtered = [c for c in candidates if c.get("score", 0) >= MIN_SCORE]
                        if not filtered:
                            filtered = sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)[:1]
                    else:
                        # Still use the best candidate even if below threshold
                        filtered = candidates[:1]
                except Exception:
                    # Still use the best candidate even if below threshold
                    filtered = candidates[:1]
            
            # Prefer non-empty entities and higher estimated_rows, then by score
            def rank_key(c):
                has_rows = 1 if c.get("has_rows", False) else 0
                row_count = int(c.get("estimated_rows", 0) or 0)
                score = float(c.get("score", 0.0))

                # Log detailed ranking for top candidates
                if len(filtered) <= 10:  # Only log for smaller result sets to avoid spam
                    table_name = c.get("table_name", c.get("name", "unknown"))
                    logger.info(f"📊 RANKING: {table_name} | has_rows={has_rows} | rows={row_count} | score={score:.3f}")

                return (has_rows, row_count, score)

            # CRITICAL: Intent-specific hard filters before final sort
            # These are AGGRESSIVE filters to ensure archive/admin/config tables NEVER poison results
            try:
                intent = state.get("intent", {}) or {}
                metrics = [m.lower() for m in (intent.get("metrics") or [])]
                entities = [e.lower() for e in (intent.get("primary_entities") or [])]
                keywords = [k.lower() for k in (intent.get("keywords_for_discovery") or [])]
                
                # Helper: is this table an archive/admin/config table?
                def is_junk(c):
                    n = (c.get("table_name") or c.get("name") or c.get("full_name") or "").lower()
                    # Archive tables
                    if any(tok in n for tok in ["archiv", "archive"]):
                        return True
                    # Permission/auth/admin tables
                    if any(tok in n for tok in ["berecht", "berechtigung", "permission", "rechte", "user", "users", "benutzer", "rolle", "role", "zugriff", "auth"]):
                        return True
                    # Config/setup tables
                    if any(tok in n for tok in ["belegart", "belegnummer", "nummernkreis", "config", "konfiguration", "einstellung", "settings"]):
                        return True
                    # Log/audit tables
                    if any(tok in n for tok in ["log", "logs", "audit", "protokoll"]):
                        return True
                    # UI/Grid/Template tables (NOT business data)
                    if any(tok in n for tok in ["grid", "template", "kennzeichen", "druckbeleg", "erfassungstyp", "layout"]):
                        return True
                    # HR / payroll / salary tables (not revenue facts)
                    if any(tok in n for tok in ["personal", "lohn", "abrechnung", "salary", "payroll"]):
                        return True
                    return False
                
                # For customer COUNT: drop ALL junk, prefer master address/customer tables
                if ("count" in metrics) and any(e in ["customer", "customers", "kunde", "kunden"] for e in entities + keywords):
                    logger.info("🎯 Filtering for customer COUNT intent")
                    # Step 1: Drop ALL junk tables
                    junk_dropped = [c for c in filtered if is_junk(c)]
                    filtered = [c for c in filtered if not is_junk(c)] or junk_dropped[:1]  # Keep 1 junk ONLY if nothing else
                    if junk_dropped:
                        logger.info(f"🧹 Dropped {len(junk_dropped)} junk tables for customer count (kept {len(filtered)})")
                    # Step 2: Prefer master customer tables
                    def is_customer_master(c):
                        n = (c.get("table_name") or c.get("name") or c.get("full_name") or "").lower()
                        return any(tok in n for tok in ["khkadressen", "adressen", "adresse", "kunde", "kunden", "customer"]) and not is_junk(c)
                    masters = [c for c in filtered if is_customer_master(c)]
                    if masters:
                        filtered = masters
                        logger.info(f"🎯 Restricting to {len(masters)} customer master table(s)")
                
                # For product COUNT: drop junk + project lists
                elif ("count" in metrics) and any(e in ["product", "products", "produkt", "produkte", "artikel"] for e in entities + keywords):
                    logger.info("🎯 Filtering for product COUNT intent")
                    junk_dropped = [c for c in filtered if is_junk(c)]
                    filtered = [c for c in filtered if not is_junk(c)] or junk_dropped[:1]
                    if junk_dropped:
                        logger.info(f"🧹 Dropped {len(junk_dropped)} junk tables for product count")
                    # Also drop project lists
                    def is_project_list(c):
                        n = (c.get("table_name") or c.get("name") or c.get("full_name") or "").lower()
                        return any(tok in n for tok in ["projektliste", "projekt_liste", "projectlist", "projekt"]) 
                    proj_dropped = [c for c in filtered if is_project_list(c)]
                    filtered = [c for c in filtered if not is_project_list(c)] or filtered
                    if proj_dropped:
                        logger.info(f"🧹 Dropped {len(proj_dropped)} project-list candidates")
                    # Prefer article master tables
                    def is_product_master(c):
                        n = (c.get("table_name") or c.get("name") or c.get("full_name") or "").lower()
                        return any(tok in n for tok in ["artikelstamm", "artikel", "product", "products"]) and not is_junk(c) and not is_project_list(c)
                    masters = [c for c in filtered if is_product_master(c)]
                    if masters:
                        filtered = masters
                        logger.info(f"🎯 Restricting to {len(masters)} product master table(s)")
                
                # For revenue/sum intents: drop junk, prefer sales transaction tables
                elif any(m in ["sum", "total"] for m in metrics) or any(k in ["revenue", "sales", "umsatz"] for k in keywords):
                    logger.info("🎯 Filtering for revenue/SUM intent")
                    junk_dropped = [c for c in filtered if is_junk(c)]
                    filtered = [c for c in filtered if not is_junk(c)] or junk_dropped[:1]
                    if junk_dropped:
                        logger.info(f"🧹 Dropped {len(junk_dropped)} junk tables for revenue intent")
                    # Prefer sales transaction tables
                    def looks_sales(c):
                        n = (c.get("table_name") or c.get("name") or c.get("full_name") or "").lower()
                        return (
                            any(tok in n for tok in [
                                "vkposition", "rechnungsposition", "position", "positionen",
                                "rechnung", "rechnungen", "vkbeleg", "belege",
                                "auftrag", "auftrags", "invoice", "invoices", "order", "orders", "umsatz", "faktura", "verkauf"
                            ])
                            and not is_junk(c)
                            and not any(tok in n for tok in ["projekt", "crm", "ek"])
                        )
                    sales_only = [c for c in filtered if looks_sales(c)]
                    if sales_only:
                        logger.info(f"🎯 Restricting to {len(sales_only)} sales transaction table(s)")
                        filtered = sales_only
            except Exception as e:
                logger.warning(f"⚠️  Intent filtering failed: {e}")
                pass

            filtered.sort(key=rank_key, reverse=True)

            # Limit count (increase for revenue intents to widen search space)
            sel_limit = self.max_candidates_to_describe
            try:
                intent = state.get("intent", {}) or {}
                metrics = [m.lower() for m in (intent.get("metrics") or [])]
                required_action = (intent.get("required_action") or "").lower()
                if ("sum" in metrics) or (required_action == "topk_sum_by_customer"):
                    sel_limit = max(sel_limit, 6)
            except Exception:
                pass
            selected = filtered[:sel_limit]
            if not selected:
                selected = sorted(candidates, key=rank_key, reverse=True)[:sel_limit]
            
            # 🆕 Check if all candidates have been exhausted (tried + skipped)
            if not selected:
                logger.warning("🔍 All candidates exhausted, none left to try.")
                merge_error_info(
                    state,
                    {
                        "type": "NO_CANDIDATES_LEFT",
                        "message": (
                            "All discovered candidates have been tried and no more "
                            "valid tables remain for this query."
                        ),
                    },
                )
                state["no_candidates_left"] = True
                return state

            # Intent-specific post-prune ordering tweaks
            try:
                intent = state.get("intent", {}) or {}
                metrics = [m.lower() for m in (intent.get("metrics") or [])]
                entities = [e.lower() for e in (intent.get("primary_entities") or [])]
                required_action = (intent.get("required_action") or "").lower()
                # For customer count, bubble up KHKAdressen/Adressen masters
                if ("count" in metrics) and any(e in ["customer", "customers", "kunde", "kunden"] for e in entities):
                    def cust_key(c):
                        n = (c.get("table_name") or c.get("name") or c.get("full_name") or "").lower()
                        return (
                            1 if any(tok in n for tok in ["khkadressen", "adressen", "adresse"]) else 0,
                            0 if any(tok in n for tok in ["projekt", "projektliste"]) else 1
                        )
                    selected = sorted(selected, key=cust_key, reverse=True)
                # For product count, bubble up Artikel/Artikelstamm and downrank Projektliste
                if ("count" in metrics) and any(e in ["product", "products", "produkt", "produkte", "artikel"] for e in entities):
                    def prod_key(c):
                        n = (c.get("table_name") or c.get("name") or c.get("full_name") or "").lower()
                        return (
                            1 if any(tok in n for tok in ["artikelstamm", "artikel", "product", "products"]) else 0,
                            0 if any(tok in n for tok in ["projekt", "projektliste"]) else 1
                        )
                    selected = sorted(selected, key=prod_key, reverse=True)
                # For Top-K SUM by customer, prefer sales position/invoice sources and de-emphasize cockpit/aggregate/config views
                if required_action == "topk_sum_by_customer" or (("sum" in metrics) and any(e in ["customer", "customers", "kunde", "kunden"] for e in entities)):
                    def rev_key(c):
                        n = (c.get("table_name") or c.get("name") or c.get("full_name") or "").lower()
                        sales_like = 1 if any(tok in n for tok in ["position", "positionen", "rechnung", "rechnungs", "beleg", "belege", "vk", "verkauf", "invoice", "order", "faktura"]) else 0
                        bad_view = 0 if any(tok in n for tok in ["cockpit", "auftragscockpit", "belegegesamt"]) else 1
                        cfg_pen = 0 if any(tok in n for tok in ["belegart", "berecht", "permission", "rechte", "user", "role", "auth"]) else 1
                        return (sales_like, bad_view, cfg_pen)
                    selected = sorted(selected, key=rev_key, reverse=True)
            except Exception:
                pass
            
            logger.info(f"✅ Selected {len(selected)} candidate(s) for description")
            logger.info("🎯 FINAL SELECTION AFTER FILTERING:")
            for i, c in enumerate(selected):
                name = c.get('table_name', c.get('name', ''))
                score = c.get('score', 0)
                rows = c.get('estimated_rows', 0)
                logger.info(f"  {i+1}. {name} | score={score:.3f} | rows={rows} | FINAL")
            log_payload = self._get_discovery_log(state)
            log_payload.setdefault("events", []).append({
                "stage": "selection",
                "tables": [
                    {
                        "table": c.get("table_name") or c.get("name"),
                        "score": round(float(c.get("score", 0)), 3),
                    }
                    for c in selected
                ],
            })
            
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
            # Phase 4: Parallel processing for independent describe operations
            describe_tasks = []
            uncached_candidates = []

            # First pass: collect cached and prepare uncached for parallel processing
            for cand in candidates:
                table_name = cand.get("table_name") or cand.get("name") or cand.get("full_name", "")

                # Check cache first
                if table_name in session_cache:
                    logger.debug(f"  {table_name} (cached)")
                    described.append(session_cache[table_name])
                    continue

                # Prepare for parallel describe
                uncached_candidates.append((table_name, cand))

            # Phase 4: Parallel describe operations (up to 3 concurrent to avoid overwhelming MCP)
            if uncached_candidates:
                logger.debug(f"  Describing {len(uncached_candidates)} tables in parallel...")

                # Create describe tasks (limit concurrency)
                semaphore = asyncio.Semaphore(3)  # Max 3 concurrent describes

                async def describe_with_semaphore(table_name, cand):
                    async with semaphore:
                        try:
                            logger.debug(f"  Describing {table_name}...")
                            # Use view-aware describe when candidate is a view
                            if cand.get("is_view", False):
                                result = await self.mcp.describe_view(table_name, include_sample=False)
                            else:
                                result = await self.mcp.describe_table(table_name, include_sample=False)
                            parsed = self._parse_describe_result(result, table_name)
                            if isinstance(parsed, dict):
                                if "full_name" not in parsed:
                                    parsed["full_name"] = table_name
                                if "schema" not in parsed and "." in table_name:
                                    parsed["schema"] = table_name.split(".", 1)[0]
                                if not parsed.get("estimated_rows") and cand.get("estimated_rows"):
                                    parsed["estimated_rows"] = cand.get("estimated_rows")
                                if "has_rows" not in parsed and (cand.get("estimated_rows") or 0) > 0:
                                    parsed["has_rows"] = True
                            # Optionally fetch view dependencies
                            if cand.get("is_view", False):
                                try:
                                    deps_res = await self.mcp.get_view_dependencies(table_name)
                                    # Try to parse simple JSON envelope
                                    deps_text = deps_res[0].get("text", "") if deps_res and isinstance(deps_res[0], dict) else ""
                                    deps_json = _extract_json_from_text(deps_text) if deps_text else {}
                                    if isinstance(deps_json, dict):
                                        parsed["dependencies"] = deps_json.get("data", {}).get("dependencies", [])
                                except Exception as dep_err:
                                    logger.debug(f"  Dependencies fetch failed for {table_name}: {dep_err}")
                            session_cache[table_name] = parsed
                            return parsed
                        except Exception as e:
                            logger.warning(f"  Failed to describe {table_name}: {e}")
                            return cand  # Return original candidate on failure

                # Execute parallel describes
                tasks = [describe_with_semaphore(table_name, cand) for table_name, cand in uncached_candidates]
                parallel_results = await asyncio.gather(*tasks, return_exceptions=True)

                # Collect results
                for result in parallel_results:
                    if isinstance(result, Exception):
                        logger.error(f"Parallel describe task failed: {result}")
                        continue
                    described.append(result)

            logger.info(f"✅ Described {len(described)} table(s) ({len(uncached_candidates)} parallel)")
            
            # Filter out invalid/empty describes (e.g., missing view, zero columns)
            valid_described = []
            for d in described:
                try:
                    columns = d.get("columns") if isinstance(d, dict) else None
                    if isinstance(columns, list) and len(columns) > 0:
                        valid_described.append(d)
                    else:
                        name = (d.get("table_name") or d.get("name") or d.get("full_name") or "") if isinstance(d, dict) else str(d)
                        logger.debug(f"  Skipping invalid/empty describe for {name}")
                except Exception:
                    continue

            # If all describes invalid, attempt an intent-aware fallback to find better candidates
            if not valid_described:
                try:
                    logger.info("🔁 No valid describes; invoking intent-aware fallback discovery for alternates")
                    alt = await self._fallback_business_table_discovery()
                    if alt:
                        # Describe top 3 alternates quickly
                        alt = alt[:3]
                        alt_described = []
                        for a in alt:
                            tname = a.get("table_name") or a.get("name") or a.get("full_name", "")
                            if not tname:
                                continue
                            try:
                                if a.get("is_view", False):
                                    r = await self.mcp.describe_view(tname, include_sample=False)
                                else:
                                    r = await self.mcp.describe_table(tname, include_sample=False)
                                parsed = self._parse_describe_result(r, tname)
                                if isinstance(parsed.get("columns"), list) and parsed.get("columns"):
                                    alt_described.append(parsed)
                            except Exception:
                                continue
                        if alt_described:
                            valid_described = alt_described
                except Exception:
                    pass

            # Finalize candidates for downstream nodes
            state["candidate_views"] = valid_described if valid_described else described
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
            relevant_tables: List[str] = []
            relevant_table_details = []
            
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

                # Store both string name list and detailed metadata
                relevant_tables.append(table_name)
                relevant_table_details.append(cand)
                
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
            
            # Targeted enrichment: ensure a customer dimension table is present for SUM-over-customers intents
            try:
                intent = state.get("intent", {}) or {}
                metrics = [m.lower() for m in (intent.get("metrics") or [])]
                entities = [e.lower() for e in (intent.get("primary_entities") or [])]
                needs_customer_dim = (any(m in ["sum", "total"] for m in metrics) and any(e in ["customer", "customers", "kunde", "kunden"] for e in entities))
                has_customer_dim = any(any(tok in (t or "").lower() for tok in ["khkadressen", "adressen", "adresse", "kunde", "kunden", "customer"]) for t in relevant_tables)
                if needs_customer_dim and not has_customer_dim:
                    logger.info("🎯 Enriching with customer dimension candidate (KHKAdressen)...")
                    try:
                        search_terms = ["khkadressen", "adressen", "kunde", "customer"]
                        best_name = None
                        best_score = -1
                        for term in search_terms:
                            res = await self.mcp.search_tables(term, page=1, page_size=10)
                            parsed = self._parse_search_result(res)
                            for r in parsed:
                                name = r.get("full_name") or r.get("name") or r.get("table_name")
                                if not name:
                                    continue
                                n = name.lower()
                                score = 0
                                if "khkadressen" in n: score += 3
                                if any(tok in n for tok in ["adresse", "adressen", "address"]): score += 2
                                if any(tok in n for tok in ["kunde", "kunden", "customer"]): score += 1
                                est = int(r.get("estimated_rows") or 0)
                                if est > 0: score += 1
                                if score > best_score:
                                    best_score = score
                                    best_name = name
                        if best_name and best_name not in relevant_tables:
                            relevant_tables.append(best_name)
                            relevant_table_details.append({"table_name": best_name, "columns": [], "is_view": False})
                            logger.info(f"✅ Added customer dimension candidate: {best_name}")
                    except Exception as _:
                        pass
                # For pure customer count intents, also ensure a customer master table is present
                needs_customer_count = (any(m in ["count"] for m in metrics) and any(e in ["customer", "customers", "kunde", "kunden"] for e in entities))
                has_customer_master = any(any(tok in (t or "").lower() for tok in ["khkadressen", "adressen", "adresse"]) for t in relevant_tables)
                if needs_customer_count and not has_customer_master:
                    try:
                        logger.info("🎯 Enriching with customer master for COUNT intent (KHKAdressen/Adressen)...")
                        res = await self.mcp.search_tables("KHKAdressen", page=1, page_size=5)
                        parsed = self._parse_search_result(res)
                        best = None
                        for r in parsed:
                            nm = (r.get("full_name") or r.get("name") or r.get("table_name") or "").lower()
                            if any(tok in nm for tok in ["khkadressen", "adressen", "adresse"]):
                                best = r.get("full_name") or r.get("name") or r.get("table_name")
                                break
                        if best and best not in relevant_tables:
                            relevant_tables.insert(0, best)
                            relevant_table_details.insert(0, {"table_name": best, "columns": [], "is_view": False})
                            logger.info(f"✅ Prefixed customer master table for COUNT: {best}")
                    except Exception:
                        pass
            except Exception:
                pass
            
            log_payload = self._get_discovery_log(state)
            log_payload.setdefault("events", []).append({
                "stage": "schema_snippet",
                "tables": relevant_tables,
            })
            state["relevant_tables"] = relevant_tables
            state["relevant_table_details"] = relevant_table_details
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
            return self._finalize_discovery_payload(state)
        
        try:
            logger.info(f"  Fetching columns for: {relevant_tables}")
            
            # 🔑 CRITICAL: Call MCP tool to get indexed columns from Scout Catalog
            column_index = await get_column_index_mcp(relevant_tables)
            
            if not column_index:
                logger.warning("⚠️  Column index fetch returned empty, continuing without it")
                state["column_index"] = {}
                return self._finalize_discovery_payload(state)

            # Canonicalise column index keys so downstream consumers see the
            # same logical identifiers as discovery/relation hints.
            dialect = state.get("db_dialect") or get_db_dialect()
            default_schema = state.get("db_default_schema") or get_db_default_schema(dialect)
            canonical_index: Dict[str, List[str]] = {}
            for table, columns in column_index.items():
                canonical = canonical_table_name(table, dialect=dialect, schema=default_schema)
                canonical_index[canonical] = list(columns or [])

            logger.info("✅ Successfully fetched column index:")
            for table, columns in canonical_index.items():
                col_count = len(columns) if isinstance(columns, list) else 0
                logger.info(f"  {table}: {col_count} column(s)")
                if col_count <= 5:
                    logger.debug(f"    Columns: {columns}")

            state["column_index"] = canonical_index
            logger.info(f"🗂️ Column index fetched; existing detail entries: {len(state.get('relevant_table_details') or [])}")
            await self._enrich_row_estimates(state)
            return self._finalize_discovery_payload(state)
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch column index: {str(e)}")
            logger.warning("⚠️  Continuing without column index (Planning Agent will fall back)")
            # Don't fail the flow - let Planning Agent handle the fetch if needed
            state["column_index"] = {}
            return self._finalize_discovery_payload(state)
    
    # Helper methods
    
    def _get_discovery_log(self, state: BaseState) -> Dict[str, Any]:
        log = state.get("discovery_log")
        if not isinstance(log, dict):
            log = {}
        log.setdefault("events", [])
        state["discovery_log"] = log
        return log

    def _catalog_tables(self, state: BaseState) -> Dict[str, Any]:
        catalog = state.get("catalog")
        if isinstance(catalog, dict):
            tables = catalog.get("tables")
            if isinstance(tables, dict):
                return tables
        return {}

    def _match_catalog_entry(self, catalog_tables: Dict[str, Any], table_name: str) -> Optional[Dict[str, Any]]:
        if table_name in catalog_tables:
            return catalog_tables[table_name]
        lowered = table_name.lower()
        for key, value in catalog_tables.items():
            if str(key).lower() == lowered:
                return value
        return None

    def _build_seed_candidates(self, tables: List[str], state: BaseState) -> List[Dict[str, Any]]:
        catalog_tables = self._catalog_tables(state)
        candidates: List[Dict[str, Any]] = []
        for raw in tables:
            if not raw:
                continue
            qualified = self._qualify_table_name(raw)
            meta = self._match_catalog_entry(catalog_tables, qualified)
            candidate = {
                "table_name": qualified,
                "full_name": qualified,
                "relevance_score": 0.45,
                "has_rows": True,
                "estimated_rows": (meta or {}).get("row_count") or (meta or {}).get("estimated_rows"),
                "column_count": (meta or {}).get("column_count"),
                "fk_count": (meta or {}).get("fk_count"),
                "is_view": bool((meta or {}).get("type") == "view"),
                "columns": (meta or {}).get("columns") or [],
                "concept_seed": True,
            }
            candidates.append(candidate)
        return candidates

    def _central_catalog_candidates(self, state: BaseState, seen: Set[str], limit: int = 5) -> List[Dict[str, Any]]:
        catalog_tables = self._catalog_tables(state)
        scored: List[Tuple[float, str, Dict[str, Any]]] = []
        for name, meta in catalog_tables.items():
            if not name or name in seen:
                continue
            fk_score = self._to_number(meta.get("fk_count"))
            row_score = self._to_number(meta.get("row_count") or meta.get("estimated_rows"))
            column_score = self._to_number(meta.get("column_count"))
            score = (fk_score * 0.4) + (row_score * 0.0001) + (column_score * 0.05)
            scored.append((score, name, meta))
        scored.sort(key=lambda item: item[0], reverse=True)
        candidates: List[Dict[str, Any]] = []
        for score, name, meta in scored[:limit]:
            candidates.append({
                "table_name": name,
                "full_name": name,
                "relevance_score": max(min(score, 1.0), 0.3),
                "has_rows": True,
                "estimated_rows": meta.get("row_count") or meta.get("estimated_rows"),
                "column_count": meta.get("column_count"),
                "fk_count": meta.get("fk_count"),
                "is_view": bool(meta.get("type") == "view"),
                "columns": meta.get("columns") or [],
                "fallback_reason": "catalog_centrality",
            })
        return candidates

    def _fallback_candidates_from_concepts(self, state: BaseState, seen: Set[str]) -> Tuple[List[Dict[str, Any]], str]:
        seed_candidates: List[Dict[str, Any]] = []
        for cand in self._build_seed_candidates(state.get("seed_tables", []) or [], state):
            name = cand.get("full_name") or cand.get("table_name")
            if name and name not in seen:
                seed_candidates.append(cand)
        if seed_candidates:
            return seed_candidates, "concept_seed"
        catalog_candidates = self._central_catalog_candidates(state, seen)
        if catalog_candidates:
            return catalog_candidates, "catalog_centrality"
        return [], ""

    def _to_number(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    
    def _split_tokens(self, value: Optional[str]) -> List[str]:
        if not value:
            return []
        text = re.sub(r"([a-z0-9])([A-ZÄÖÜ])", r"\1 \2", str(value))
        text = re.sub(r"[^0-9A-Za-zÄÖÜäöüß]+", " ", text)
        tokens = [tok.lower() for tok in text.split() if tok]
        return tokens

    def _canonical_entity(self, entity: str) -> str:
        stripped = entity.strip().lower()
        if stripped in self.entity_canonical_map:
            return self.entity_canonical_map[stripped]
        # Remove plural 's' or German plural 'en' heuristically
        if stripped.endswith("en") and stripped[:-2] in self.entity_canonical_map:
            return self.entity_canonical_map[stripped[:-2]]
        if stripped.endswith("s") and stripped[:-1] in self.entity_canonical_map:
            return self.entity_canonical_map[stripped[:-1]]
        return stripped

    def _collect_terms(self, intent: Dict[str, Any], keys: Optional[List[str]] = None) -> Set[str]:
        if not intent:
            return set()
        sequences: List[str] = []
        if keys is None or "primary_entities" in keys:
            sequences.extend(intent.get("primary_entities") or [])
        if keys is None or "secondary_entities" in keys:
            sequences.extend(intent.get("secondary_entities") or [])
        if keys is None or "metrics" in keys:
            sequences.extend(intent.get("metrics") or [])
        if keys is None or "keywords_for_discovery" in keys:
            sequences.extend(intent.get("keywords_for_discovery") or [])
        if keys is None or "raw_query" in keys:
            raw = intent.get("raw_query")
            if raw:
                sequences.append(raw)
        tokens: Set[str] = set()
        for seq in sequences:
            tokens.update(self._split_tokens(seq))
        return tokens

    def _string_similarity(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def _get_columns_for_table(
        self,
        table: str,
        detail: DiscoveryCandidate,
        column_index: Dict[str, List[str]],
    ) -> List[str]:
        if column_index and table in column_index and isinstance(column_index[table], list):
            return [str(col) for col in column_index[table] if col]
        if detail.columns:
            cols = []
            for col in detail.columns:
                name = col.get("column") or col.get("column_name") or col.get("name")
                if name:
                    cols.append(str(name))
            return cols
        return []

    def _token_overlap(self, tokens: Set[str], reference: Set[str]) -> float:
        if not tokens or not reference:
            return 0.0
        intersection = tokens & reference
        if not intersection:
            return 0.0
        return len(intersection) / len(reference)

    def _score_column_against_terms(self, column: str, term_tokens: Set[str], term_strings: List[str]) -> float:
        tokens = set(self._split_tokens(column))
        overlap_score = self._token_overlap(tokens, term_tokens)
        similarity_score = 0.0
        for term in term_strings:
            similarity_score = max(similarity_score, self._string_similarity(column, term))
        # weight overlap higher than loose similarity
        return max(overlap_score, similarity_score)

    def _build_role_hints(
        self,
        detail_models: List[DiscoveryCandidate],
        column_index: Dict[str, List[str]],
        intent: Dict[str, Any],
    ) -> DiscoveryRoleHints:
        role_hints = DiscoveryRoleHints()
        if not detail_models:
            return role_hints

        metric_terms = self._collect_terms(intent, keys=["metrics", "keywords_for_discovery", "raw_query"])
        metric_strings = [
            *(intent.get("metrics") or []),
            *(intent.get("keywords_for_discovery") or []),
        ]
        if intent.get("raw_query"):
            metric_strings.append(intent["raw_query"])

        entity_terms_map: Dict[str, Set[str]] = {}
        for entity in intent.get("primary_entities") or []:
            canonical = self._canonical_entity(entity)
            tokens = self._split_tokens(entity)
            if canonical not in entity_terms_map:
                entity_terms_map[canonical] = set()
            entity_terms_map[canonical].update(tokens)
        for entity in intent.get("secondary_entities") or []:
            canonical = self._canonical_entity(entity)
            tokens = self._split_tokens(entity)
            if canonical not in entity_terms_map:
                entity_terms_map[canonical] = set()
            entity_terms_map[canonical].update(tokens)

        fact_candidates: List[RoleHintFact] = []

        for detail in detail_models:
            table = detail.full_name
            columns = self._get_columns_for_table(table, detail, column_index)
            column_tokens_map = {col: set(self._split_tokens(col)) for col in columns}

            metric_candidates: Dict[str, float] = {}
            if metric_terms:
                for col in columns:
                    score = self._score_column_against_terms(col, metric_terms, metric_strings)
                    if score > 0:
                        metric_candidates[col] = score

            # Fallback: inject obvious numeric metrics when lexical match misses them
            numeric_keyword_tokens = (
                "umsatz",
                "betrag",
                "preis",
                "brutto",
                "netto",
                "wert",
                "amount",
                "total",
                "sum",
                "revenue",
                "sales",
                "menge",
                "quantity",
                "qty",
                "value",
            )
            non_numeric_tokens = (
                "gruppe",
                "kundengruppe",
                "status",
                "typ",
                "category",
                "klasse",
                "code",
                "position",
                "matchcode",
                "kontakt",
                "adress",
                "adresse",
                "strasse",
                "straße",
                "name",
                "nummer",
                "nr",
                "id",
                "kennzeichen",
                "customerid",
                "kundennr",
                "kundnr",
                "kundenid",
                "anrede",
                "empfaenger",
            )
            for col in columns:
                lower_col = (col or "").lower()
                if any(token in lower_col for token in non_numeric_tokens):
                    continue
                if any(token in lower_col for token in numeric_keyword_tokens):
                    metric_candidates[col] = max(metric_candidates.get(col, 0.0), 0.95)

            # Purge obviously non-numeric fields that slipped through lexical scoring
            for col in list(metric_candidates.keys()):
                lower_col = (col or "").lower()
                if any(token in lower_col for token in non_numeric_tokens):
                    metric_candidates.pop(col, None)

            date_columns = [
                col
                for col, tokens in column_tokens_map.items()
                if self._token_overlap(tokens, self.date_signal_tokens) > 0
            ]

            entity_keys: Dict[str, List[str]] = {}
            for role, tokens in entity_terms_map.items():
                if not tokens:
                    continue
                candidate_cols = [
                    col
                    for col, col_tokens in column_tokens_map.items()
                    if self._token_overlap(col_tokens, tokens | self.id_signal_tokens) > 0
                ]
                if candidate_cols:
                    entity_keys[role] = candidate_cols[:3]

            fact_candidates.append(
                RoleHintFact(
                    table=table,
                    estimated_rows=detail.estimated_rows,
                    metric_candidates=dict(sorted(metric_candidates.items(), key=lambda item: item[1], reverse=True)[:5]),
                    date_columns=date_columns[:5],
                    entity_keys=entity_keys,
                )
            )

            # Dimension detection
            table_tokens = set(self._split_tokens(detail.name or detail.full_name))
            for role, tokens in entity_terms_map.items():
                if not tokens:
                    continue
                overlap = self._token_overlap(table_tokens, tokens)
                if overlap <= 0:
                    continue

                id_cols = [
                    col
                    for col, col_tokens in column_tokens_map.items()
                    if self._token_overlap(col_tokens, self.id_signal_tokens | tokens) > 0
                ]
                label_cols = [
                    col
                    for col, col_tokens in column_tokens_map.items()
                    if self._token_overlap(col_tokens, self.label_signal_tokens) > 0
                ]

                candidate_dimension = RoleHintDimension(
                    role=role,
                    table=table,
                    estimated_rows=detail.estimated_rows,
                    id_columns=id_cols[:3],
                    label_columns=label_cols[:3],
                )

                existing = role_hints.dimensions.get(role)
                if existing is None or (detail.estimated_rows or 0) > (existing.estimated_rows or 0):
                    role_hints.dimensions[role] = candidate_dimension

            # Fallback: if entity keys identified but no dimension created, synthesize from this table
            for role, keys in entity_keys.items():
                if role in role_hints.dimensions or not keys:
                    continue
                label_cols = [
                    col
                    for col, col_tokens in column_tokens_map.items()
                    if self._token_overlap(col_tokens, self.label_signal_tokens) > 0
                ]
                candidate_dimension = RoleHintDimension(
                    role=role,
                    table=table,
                    estimated_rows=detail.estimated_rows,
                    id_columns=keys[:3],
                    label_columns=label_cols[:3],
                )
                role_hints.dimensions[role] = candidate_dimension

        fact_candidates.sort(
            key=lambda fc: (
                max(fc.metric_candidates.values()) if fc.metric_candidates else 0.0,
                fc.estimated_rows or 0,
            ),
            reverse=True,
        )
        role_hints.fact_candidates = fact_candidates
        return role_hints

    async def _enrich_row_estimates(self, state: BaseState) -> None:
        """Probe candidate tables to ensure we have a non-zero row estimate."""
        details = state.get("relevant_table_details") or []
        logger.info(f"🧮 Enrich row estimates for {len(details)} candidate(s)")
        if not details:
            return

        enriched: List[DiscoveryCandidate] = []
        for raw in details:
            try:
                model = DiscoveryCandidate.model_validate(raw)
            except Exception:
                continue
            current_rows = model.estimated_rows or 0
            if current_rows <= 0:
                try:
                    row_count = await self._probe_table_rows(model.full_name)
                except Exception as exc:
                    logger.debug(f"🔍 Row probe failed for {model.full_name}: {exc}")
                    row_count = 0
                if row_count > 0:
                    logger.info(f"✅ Row probe confirmed data for {model.full_name} (>= {row_count} rows)")
                    model.estimated_rows = row_count
                    model.has_rows = True
                elif model.has_rows:
                    # Describe metadata claims the table has rows even though probe failed.
                    # Treat it as non-empty but mark minimal estimate to keep it in play.
                    model.estimated_rows = 1
                    logger.info(f"ℹ️  Trusting describe(has_rows) for {model.full_name}; setting estimated_rows=1")
            logger.info(f"📊 Row estimate for {model.full_name}: {model.estimated_rows}")
            enriched.append(model)

        enriched_models = [m for m in enriched]

        if not enriched_models or not any((model.estimated_rows or 0) > 0 for model in enriched_models):
            fallback = await self._fallback_fact_from_keywords(state.get("intent") or {})
            if fallback:
                logger.info(f"✅ Fallback fact candidate selected: {fallback.full_name}")
                enriched_models = [fallback]
                state["relevant_tables"] = [fallback.full_name]

        state["relevant_table_details"] = [m.model_dump() for m in enriched_models]

    async def _probe_table_rows(self, table: str) -> int:
        """Return 1 if the table appears to contain rows, otherwise 0."""
        qualified = self._qualify_table_name(table)
        sql = f"SELECT TOP 1 1 AS probe FROM {qualified}"
        try:
            result = await self.mcp.query_bounded(sql, max_rows=1)
        except Exception as exc:
            logger.debug(f"Row probe error for {table}: {exc}")
            return 0

        if not isinstance(result, dict) or not result.get("ok"):
            return 0

        row_count = result.get("row_count")
        if isinstance(row_count, (int, float)) and row_count > 0:
            return int(row_count)

        rows = result.get("data")
        if isinstance(rows, list) and rows:
            return len(rows)

        return 0

    def _qualify_table_name(self, table: str) -> str:
        """
        Map any incoming table identifier to the canonical logical name.

        This is used both for seed tables and for lightweight probes
        (e.g., row-count checks).  Actual SQL generation is responsible
        for applying dialect-specific quoting.
        """
        raw = (table or "").strip()
        if not raw:
            return ""
        dialect = get_db_dialect()
        default_schema = get_db_default_schema(dialect)
        return canonical_table_name(raw, dialect=dialect, schema=default_schema)

    async def _fallback_fact_from_keywords(self, intent: Dict[str, Any]) -> Optional[DiscoveryCandidate]:
        keywords = intent.get("keywords_for_discovery") or []
        if not keywords:
            return None

        query = " ".join(keywords[:4])
        try:
            result = await self.mcp.search_tables(query, page=1, page_size=8, intent_data=intent)
        except Exception as exc:
            logger.debug(f"Fallback fact search failed: {exc}")
            return None

        parsed = self._parse_search_result(result)
        for raw in parsed:
            try:
                candidate = DiscoveryCandidate.model_validate(raw)
            except Exception:
                continue

            rows = candidate.estimated_rows or 0
            if rows <= 0:
                rows = await self._probe_table_rows(candidate.full_name)
            if rows <= 0:
                continue

            candidate.estimated_rows = rows
            candidate.has_rows = True
            return candidate

        return None

    def _extract_keywords(self, user_input: str, intent: Dict[str, Any]) -> List[str]:
        """
        Extract primary search keywords strictly from the IntentParser output.

        We intentionally avoid inventing new tokens here—primary discovery must stay
        anchored to what the intent parser produced so we don't drift into unrelated
        domains (payroll tables, admin metadata, etc.).
        """
        discovery_query = intent.get("discovery_query")
        if discovery_query:
            logger.info(f"📌 Using discovery query string: {discovery_query}")
            return [discovery_query]
        base = [k for k in (intent.get("keywords_for_discovery") or []) if k]
        if not base and user_input:
            base = [user_input]
        logger.info(f"📌 Using intent keywords (exact): {base}")
        return base

    def _enrichment_queries(self, intent: Dict[str, Any]) -> List[str]:
        """
        Build a small set of intent-driven enrichment queries. These are executed
        separately so they cannot drown out the primary signal.
        """
        entities = [e.lower() for e in (intent.get("primary_entities") or [])]
        metrics = [m.lower() for m in (intent.get("metrics") or [])]
        base = [k.lower() for k in (intent.get("keywords_for_discovery") or []) if k]

        extra: List[str] = []
        if any(e in ["customer", "customers", "kunde", "kunden"] for e in entities + base):
            extra.extend(["KHKAdressen", "Kunde", "Kunden"])
        if any(e in ["product", "products", "produkt", "produkte", "artikel", "artikelstamm"] for e in entities + base):
            extra.extend(["Artikelstamm", "Produkte", "Artikel"])
        if any(m in ["sum", "total"] for m in metrics) or any(k in ["umsatz", "revenue", "sales"] for k in base):
            extra.extend(["Umsatz", "VKPosition", "Rechnungsposition"])

        # Deduplicate while preserving order and drop anything already present in the
        # primary keywords to avoid redundant calls.
        seen = set()
        filtered: List[str] = []
        for term in extra:
            key = term.lower()
            if key in seen or key in base:
                continue
            seen.add(key)
            filtered.append(term)
        return filtered
    
    def _parse_search_result(self, result: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse MCP search_tables result with robust JSON extraction."""
        if not result or len(result) == 0:
            return []

        try:
            content = result[0].get("text", "")
            data = _extract_json_from_text(content) if isinstance(content, str) else content

            if isinstance(data, dict):
                container = data
                if "data" in data and isinstance(data["data"], dict):
                    container = data["data"]
                tables = container.get("results") or container.get("tables") or []
            elif isinstance(data, list):
                tables = data
            else:
                return []

            normalized: List[Dict[str, Any]] = []
            for raw_candidate in tables:
                if not isinstance(raw_candidate, dict):
                    continue

                candidate_input = {
                    "full_name": raw_candidate.get("full_name") or raw_candidate.get("table_name") or raw_candidate.get("name"),
                    "schema": raw_candidate.get("schema") or raw_candidate.get("table_schema"),
                    "name": raw_candidate.get("table_name") or raw_candidate.get("name"),
                    "type": raw_candidate.get("type"),
                    "is_view": raw_candidate.get("is_view"),
                    "relevance_score": raw_candidate.get("relevance_score", raw_candidate.get("score", raw_candidate.get("relevance", 0.0))),
                    "role_coverage": raw_candidate.get("role_coverage", 0.0),
                    "has_rows": raw_candidate.get("has_rows"),
                    "estimated_rows": raw_candidate.get("estimated_rows"),
                    "column_count": raw_candidate.get("column_count"),
                    "fk_count": raw_candidate.get("fk_count"),
                    "columns": raw_candidate.get("columns", []),
                    "description": raw_candidate.get("description"),
                }

                try:
                    candidate = DiscoveryCandidate.model_validate(candidate_input)
                    normalized.append(candidate.model_dump())
                except Exception as exc:
                    logger.debug(f"Skipping discovery candidate due to validation error: {exc}")
                    continue

            return normalized

        except Exception as e:
            logger.warning(f"Failed to parse search result: {e}")
            return []
    
    def _parse_describe_result(self, result: List[Dict[str, Any]], table_name: str) -> Dict[str, Any]:
        """Parse MCP describe_table result with robust JSON extraction."""
        if not result or len(result) == 0:
            return {"table_name": table_name, "columns": []}

        try:
            content = result[0].get("text", "")
            data = _extract_json_from_text(content) if isinstance(content, str) else content

            # Support nesting under data
            details = data
            if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
                details = data["data"]

            return {
                "table_name": table_name,
                "columns": details.get("columns", []),
                "row_count": details.get("row_count", 0),
                "has_rows": details.get("has_rows", True),
                "is_view": details.get("is_view", False),
                "role_coverage": float(details.get("role_coverage", 0)),
                "relationships": details.get("relationships", [])
            }
        except Exception as e:
            logger.warning(f"Failed to parse describe result for {table_name}: {e}")
            return {"table_name": table_name, "columns": []}
    
    def _score_candidate(self, candidate: Dict[str, Any], intent: Dict[str, Any]) -> float:
        """
        Score a candidate using hybrid ranking formula.
        
        score = 0.45*text_sim + 0.25*role_coverage + 0.15*subject_match + 0.10*has_rows + 0.05*is_view
        """
        # Use MCP-provided relevance_score in [0.0, 1.0]; fallback to score if present
        text_sim = float(candidate.get("relevance_score", candidate.get("score", 0.0)))
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
        
        # Entity-aware adjustments: prefer appropriate sources for the intent
        try:
            name = (candidate.get("table_name") or candidate.get("full_name") or "").lower()
            metrics = [m.lower() for m in (intent.get("metrics") or [])]
            keywords = [k.lower() for k in (intent.get("keywords_for_discovery") or [])]
            entities = [e.lower() for e in (intent.get("primary_entities") or [])]

            is_table = not candidate.get("is_view", False)
            est_rows = candidate.get("estimated_rows")
            col_count = candidate.get("column_count", 0)

            # Penalize obviously empty/unknown structures
            if est_rows == 0:
                score -= 0.08
            if col_count == 0:
                score -= 0.05

            # Customer-centric counts: prefer base address/customer tables
            if ("count" in metrics or "wie viele" in " ".join(keywords)) and any(e in ["customer", "customers", "kunde", "kunden"] for e in entities + keywords):
                if any(token in name for token in ["adresse", "adressen", "khkadressen", "kunde", "kunden"]):
                    if is_table:
                        score += 0.15  # TABLE bonus for canonical master data
                    else:
                        score += 0.05  # small bonus if a high-quality view matches
                # Slight penalty for cockpit/analytics views for pure counts
                if any(token in name for token in ["cockpit", "auftragscockpit", "dashboard", "report"]):
                    score -= 0.08
                # Strongly de-emphasize project-centric sources for customer counts
                if any(token in name for token in ["projekt", "projektliste", "pps", "ppsmaterial", "project"]):
                    score -= 0.12

            # Revenue/sales aggregates: prefer sales/invoice/position sources; penalize cockpit/aggregate views
            if any(m in metrics for m in ["sum", "total"]) or any(k in keywords for k in ["umsatz", "revenue", "sales"]):
                if any(token in name for token in ["vk", "verkauf", "rechnung", "rechnungs", "beleg", "belege", "auftrag", "position", "positionen", "umsatz", "invoice", "order", "faktura"]):
                    score += 0.30
                if any(token in name for token in ["cockpit", "auftragscockpit", "belegegesamt", "dashboard"]):
                    score -= 0.12
                # De-emphasize address/contact-only sources for revenue aggregation
                addr_like = any(token in name for token in ["adresse", "adressen", "kontakt", "contacts", "khkadressen", "address"])
                sales_like = any(token in name for token in ["vk", "verkauf", "rechnung", "rechnungs", "beleg", "belege", "auftrag", "position", "positionen", "umsatz"])
                if addr_like and not sales_like:
                    score -= 0.30

            # Product-centric counts: prefer product/article master tables, avoid project listings
            if ("count" in metrics) and any(e in ["product", "products", "produkt", "produkte", "artikel"] for e in entities + keywords):
                if any(token in name for token in ["artikelstamm", "artikel", "products", "product", "artikelnummer", "artikel_liste", "produkt"]):
                    score += (0.15 if is_table else 0.06)
                if any(token in name for token in ["projekt", "projektliste", "crm", "pm"]):
                    score -= 0.10
                # Small table preference for counts
                if is_table:
                    score += 0.04

            # Project-centric queries: boost project/projekte tables
            if any(e in ["project", "projects", "projekt", "projekte"] for e in entities + keywords):
                if any(token in name for token in ["projekt", "projekte", "projektstamm", "projektliste", "project"]):
                    score += (0.14 if is_table else 0.06)
                # de-emphasize archive/crm for core project questions
                if any(token in name for token in ["archiv", "archive", "crm"]):
                    score -= 0.06

            # Clamp and return
            return max(0.0, min(1.0, score))
        except Exception:
            return min(1.0, score)

    async def _strategic_query_discovery(self, user_input: str, intent: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Enhanced discovery for strategic/complex queries requiring multi-keyword search."""
        logger.info(f"🔍 [STRATEGIC_DISCOVERY] Starting strategic discovery for: {user_input}")

        required_action = intent.get("required_action", "")
        entities = intent.get("primary_entities", [])
        keywords = intent.get("keywords_for_discovery", [])

        # Define search strategies based on query type
        search_strategies = {
            "growth_analysis": {
                "primary_keywords": ["kunde", "kunden", "customer", "customers", "adress", "adressen"],
                "secondary_keywords": ["datum", "date", "created", "erfass"],
                "boost_patterns": ["adressen", "kunden", "customer"],
                "exclude_patterns": ["grid", "template", "kennzeichen", "druckbeleg"]
            },
            "department_productivity": {
                "primary_keywords": ["mitarbeiter", "employee", "personal", "staff", "abteilung", "department"],
                "secondary_keywords": ["produktivität", "productivity", "leistung", "performance", "effizienz"],
                "boost_patterns": ["mitarbeiter", "employee", "abteilung", "department"],
                "exclude_patterns": ["grid", "template", "config", "setup"]
            },
            "comparative_analysis": {
                "primary_keywords": ["umsatz", "revenue", "verkauf", "sales", "betrag", "amount"],
                "secondary_keywords": ["datum", "date", "quartal", "quarter", "monat", "month"],
                "boost_patterns": ["vkposition", "rechnung", "invoice", "umsatz", "revenue"],
                "exclude_patterns": ["grid", "template", "kennzeichen", "config"]
            }
        }

        strategy = search_strategies.get(required_action, {
            "primary_keywords": keywords + entities,
            "secondary_keywords": [],
            "boost_patterns": entities,
            "exclude_patterns": ["grid", "template", "kennzeichen", "druckbeleg", "config"]
        })

        # Perform multi-keyword search
        all_candidates = []

        # Search primary keywords
        for keyword in strategy["primary_keywords"][:3]:  # Limit to avoid overload
            try:
                logger.debug(f"🔍 [STRATEGIC] Searching primary keyword: '{keyword}'")
                result = await self.mcp.search_tables(keyword, page=1, page_size=15)
                parsed = self._parse_search_result(result)
                if parsed:
                    all_candidates.extend(parsed)
            except Exception as e:
                logger.debug(f"🔍 [STRATEGIC] Primary search for '{keyword}' failed: {e}")

        # Search secondary keywords if we have few results
        if len(all_candidates) < 5 and strategy["secondary_keywords"]:
            for keyword in strategy["secondary_keywords"][:2]:
                try:
                    logger.debug(f"🔍 [STRATEGIC] Searching secondary keyword: '{keyword}'")
                    result = await self.mcp.search_tables(keyword, page=1, page_size=10)
                    parsed = self._parse_search_result(result)
                    if parsed:
                        all_candidates.extend(parsed)
                except Exception as e:
                    logger.debug(f"🔍 [STRATEGIC] Secondary search for '{keyword}' failed: {e}")

        # Deduplicate and apply strategic scoring
        seen = set()
        unique_candidates = []
        for candidate in all_candidates:
            table_name = candidate.get("table_name", "")
            if table_name and table_name not in seen:
                seen.add(table_name)

                # Apply strategic scoring boosts
                score = candidate.get("relevance_score", 0.0)

                # Boost for strategy patterns
                table_lower = table_name.lower()
                for pattern in strategy["boost_patterns"]:
                    if pattern.lower() in table_lower:
                        score = min(1.0, score + 0.3)
                        break

                # Penalize excluded patterns
                for pattern in strategy["exclude_patterns"]:
                    if pattern.lower() in table_lower:
                        score = max(0.0, score - 0.5)
                        break

                candidate["relevance_score"] = score
                unique_candidates.append(candidate)

        # Sort by strategic score
        unique_candidates.sort(key=lambda x: (
            -x.get("relevance_score", 0),
            -x.get("estimated_rows", 0),
            x.get("table_name", "")
        ))

        # Take top candidates
        top_candidates = unique_candidates[:8]

        logger.info(f"🔍 [STRATEGIC_DISCOVERY] Found {len(top_candidates)} strategic candidates")
        for i, c in enumerate(top_candidates[:3]):
            logger.info(f"🔍 [STRATEGIC] {i+1}. {c.get('table_name')} (score: {c.get('relevance_score', 0):.2f})")

        return top_candidates

    def _finalize_discovery_payload(self, state: BaseState) -> BaseState:
        """Validate and normalize discovery payload before handing off to downstream agents."""
        try:
            clarification_triggered = False

            raw_details = state.get("relevant_table_details") or state.get("candidate_views") or []
            if not raw_details:
                fallback_tables = state.get("relevant_tables") or []
                if fallback_tables:
                    logger.info("🧾 No detailed metadata available, constructing fallback candidates from relevant_tables")
                    raw_details = [
                        {"full_name": tbl, "estimated_rows": 1, "has_rows": True}
                        for tbl in fallback_tables
                    ]
            logger.info(f"🧾 Finalizing discovery payload with {len(raw_details)} raw detail entries")
            detail_models: List[DiscoveryCandidate] = []
            for raw in raw_details:
                try:
                    detail_models.append(DiscoveryCandidate.model_validate(raw))
                except Exception as exc:
                    logger.debug(f"Skipping table detail due to validation error: {exc}")

            if detail_models:
                non_empty_details = [
                    model
                    for model in detail_models
                    if (model.estimated_rows or 0) > 0 or model.has_rows
                ]
                logger.info(
                    f"🧾 Non-empty detail entries: {len(non_empty_details)} / {len(detail_models)}"
                )
                if non_empty_details:
                    detail_models = non_empty_details
                else:
                    logger.warning("⚠️ Discovery only found empty tables; requesting clarification")
                    state["error_info"] = {
                        "type": "DISCOVERY_EMPTY_TABLES",
                        "message": "Discovery found only empty tables for this request.",
                        "suggestion": "Try specifying a different metric, table, or time window so I can target a table with data.",
                        "details": {
                            "candidates": [model.full_name for model in detail_models],
                        },
                    }
                    intent_state = state.setdefault("intent", {})
                    intent_state["needs_clarification"] = True
                    intent_state["clarification_question"] = (
                        "I only found tables without data for this topic. Could you clarify which business area or timeframe to inspect?"
                    )
                    intent_state["ambiguity_reason"] = "Discovery found only empty tables for the current intent."
                    clarification_triggered = True
                    detail_models = []
                    state["relevant_tables"] = []
            if not detail_models and not clarification_triggered:
                # As a fallback, use names already present in relevant_tables (without metadata)
                detail_models = []
                for name in state.get("relevant_tables", []) or []:
                    try:
                        detail_models.append(DiscoveryCandidate.model_validate({"full_name": name}))
                    except Exception:
                        continue

            # Canonicalise detail models and derive canonical table list.
            dialect = state.get("db_dialect") or get_db_dialect()
            default_schema = state.get("db_default_schema") or get_db_default_schema(dialect)

            canonical_detail_models: List[DiscoveryCandidate] = []
            for model in detail_models:
                try:
                    canonical_full = canonical_table_name(
                        model.full_name,
                        dialect=dialect,
                        schema=default_schema,
                    )
                    model.full_name = canonical_full
                    # Keep schema/name fields consistent with full_name
                    if "." in canonical_full:
                        schema_part, table_part = canonical_full.split(".", 1)
                        model.schema = schema_part
                        model.name = table_part
                except Exception:
                    # Best-effort; if anything goes wrong, keep the original model
                    pass
                canonical_detail_models.append(model)

            detail_models = canonical_detail_models

            candidate_view_models = [model for model in detail_models if model.is_view]
            relevant_tables = [model.full_name for model in detail_models]

            # Phase 4: KPI-driven table guardrails.
            # Ensure tables implied by KPI expressions (e.g. Products. in inventory_reorder)
            # are present in the final discovery result when available in seed_tables.
            required_tables = state.get("required_tables_from_kpi") or []
            if required_tables:
                seed_tables = state.get("seed_tables") or []

                existing_full = {str(t) for t in relevant_tables}
                existing_base = {str(t).split(".")[-1].lower(): str(t) for t in relevant_tables}
                seed_full = {str(t): str(t) for t in seed_tables}
                seed_base = {str(t).split(".")[-1].lower(): str(t) for t in seed_tables}

                injected_any = False
                missing_required: List[str] = []

                for req in required_tables:
                    req_str = str(req)
                    base = req_str.split(".")[-1].lower()

                    # Already present (by full name or base name) → nothing to do
                    if req_str in existing_full or base in existing_base:
                        continue

                    # Prefer canonical seed table when available
                    candidate_name = seed_full.get(req_str) or seed_base.get(base)
                    if candidate_name:
                        try:
                            detail_models.append(
                                DiscoveryCandidate.model_validate(
                                    {
                                        "full_name": candidate_name,
                                        # Minimal but non-empty metadata so downstream logic
                                        # treats this as a valid table candidate.
                                        "estimated_rows": 1,
                                        "has_rows": True,
                                    }
                                )
                            )
                            relevant_tables.append(candidate_name)
                            existing_full.add(candidate_name)
                            existing_base[base] = candidate_name
                            injected_any = True
                        except Exception as exc:
                            logger.debug(f"🧾 Failed to inject KPI-required table '{candidate_name}': {exc}")
                    else:
                        missing_required.append(req_str)

                if injected_any:
                    logger.info(
                        "🧾 [DISCOVERY] Injected KPI-required tables into discovery results: %s",
                        [t for t in relevant_tables if t in existing_full],
                    )
                    log_payload = self._get_discovery_log(state)
                    log_payload.setdefault("events", []).append(
                        {
                            "stage": "kpi_required_tables",
                            "required_tables_from_kpi": list(required_tables),
                            "missing_from_seed": missing_required,
                        }
                    )
                    state["discovery_log"] = log_payload

                if missing_required:
                    logger.warning(
                        "⚠️ [DISCOVERY] KPI-required tables not found in seeds or existing candidates: %s",
                        missing_required,
                    )

            role_hints = self._build_role_hints(
                detail_models,
                state.get("column_index") or {},
                state.get("intent") or {},
            )

            payload = DiscoveryOutput(
                relevant_tables=relevant_tables or [str(name) for name in (state.get("relevant_tables") or [])],
                schema_snippet=state.get("schema_snippet"),
                candidate_views=candidate_view_models,
                relevant_table_details=detail_models,
                column_index=state.get("column_index") or {},
                role_hints=role_hints,
            )
            updates = {
                "relevant_tables": payload.relevant_tables,
                "schema_snippet": payload.schema_snippet or state.get("schema_snippet", ""),
                "candidate_views": [view.model_dump() for view in payload.candidate_views],
                "relevant_table_details": [detail.model_dump() for detail in payload.relevant_table_details],
                "column_index": payload.column_index,
                "discovery_role_hints": payload.role_hints.model_dump(),
            }
            logger.info("🧾 Discovery updates keys: %s", list(updates.keys()))
            logger.info(
                "🧾 Discovery payload validated: %d detail(s), %d fact candidates, %d dimensions",
                len(payload.relevant_table_details),
                len(payload.role_hints.fact_candidates),
                len(payload.role_hints.dimensions),
            )
            logger.info("🧾 Discovery role hints payload: %s", updates["discovery_role_hints"])
            state.update(updates)
            log_payload = self._get_discovery_log(state)
            log_payload["final_tables"] = updates["relevant_tables"]
            log_payload["final_schema"] = updates["schema_snippet"]
            state["discovery_log"] = log_payload
            return dict(state)
        except Exception as exc:
            logger.warning(f"⚠️ Discovery output validation failed: {exc}")
        return dict(state)


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
