"""
IntentParserAgent - LangGraph Subgraph for Semantic Intent Analysis (Phase 9.1)

This agent is now a FULL LangGraph subgraph that provides agentic reasoning for intent parsing:

1. analyze_query: Initial semantic analysis with LLM
2. classify_operation: Determine operation type (query/schema/health/clarify)
3. extract_entities: Extract semantic entities, metrics, filters
4. validate_intent: Check completeness and confidence scoring
5. handle_ambiguity: Ask for clarification if needed (conditional)
6. refine_intent: Improve intent based on feedback

This provides ROBUST intent parsing with:
- Multi-step reasoning instead of single LLM call
- Built-in error recovery and fallbacks
- Conditional routing for ambiguous queries
- Confidence scoring and validation
- Proper agentic behavior with state management

ARCHITECTURE:
- LangGraph subgraph with 6+ nodes
- Conditional edges for different query types
- State persistence across reasoning steps
- LLM-driven decisions at each step
"""

import logging
import json
import re
import asyncio
import concurrent.futures
from typing import Any, Dict, Optional, List, Literal

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph_integration.contracts.state import BaseState, ParsedIntent

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Helper to run async functions synchronously for compatibility."""
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


class IntentParserAgent:
    """
    LangGraph subgraph for agentic intent parsing with multi-step reasoning.

    Input: {user_input, messages (optional)}
    Output: {intent: ParsedIntent, needs_clarification: bool, clarification_question: str}

    Graph nodes:
    1. analyze_query: Initial LLM analysis of user intent
    2. classify_operation: Determine operation type with confidence
    3. extract_entities: Extract semantic entities, metrics, filters
    4. validate_intent: Check completeness and score confidence
    5. handle_ambiguity: Generate clarification questions if needed
    6. refine_intent: Improve intent based on user feedback
    """

    def __init__(self, llm_model: str = "gpt-4o", llm_temp: float = 0.0):
        """
        Initialize IntentParserAgent with LLM.

        Args:
            llm_model: LLM model name (e.g., "gpt-4o")
            llm_temp: Temperature for LLM (0.0 = deterministic)
        """
        self.llm = ChatOpenAI(model=llm_model, temperature=llm_temp)  # Uses OPENAI_API_KEY from env

    def build_subgraph(self) -> StateGraph:
        """
        Build the LangGraph subgraph for intent parsing.

        Returns:
            Compiled LangGraph subgraph with agentic reasoning
        """
        graph = StateGraph(BaseState)

        # Define nodes (wrap async for sync compatibility)
        graph.add_node("analyze_query", lambda state: _run_async(self._analyze_query_node(state)))
        graph.add_node("classify_operation", lambda state: _run_async(self._classify_operation_node(state)))
        graph.add_node("extract_entities", lambda state: _run_async(self._extract_entities_node(state)))
        graph.add_node("validate_intent", lambda state: _run_async(self._validate_intent_node(state)))
        graph.add_node("handle_ambiguity", lambda state: _run_async(self._handle_ambiguity_node(state)))

        # Define edges
        graph.add_edge("analyze_query", "classify_operation")
        graph.add_edge("classify_operation", "extract_entities")
        graph.add_edge("extract_entities", "validate_intent")

        # Conditional routing: validate → handle_ambiguity (if needed) or END
        def route_after_validation(state: BaseState) -> Literal["handle_ambiguity", END]:
            """Route to ambiguity handling or end based on validation."""
            intent = state.get("intent", {})
            needs_clarification = intent.get("needs_clarification", False)
            confidence = intent.get("confidence", 0.0)

            if needs_clarification or confidence < 0.6:
                return "handle_ambiguity"
            return END

        graph.add_conditional_edges(
            "validate_intent",
            route_after_validation,
            {
                "handle_ambiguity": "handle_ambiguity",
                END: END,
            }
        )

        # Set entry point
        graph.set_entry_point("analyze_query")

        return graph.compile()

    # ==========================================
    # LANGGRAPH NODE IMPLEMENTATIONS
    # ==========================================

    async def _analyze_query_node(self, state: BaseState) -> BaseState:
        """
        Node 1: Initial LLM analysis of user intent.

        Performs broad semantic analysis to understand the query type and extract
        preliminary entities and intent indicators.
        """
        user_input = state.get("user_input", "")
        logger.info(f"🧠 [ANALYZE] Starting analysis of: {user_input}")

        if not user_input or not user_input.strip():
            logger.warning("🧠 [ANALYZE] Empty input detected")
            return {**state, "intent": self._empty_intent(user_input)}

        # Fast-path detection for special operations
        user_lower = user_input.lower()
        if self._is_schema_query(user_lower):
            logger.info("🧠 [ANALYZE] Detected schema query - fast path")
            intent = {
                "operation": "schema_query",
                "primary_entities": [],
                "metrics": [],
                "filters": [],
                "time_window": None,
                "keywords_for_discovery": [],
                "raw_query": user_input,
                "confidence": 1.0,
                "needs_clarification": False
            }
            return {**state, "intent": intent}

        if self._is_health_check(user_lower):
            logger.info("🧠 [ANALYZE] Detected health check - fast path")
            intent = {
                "operation": "health_check",
                "primary_entities": [],
                "metrics": [],
                "filters": [],
                "time_window": None,
                "keywords_for_discovery": [],
                "raw_query": user_input,
                "confidence": 1.0,
                "needs_clarification": False
            }
            return {**state, "intent": intent}

        # For data queries, do initial analysis
        prompt = f"""
Analyze this database query and provide initial intent classification.

Query: "{user_input}"

Provide JSON with:
{{
  "query_type": "data_query",  // or "schema_query", "health_check", "clarify"
  "broad_category": "reporting|analysis|operational|lookup",
  "key_topics": ["topic1", "topic2"],  // Main subjects mentioned
  "intent_indicators": ["count", "sum", "filter", "trend"],  // What user wants to do
  "complexity": "simple|moderate|complex",  // Query complexity level
  "confidence": 0.8  // Initial confidence [0.0-1.0]
}}

Respond ONLY with JSON, no markdown blocks.
"""
        try:
            response = await self.llm.ainvoke(prompt)
            response_text = self._strip_markdown_blocks(response.content.strip())
            analysis = json.loads(response_text)

            # Store initial analysis in state for next nodes
            state["query_analysis"] = analysis
            logger.info(f"🧠 [ANALYZE] Initial analysis: {analysis.get('broad_category')} query, confidence {analysis.get('confidence')}")
            return state

        except Exception as e:
            logger.warning(f"🧠 [ANALYZE] LLM analysis failed: {e}, falling back to heuristics")
            # Fallback analysis
            analysis = {
                "query_type": "data_query",
                "broad_category": "lookup",
                "key_topics": self._extract_basic_keywords(user_input),
                "intent_indicators": ["lookup"],
                "complexity": "simple",
                "confidence": 0.3
            }
            state["query_analysis"] = analysis
            return state

    async def _classify_operation_node(self, state: BaseState) -> BaseState:
        """
        Node 2: Determine operation type with confidence scoring.

        Uses the initial analysis to classify the exact operation type.
        """
        user_input = state.get("user_input", "")
        analysis = state.get("query_analysis", {})

        logger.info(f"🧠 [CLASSIFY] Classifying operation for: {user_input}")

        # Use LLM to classify operation with more precision
        prompt = f"""
Based on this query analysis, classify the exact operation type.

Query: "{user_input}"
Initial Analysis: {json.dumps(analysis)}

Classify into one of:
- "query": Normal data retrieval (SELECT queries)
- "schema_query": Database structure questions (SHOW TABLES, DESCRIBE)
- "health_check": System status questions
- "clarify": Ambiguous or needs clarification

Return JSON:
{{
  "operation": "query",
  "confidence": 0.9,
  "reasoning": "Brief explanation",
  "alternative_operations": ["query"]  // If multiple possibilities
}}

Respond ONLY with JSON.
"""
        try:
            response = await self.llm.ainvoke(prompt)
            response_text = self._strip_markdown_blocks(response.content.strip())
            classification = json.loads(response_text)

            # Update intent with operation classification
            intent = state.get("intent", {})
            intent.update({
                "operation": classification.get("operation", "query"),
                "operation_confidence": classification.get("confidence", 0.5),
                "classification_reasoning": classification.get("reasoning", ""),
                "alternative_operations": classification.get("alternative_operations", [])
            })

            logger.info(f"🧠 [CLASSIFY] Classified as: {intent['operation']} (confidence: {intent.get('operation_confidence')})")
            return {**state, "intent": intent}

        except Exception as e:
            logger.warning(f"🧠 [CLASSIFY] LLM classification failed: {e}, using fallback")
            intent = state.get("intent", {})
            intent.update({
                "operation": "query",  # Default to query
                "operation_confidence": 0.4,
                "classification_reasoning": "Fallback classification"
            })
            return {**state, "intent": intent}

    async def _extract_entities_node(self, state: BaseState) -> BaseState:
        """
        Node 3: Extract semantic entities, metrics, and filters.

        The core extraction logic with detailed semantic understanding.
        """
        user_input = state.get("user_input", "")
        analysis = state.get("query_analysis", {})
        intent = state.get("intent", {})

        logger.info(f"🧠 [EXTRACT] Extracting entities from: {user_input}")

        # Detailed extraction prompt
        prompt = f"""
Extract structured intent from this ERP database query.

Query: "{user_input}"
Context: {json.dumps(analysis)}

Return JSON with EXACTLY these fields:
{{
  "primary_entities": ["entity1", "entity2"],  // 1-3 main business entities (customers, products, orders)
  "secondary_entities": ["entity3"],           // Supporting entities if any
  "metrics": ["count", "sum", "avg"],          // What to measure/aggregate
  "filters": [                                 // Structured filter conditions
    {{
      "field": "column_name",
      "operator": "<|>|=|!=",
      "value": "filter_value",
      "description": "human readable description"
    }}
  ],
  "time_window": {{
    "period": "last_month|last_quarter|this_year",
    "start": "YYYY-MM-DD",
    "end": "YYYY-MM-DD"
  }} or null,
  "keywords_for_discovery": ["clean", "keywords"],  // For table search (NO noise words)
  "confidence": 0.85
}}

EXAMPLES:

Query: "How many customers do we have?"
{{
  "primary_entities": ["customers"],
  "secondary_entities": [],
  "metrics": ["count"],
  "filters": [],
  "time_window": null,
  "keywords_for_discovery": ["customers"],
  "confidence": 1.0
}}

Query: "Which products have inventory below 100?"
{{
  "primary_entities": ["products"],
  "secondary_entities": [],
  "metrics": ["inventory"],
  "filters": [{{"field": "inventory", "operator": "<", "value": "100", "description": "below 100"}}],
  "time_window": null,
  "keywords_for_discovery": ["products", "inventory", "stock"],
  "confidence": 0.95
}}

Respond ONLY with JSON.
"""
        try:
            response = await self.llm.ainvoke(prompt)
            response_text = self._strip_markdown_blocks(response.content.strip())
            extracted = json.loads(response_text)

            # Update intent with extracted information
            intent.update({
                "primary_entities": extracted.get("primary_entities", [])[:3],
                "secondary_entities": extracted.get("secondary_entities", [])[:2],
                "metrics": extracted.get("metrics", [])[:5],
                "filters": extracted.get("filters", [])[:10],
                "time_window": extracted.get("time_window"),
                "keywords_for_discovery": extracted.get("keywords_for_discovery", [])[:10],
                "extraction_confidence": extracted.get("confidence", 0.5)
            })

            # Derived action hints for downstream agents (discovery/planning/execution)
            derived = self._derive_action_hints(state.get("user_input", ""), intent)
            intent.update(derived)
            # Expand keywords with German translations and related terms
            base_keywords = intent.get("keywords_for_discovery", [])
            expanded_keywords = self._expand_keywords_with_translations(base_keywords, intent.get("primary_entities", []))
            intent["keywords_for_discovery"] = expanded_keywords[:10]

            # Merge derived extra keywords into discovery keywords (dedup + cap)
            try:
                if derived.get("extra_keywords"):
                    merged_kw = expanded_keywords + list(derived.get("extra_keywords") or [])
                    # deduplicate preserving order
                    seen = set()
                    merged_kw = [k for k in merged_kw if not (k in seen or seen.add(k))]
                    intent["keywords_for_discovery"] = merged_kw[:10]
            except Exception:
                pass

            logger.info(f"🧠 [EXTRACT] Entities: {intent['primary_entities']}, Keywords: {intent['keywords_for_discovery']}")
            return {**state, "intent": intent}

        except Exception as e:
            logger.warning(f"🧠 [EXTRACT] LLM extraction failed: {e}, using fallback")
            # Fallback extraction
            fallback = self._fallback_entity_extraction(user_input)
            intent.update(fallback)

            # Expand keywords with German translations
            base_keywords = intent.get("keywords_for_discovery", [])
            expanded_keywords = self._expand_keywords_with_translations(base_keywords, intent.get("primary_entities", []))
            intent["keywords_for_discovery"] = expanded_keywords[:10]

            # Also derive action hints on fallback
            derived = self._derive_action_hints(user_input, intent)
            intent.update(derived)
            try:
                if derived.get("extra_keywords"):
                    merged_kw = expanded_keywords + list(derived.get("extra_keywords") or [])
                    seen = set()
                    merged_kw = [k for k in merged_kw if not (k in seen or seen.add(k))]
                    intent["keywords_for_discovery"] = merged_kw[:10]
            except Exception:
                pass
            return {**state, "intent": intent}

    async def _validate_intent_node(self, state: BaseState) -> BaseState:
        """
        Node 4: Validate intent completeness and score overall confidence.

        Checks if the extracted intent is complete and coherent.
        """
        intent = state.get("intent", {})

        logger.info(f"🧠 [VALIDATE] Validating intent completeness")

        # Validation criteria
        has_entities = len(intent.get("primary_entities", [])) > 0
        has_keywords = len(intent.get("keywords_for_discovery", [])) > 0
        operation = intent.get("operation", "query")
        extraction_confidence = intent.get("extraction_confidence", 0.5)

        # Calculate overall confidence
        confidence_factors = []
        if has_entities: confidence_factors.append(0.3)
        if has_keywords: confidence_factors.append(0.3)
        if extraction_confidence > 0.7: confidence_factors.append(0.4)

        overall_confidence = min(sum(confidence_factors), 1.0)

        # Determine if clarification is needed
        needs_clarification = (
            not has_entities or
            not has_keywords or
            overall_confidence < 0.6 or
            operation == "clarify"
        )

        intent.update({
            "confidence": overall_confidence,
            "needs_clarification": needs_clarification,
            "validation_notes": {
                "has_entities": has_entities,
                "has_keywords": has_keywords,
                "extraction_confidence": extraction_confidence
            }
        })

        logger.info(f"🧠 [VALIDATE] Confidence: {overall_confidence:.2f}, Needs clarification: {needs_clarification}")
        return {**state, "intent": intent}

    async def _handle_ambiguity_node(self, state: BaseState) -> BaseState:
        """
        Node 5: Generate clarification questions for ambiguous queries.

        When validation fails, ask the user for clarification.
        """
        user_input = state.get("user_input", "")
        intent = state.get("intent", {})

        logger.info(f"🧠 [AMBIGUITY] Handling ambiguous query: {user_input}")

        # Generate clarification question
        prompt = f"""
This query is ambiguous and needs clarification:

Query: "{user_input}"
Current Intent: {json.dumps(intent, indent=2)}

Generate a helpful clarification question that will help disambiguate what the user wants.

Return JSON:
{{
  "clarification_question": "What specific aspect would you like to see?",
  "suggested_options": ["Option 1", "Option 2"],
  "reason_ambiguous": "Brief explanation of what's unclear"
}}

Keep the question clear and actionable.
"""
        try:
            response = await self.llm.ainvoke(prompt)
            response_text = self._strip_markdown_blocks(response.content.strip())
            clarification = json.loads(response_text)

            intent.update({
                "needs_clarification": True,
                "clarification_question": clarification.get("clarification_question", "Could you please clarify your request?"),
                "suggested_options": clarification.get("suggested_options", []),
                "ambiguity_reason": clarification.get("reason_ambiguous", "Query is unclear")
            })

            logger.info(f"🧠 [AMBIGUITY] Generated clarification: {intent['clarification_question']}")
            return {**state, "intent": intent}

        except Exception as e:
            logger.warning(f"🧠 [AMBIGUITY] Failed to generate clarification: {e}")
            # Fallback clarification
            intent.update({
                "needs_clarification": True,
                "clarification_question": "Could you please provide more details about what you're looking for?",
                "suggested_options": ["Customers", "Products", "Orders", "Sales"],
                "ambiguity_reason": "Unable to determine specific intent"
            })
            return {**state, "intent": intent}

    # ==========================================
    # HELPER METHODS
    # ==========================================

    def _strip_markdown_blocks(self, text: str) -> str:
        """Strip markdown code blocks from LLM response."""
        if "```" in text:
            pattern = r'```(?:json)?\s*(.*?)\s*```'
            matches = re.findall(pattern, text, re.DOTALL)
            if matches:
                return matches[0].strip()
        return text

    def _extract_basic_keywords(self, text: str) -> list:
        """Basic keyword extraction for fallback."""
        stop_words = {
            "the", "a", "an", "is", "are", "how", "many", "show", "me",
            "what", "which", "do", "we", "have", "has", "get", "find"
        }
        words = text.lower().split()
        return [w.strip("?,.!;:") for w in words if w not in stop_words and len(w) > 2][:3]

    def _fallback_entity_extraction(self, user_input: str) -> dict:
        """Fallback entity extraction when LLM fails."""
        logger.info(f"🧠 Using fallback entity extraction for: {user_input}")

        keywords = self._extract_basic_keywords(user_input)

        return {
            "primary_entities": keywords[:2],
            "secondary_entities": [],
            "metrics": ["count"] if "count" in user_input.lower() else [],
            "filters": [],
            "time_window": None,
            "keywords_for_discovery": keywords,
            "extraction_confidence": 0.3
        }

    def _derive_action_hints(self, user_input: str, intent: dict) -> dict:
        """Derive structured action hints from user input and extracted intent.

        Produces fields to guide discovery and planning:
        - required_action: one of ["count", "topk_sum_by_customer", "sum_with_period", "trend_series", "month_count", "interpret_previous"]
        - group_by: e.g., "customer"
        - top_k: integer if applicable
        - time_granularity: "year"|"month" for trends
        """
        text = (user_input or "").lower()
        entities = [e.lower() for e in (intent.get("primary_entities") or [])]
        metrics = [m.lower() for m in (intent.get("metrics") or [])]

        # FALLBACK: Extract metrics from raw text if LLM extraction returned empty
        if not metrics:
            if any(k in text for k in ["sum", "total", "umsatz", "verkauf", "revenue", "improved"]):
                metrics.append("sum")
            if any(k in text for k in ["count", "how many", "wie viele", "number of"]):
                metrics.append("count")
            if any(k in text for k in ["average", "avg", "mean", "durchschnitt", "mittelwert"]):
                metrics.append("avg")

        # top_k detection
        top_k = None
        try:
            m = re.search(r"top\s+(\d{1,3})", text)
            if m:
                top_k = int(m.group(1))
        except Exception:
            top_k = None

        # group_by detection for customers
        group_by = None
        if any(e in ["customer", "customers", "kunde", "kunden"] for e in entities):
            group_by = "customer"

        # time granularity
        time_granularity = None
        if any(kw in text for kw in ["per year", "yearly", "years", "letzten jahren", "jahre"]):
            time_granularity = "year"
        if any(kw in text for kw in ["per month", "monthly", "months", "monat", "monate"]):
            time_granularity = time_granularity or "month"

        # action classification
        required_action = None
        # Follow-up interpretation on prior results (no new DB query)
        if any(p in text for p in [
            "these results", "those results", "previous results", "previous answer", "last answer",
            "that table", "above table", "from that list", "in that list", "in those rows",
            "sort them", "filter them", "group them", "format them", "explain these"
        ]):
            required_action = "interpret_previous"
        if ("sum" in metrics or "total" in metrics or "umsatz" in text) and (group_by == "customer"):
            required_action = "topk_sum_by_customer" if ("top" in text or top_k) else "sum_by_customer"
        elif ("count" in metrics) and any(m in text for m in ["october", "oktober", "january", "februar", "march", "april", "mai", "juni", "juli", "august", "september", "november", "dezember"]):
            required_action = "month_count"
        elif any(kw in text for kw in ["over the last", "last \d+ years", "last \d+ months", "entwickel", "trend"]):
            required_action = "trend_series"
        elif any(kw in text for kw in ["growth", "wachstum", "increase", "gewachsen", "entwicklung"]) and any(kw in text for kw in ["over", "last", "years", "jahre", "time"]):
            required_action = "growth_analysis"
        elif any(kw in text for kw in ["productivity", "produktivität", "performance", "leistung", "efficiency", "effizienz"]) and any(kw in text for kw in ["department", "abteilung", "bereich", "by department"]):
            required_action = "department_productivity"
        elif any(kw in text for kw in ["vs", "versus", "compared", "comparison", "vergleich", "gegenüber", "gegen", "quarter", "quartal"]):
            required_action = "comparative_analysis"
        # NEW: SUM/TOTAL + temporal period (e.g., "sales from Sept to Oct", "improved from Sept to Oct")
        elif ("sum" in metrics or "total" in metrics or "umsatz" in text or "verkauf" in text or "sales" in text) and \
             any(m in text for m in ["october", "oktober", "january", "februar", "march", "april", "mai", "juni", "juli", "august", "september", "november", "dezember", "january", "february"]):
            required_action = "sum_with_period"
        # FALLBACK: Explicit temporal queries with words like "improved", "changed", "from X to Y"
        elif any(k in text for k in ["improved", "changed", "growth", "increased", "decreased", "from", "between"]) and \
             any(m in text for m in ["october", "oktober", "september", "juni", "juli", "august", "januar", "februar", "march", "april", "mai", "november", "dezember"]):
            # Even without explicit sum/sales keywords, temporal with period indicators suggests time-series aggregation
            required_action = "sum_with_period"
        elif "count" in metrics or "how many" in text or "wie viele" in text:
            required_action = "count"

        # Default top_k
        if required_action in ["topk_sum_by_customer"] and top_k is None and "top" in text:
            top_k = 5

        # PHASE 6: Clarification loop for ambiguous queries
        needs_clarification = self._check_needs_clarification(text, entities, metrics, required_action)

        # Enrich discovery keywords for specific actions (kept within intent parsing)
        extra_keywords: list[str] = []
        try:
            if required_action in ["topk_sum_by_customer", "sum_by_customer", "sum_with_period"]:
                extra_keywords = [
                    # sales/revenue domain (DE/EN)
                    "umsatz", "verkauf", "vk", "rechnung", "rechnungen", "rechnungsposition", "position", "positionen",
                    "invoice", "invoices", "order", "orders", "faktura", "amount", "betrag", "preis", "wert"
                ]
        except Exception:
            extra_keywords = []

        return {
            "required_action": required_action,
            "group_by": group_by,
            "top_k": top_k,
            "time_granularity": time_granularity,
            "extra_keywords": extra_keywords
        }

    def _expand_keywords_with_translations(self, base_keywords: list, entities: list) -> list:
        """Expand keywords with German translations and related terms for better table discovery."""
        expanded = list(base_keywords)  # Start with original keywords

        # Entity-specific translations
        entity_translations = {
            "customer": ["kunde", "kunden", "client", "adressen", "contacts"],
            "customers": ["kunde", "kunden", "client", "adressen", "contacts"],
            "product": ["produkt", "produkte", "artikel", "item", "artikel"],
            "products": ["produkt", "produkte", "artikel", "item", "artikel"],
            "project": ["projekt", "projekte", "task", "job"],
            "projects": ["projekt", "projekte", "task", "job"],
            "sales": ["verkauf", "umsatz", "revenue", "rechnung", "invoice"],
            "inventory": ["lager", "stock", "bestand", "inventory"],
            "order": ["auftrag", "bestellung", "order"],
            "orders": ["auftrag", "bestellung", "order"],
            "supplier": ["lieferant", "supplier", "vendor"],
            "suppliers": ["lieferant", "supplier", "vendor"]
        }

        # Add translations for recognized entities
        for entity in entities:
            entity_lower = entity.lower()
            if entity_lower in entity_translations:
                expanded.extend(entity_translations[entity_lower])

        # Add common German business terms
        german_business_terms = [
            "khk", "adressen", "kontakt", "firma", "unternehmen",
            "position", "positionen", "kopf", "zeile"
        ]
        expanded.extend(german_business_terms)

        # Remove duplicates while preserving order
        seen = set()
        deduplicated = []
        for keyword in expanded:
            if keyword not in seen:
                seen.add(keyword)
                deduplicated.append(keyword)

        return deduplicated

    def _is_schema_query(self, user_lower: str) -> bool:
        """Detect schema/structure queries."""
        schema_keywords = [
            "what table", "schema", "database structure", "what columns",
            "what fields", "list table", "how many table", "show table",
            "describe", "structure"
        ]
        return any(kw in user_lower for kw in schema_keywords)

    def _is_health_check(self, user_lower: str) -> bool:
        """Detect health/status queries."""
        health_keywords = [
            "health", "status", "working", "running", "online", "available",
            "connected", "connection", "alive"
        ]
        return any(kw in user_lower for kw in health_keywords)

    def _empty_intent(self, user_input: str) -> dict:
        """Return empty intent for empty input."""
        return {
            "operation": "query",
            "primary_entities": [],
            "metrics": [],
            "filters": [],
            "time_window": None,
            "keywords_for_discovery": [],
            "raw_query": user_input or "",
            "confidence": 0.0,
            "needs_clarification": False
        }

    def _check_needs_clarification(self, text: str, entities: List[str], metrics: List[str], required_action: str) -> bool:
        """
        Check if the query needs clarification based on ambiguity indicators.

        Returns True if clarification is needed.
        """
        text_lower = text.lower()

        # Check for multiple conflicting metrics
        conflicting_metrics = [
            ("count", "sum", "total"),
            ("min", "max"),
        ]
        for conflict_group in conflicting_metrics:
            found_metrics = [m for m in metrics if m.lower() in conflict_group]
            if len(found_metrics) > 1:
                logger.info(f"🤔 [CLARIFICATION] Conflicting metrics: {found_metrics}")
                return True

        # Check for ambiguous entities (multiple business domains)
        business_domains = {
            "customer": ["kunde", "kunden", "customer", "client"],
            "product": ["produkt", "produkte", "artikel", "product", "item"],
            "project": ["projekt", "project", "task", "job"],
            "sales": ["verkauf", "sales", "umsatz", "revenue"],
            "inventory": ["lager", "inventory", "stock", "bestand"]
        }

        found_domains = []
        for domain, keywords in business_domains.items():
            if any(kw in text_lower for kw in keywords) or any(e.lower() in keywords for e in entities):
                found_domains.append(domain)

        if len(found_domains) > 2:
            logger.info(f"🤔 [CLARIFICATION] Multiple business domains: {found_domains}")
            return True

        # Check for vague time periods
        vague_times = ["recently", "lately", "recent", "past", "some time ago", "before"]
        if any(vt in text_lower for vt in vague_times) and not any(num in text for num in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "one", "two", "three"]):
            logger.info("🤔 [CLARIFICATION] Vague time period detected")
            return True

        # Check for ambiguous ranking requests
        if "top" in text_lower and not any(char.isdigit() for char in text):
            logger.info("🤔 [CLARIFICATION] 'Top' without specific number")
            return True

        # Check for unclear comparative queries
        if any(word in text_lower for word in ["vs", "versus", "compared", "comparison", "better", "worse"]) and len(entities) < 2:
            logger.info("🤔 [CLARIFICATION] Comparative query with insufficient entities")
            return True

        # Check for strategic queries that might need more context
        strategic_actions_needing_clarification = ["growth_analysis", "department_productivity"]
        if required_action in strategic_actions_needing_clarification and len(entities) == 0:
            logger.info(f"🤔 [CLARIFICATION] Strategic action '{required_action}' needs entity clarification")
            return True

        return False