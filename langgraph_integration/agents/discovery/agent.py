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
from langgraph_integration.mcp_client import get_shared_mcp_tool, get_column_index_mcp, _extract_json_from_text
from langgraph_integration.prompts.discovery import TABLE_FOCUS_PROMPT, VIEWS_FIRST_GUIDANCE

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
            # Search for matching tables/views using a single joined query first
            candidates: List[Dict[str, Any]] = []
            query_str = " ".join(keywords)
            logger.debug(f"  Searching with joined keywords: '{query_str}'")
            try:
                result = await self.mcp.search_tables(query_str, page=1, page_size=10, intent_data=intent)
                parsed = self._parse_search_result(result)
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

            # Fallback per-keyword searches DISABLED to prevent search spam
            
            # Deduplicate by table name
            seen = set()
            unique_candidates = []
            for c in candidates:
                table_name = c.get("table_name") or c.get("name") or c.get("full_name", "")
                if table_name not in seen and table_name:
                    seen.add(table_name)
                    unique_candidates.append(c)
            
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
            except Exception:
                pass

            # Business-pattern fallback DISABLED; rely on primary joined search only
            logger.info(f"✅ Using primary joined search only: {len(unique_candidates)} candidate(s)")

            # Check if we have meaningful semantic matches (not just size-based ranking)
            semantic_candidates = [c for c in unique_candidates if c.get("relevance_score", 0) > 0.05]
            has_meaningful_matches = len(semantic_candidates) > 0

            if not unique_candidates or not has_meaningful_matches:
                logger.warning(f"⚠️  No semantically relevant tables/views found for keywords: {', '.join(keywords)}")
                logger.info(f"   Found {len(unique_candidates)} candidates, but none with semantic relevance > 0.05")
                # Trigger clarification by returning empty candidates
                state["candidate_views"] = []
                return state
            
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
            table_name = c.get("table_name") or c.get("name") or c.get("full_name", "")
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
                    filtered = candidates[:1]
            
            # Prefer non-empty entities and higher estimated_rows, then by score
            def rank_key(c):
                return (
                    1 if c.get("has_rows", False) else 0,
                    int(c.get("estimated_rows", 0) or 0),
                    float(c.get("score", 0.0))
                )

            # Intent-specific hard filters before final sort
            try:
                intent = state.get("intent", {}) or {}
                metrics = [m.lower() for m in (intent.get("metrics") or [])]
                entities = [e.lower() for e in (intent.get("primary_entities") or [])]
                if ("count" in metrics) and any(e in ["product", "products", "produkt", "produkte", "artikel"] for e in entities):
                    def is_project_list(c):
                        n = (c.get("table_name") or c.get("name") or c.get("full_name") or "").lower()
                        return any(tok in n for tok in ["projektliste", "projekt_liste", "projectlist"]) 
                    proj_dropped = [c for c in filtered if is_project_list(c)]
                    filtered = [c for c in filtered if not is_project_list(c)] or filtered
                    if proj_dropped:
                        logger.info(f"🧹 Dropped {len(proj_dropped)} project-list candidates for product count intent")
                # For revenue/sum intents: drop archive tables/views when possible
                if any(m in ["sum", "total"] for m in metrics) or any(k in ["revenue", "sales", "umsatz"] for k in (intent.get("keywords_for_discovery") or [])):
                    def is_archive(c):
                        n = (c.get("table_name") or c.get("name") or c.get("full_name") or "").lower()
                        return ("archiv" in n) or ("archive" in n)
                    arch_dropped = [c for c in filtered if is_archive(c)]
                    filtered = [c for c in filtered if not is_archive(c)] or filtered
                    if arch_dropped:
                        logger.info(f"🧹 Dropped {len(arch_dropped)} archive candidates for revenue intent")
                    # Prefer sales-like sources if any exist among remaining candidates
                    def looks_sales(c):
                        n = (c.get("table_name") or c.get("name") or c.get("full_name") or "").lower()
                        return any(tok in n for tok in [
                            "vk", "verkauf", "rechnung", "rechnungs", "beleg", "belege",
                            "position", "positionen", "umsatz", "invoice", "order", "faktura"
                        ]) and not any(ex in n for ex in ["archiv", "archive", "projekt", "crm", "ek"])
                    sales_only = [c for c in filtered if looks_sales(c)]
                    if sales_only:
                        logger.info(f"🎯 Sales-like candidates available; restricting to {len(sales_only)} items for revenue intent")
                        filtered = sales_only
            except Exception:
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
                # For Top-K SUM by customer, prefer sales position/invoice sources and de-emphasize cockpit/aggregate views
                if required_action == "topk_sum_by_customer" or (("sum" in metrics) and any(e in ["customer", "customers", "kunde", "kunden"] for e in entities)):
                    def rev_key(c):
                        n = (c.get("table_name") or c.get("name") or c.get("full_name") or "").lower()
                        return (
                            1 if any(tok in n for tok in ["position", "positionen", "rechnung", "rechnungs", "beleg", "belege", "vk", "verkauf"]) else 0,
                            0 if any(tok in n for tok in ["cockpit", "auftragscockpit", "belegegesamt"]) else 1
                        )
                    selected = sorted(selected, key=rev_key, reverse=True)
            except Exception:
                pass
            
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
        Extract search keywords strictly from the IntentParser output.
        No fallback, no augmentation, no trimming.
        """
        base = intent.get("keywords_for_discovery", [])
        logger.info(f"📌 Using intent keywords (exact): {base}")

        # Minimal, intent-driven synonym expansion (single joined query string)
        # This keeps dependency on intent while improving cross-language recall.
        entities = [e.lower() for e in (intent.get("primary_entities") or [])]
        metrics = [m.lower() for m in (intent.get("metrics") or [])]

        extra: List[str] = []
        if any(e in ["customer", "customers", "kunde", "kunden"] for e in entities + base):
            extra += ["kunde", "kunden", "adresse", "adressen", "khkadressen", "customer", "customers"]
        if any(e in ["product", "products", "produkt", "produkte", "artikel", "artikelstamm"] for e in entities + base):
            extra += ["produkt", "produkte", "artikel", "artikelstamm", "artikelnummer", "product", "products"]
        if any(m in ["sum", "total"] for m in metrics) or any(k.lower() in ["umsatz", "revenue", "sales"] for k in base):
            # Revenue/sales domain terms (DE/EN) to help recall sales facts/views
            extra += [
                "umsatz", "betrag", "erloes", "erlös", "revenue", "sales",
                "vk", "verkauf", "rechnung", "rechnungs", "beleg", "belege",
                "position", "positionen", "vkbeleg", "vkbelege", "vkposition", "vkpositionen",
                "auftrag", "auftrags", "faktura"
            ]

        # Build one joined query string to respect the single-call constraint
        joined = " ".join(dict.fromkeys([*(k for k in base if k), *extra]))
        return [joined] if joined else base
    
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
        """Parse MCP search_tables result with robust JSON extraction."""
        if not result or len(result) == 0:
            return []

        try:
            content = result[0].get("text", "")
            # Robustly extract JSON from possible decorated text
            data = _extract_json_from_text(content) if isinstance(content, str) else content

            # Handle different response formats (including {ok, data: {results|tables}})
            tables: List[Dict[str, Any]] = []
            if isinstance(data, dict):
                container = data
                if "data" in data and isinstance(data["data"], dict):
                    container = data["data"]
                if "results" in container:
                    tables = container.get("results", [])
                elif "tables" in container:
                    tables = container.get("tables", [])
            elif isinstance(data, list):
                tables = data
            else:
                return []

            # Normalize table format
            normalized: List[Dict[str, Any]] = []
            for t in tables:
                if isinstance(t, dict):
                    full_name = t.get("full_name", "")
                    name = t.get("table_name") or t.get("name") or full_name
                    # Prefer MCP's relevance_score (0.0-1.0); fallback to score/relevance if present
                    relevance = t.get("relevance_score", t.get("score", t.get("relevance", 0.0)))
                    # Derive booleans from MCP payload
                    derived_is_view = (t.get("type") == "VIEW") if t.get("type") else t.get("is_view", False)
                    estimated_rows = t.get("estimated_rows", None)
                    derived_has_rows = (estimated_rows is not None and estimated_rows > 0) if estimated_rows is not None else t.get("has_rows", True)

                    normalized.append({
                        "table_name": name,
                        "full_name": full_name or name,
                        "relevance_score": float(relevance),
                        "is_view": bool(derived_is_view),
                        "role_coverage": float(t.get("role_coverage", 0)),
                        "has_rows": bool(derived_has_rows),
                        "estimated_rows": estimated_rows if isinstance(estimated_rows, (int, float)) else 0,
                        "column_count": t.get("column_count", 0)
                    })

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