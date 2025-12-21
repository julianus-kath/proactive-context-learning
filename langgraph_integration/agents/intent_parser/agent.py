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
import os
from typing import Any, Dict, Optional, List, Literal

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph_integration.contracts.state import BaseState, ParsedIntent
from langgraph_integration.agents.intent_parser.templates import infer_template_and_action

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
        self.llm_model = llm_model
        self.llm_temp = llm_temp
        self.llm = None  # Initialize as None first

        # Only initialize LLM if API key is available
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        no_llm = os.getenv("NO_LLM", "").lower() in ("1", "true", "yes")
        if api_key and not no_llm:
            try:
                self.llm = ChatOpenAI(model=llm_model, temperature=llm_temp)
            except Exception as e:
                logger.warning(f"🧠 [LLM_INIT] Failed to initialize LLM: {e}")
        else:
            logger.warning("🧠 [LLM_INIT] Skipping LLM initialization - no API key or NO_LLM set")

    def _can_use_llm(self) -> bool:
        """Check if LLM can be used (API key present and not explicitly disabled)."""
        if self.llm is None:
            logger.warning("🧠 [LLM_GUARD] LLM not initialized - skipping LLM calls")
            return False
        return True

    async def parse(self, user_input: str, messages: Optional[List[Dict[str, Any]]] = None) -> ParsedIntent:
        """Convenience method to parse intent directly without manual state management."""
        state: BaseState = {
            "user_input": user_input,
            "messages": messages or [],
        }
        subgraph = self.build_subgraph()
        result = await subgraph.ainvoke(state)
        return result.get("intent", {})

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

        conversation_context = self._format_message_history(state.get("messages", []))

        # For data queries, do initial analysis
        prompt = f"""
Analyze this database query and provide initial intent classification.

Conversation history (most recent last):
{conversation_context or "<none>"}

Current user query: "{user_input}"
The query may be written in German or English. Treat German business terms (e.g., "Kunden", "Umsatz") as first-class concepts and keep them in the output without translating them.

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
            if not self._can_use_llm():
                raise ValueError("LLM not available - API key missing or disabled")
            response = await self.llm.ainvoke(prompt)
            response_text = self._strip_markdown_blocks(response.content.strip())
            analysis = json.loads(response_text)

            # Store initial analysis in state for next nodes
            state["query_analysis"] = analysis
            logger.info(f"🧠 [ANALYZE] Initial analysis: {analysis.get('broad_category')} query, confidence {analysis.get('confidence')}")
            return state

        except Exception as e:
            logger.warning(f"🧠 [ANALYZE] LLM analysis failed: {e}. Using minimal heuristic analysis.")
            analysis = {
                "query_type": "data_query",
                "broad_category": "lookup",
                "key_topics": [],
                "intent_indicators": ["lookup"],
                "complexity": "simple",
                "confidence": 0.0
            }
            state["query_analysis"] = analysis
            return state

    async def _classify_operation_node(self, state: BaseState) -> BaseState:
        """
        Node 2: Determine operation type with confidence scoring.

        Uses the initial analysis to classify the exact operation type.
        """
        user_input = state.get("user_input", "")
        intent = state.get("intent", {}) or {}
        preset_operation = intent.get("operation")
        if preset_operation and preset_operation not in {"query", None, ""}:
            logger.info(f"🧠 [CLASSIFY] Operation preset to '{preset_operation}', skipping classification.")
            return {**state, "intent": intent}

        analysis = state.get("query_analysis", {})

        logger.info(f"🧠 [CLASSIFY] Classifying operation for: {user_input}")

        # Use LLM to classify operation with more precision
        conversation_context = self._format_message_history(state.get("messages", []))

        prompt = f"""
Based on this query analysis, classify the exact operation type and detect if this is a refinement of a previous query.

Conversation history (most recent last):
{conversation_context or "<none>"}

Current user query: "{user_input}"
Initial Analysis: {json.dumps(analysis)}

IMPORTANT: Detect refinement queries:
- If the user mentions a table/view name in their message (e.g., "Look in KHKArtikelLagerbewegungen"), and there was a previous assistant message that discussed tables or asked where to look, treat this as a "refine_previous" action.
- If the message refers back to the previous query with "that", "those", "the previous", etc., it's likely a refinement.
- Extract any table names the user explicitly mentions (target_tables).

Classify into one of:
- "query": Normal data retrieval (SELECT queries)
- "schema_query": Database structure questions (SHOW TABLES, DESCRIBE)
- "health_check": System status questions
- "clarify": Ambiguous or needs clarification
- "interpret_previous": Follow-up question about previous results (no new query)

Return JSON:
{{
  "operation": "query",
  "confidence": 0.9,
  "reasoning": "Brief explanation",
  "required_action": "query",  // or "refine_previous", "interpret_previous"
  "target_tables": ["TableName1", "TableName2"],  // Tables the user explicitly mentioned
  "alternative_operations": ["query"]
}}

Respond ONLY with JSON.
"""
        try:
            if not self._can_use_llm():
                raise ValueError("LLM not available - API key missing or disabled")
            response = await self.llm.ainvoke(prompt)
            response_text = self._strip_markdown_blocks(response.content.strip())
            classification = json.loads(response_text)

            # Update intent with operation classification
            intent.update({
                "operation": classification.get("operation", "query"),
                "operation_confidence": classification.get("confidence", 0.5),
                "classification_reasoning": classification.get("reasoning", ""),
                "alternative_operations": classification.get("alternative_operations", []),
                "required_action": classification.get("required_action", "query"),
                "target_tables": classification.get("target_tables", [])
            })

            logger.info(f"🧠 [CLASSIFY] Classified as: {intent['operation']} (confidence: {intent.get('operation_confidence')})")
            if intent.get("required_action") == "refine_previous":
                logger.info(f"🧠 [CLASSIFY] 🔄 Detected refinement query with target tables: {intent.get('target_tables')}")
            return {**state, "intent": intent}

        except Exception as e:
            logger.warning(f"🧠 [CLASSIFY] LLM classification failed: {e}. Requesting clarification.")
            intent = state.get("intent", {}) or {}
            intent.setdefault("primary_entities", [])
            intent.setdefault("metrics", [])
            intent.setdefault("filters", [])
            intent["operation"] = "clarify"
            intent["operation_confidence"] = 0.0
            intent["classification_reasoning"] = "Unable to classify intent from query"
            intent["needs_clarification"] = True
            intent["clarification_question"] = intent.get(
                "clarification_question",
                "Kannst du genauer beschreiben, welche Information du benötigst?"
            )
            intent["ambiguity_reason"] = intent.get("ambiguity_reason", "Operation classification failed")
            intent["keywords_for_discovery"] = intent.get("keywords_for_discovery", [])[:10]
            return {**state, "intent": intent}

    async def _extract_entities_node(self, state: BaseState) -> BaseState:
        """
        Node 3: Extract semantic entities, metrics, and filters.

        The core extraction logic with detailed semantic understanding.
        """
        user_input = state.get("user_input", "")
        analysis = state.get("query_analysis", {})
        intent = state.get("intent", {})
        conversation_context = self._format_message_history(state.get("messages", []))

        if intent.get("operation") != "query":
            logger.info(f"🧠 [EXTRACT] Skipping extraction for operation '{intent.get('operation')}'")
            return {**state, "intent": intent}

        logger.info(f"🧠 [EXTRACT] Extracting entities from: {user_input}")

        # Detailed extraction prompt
        prompt = f"""
        Extract structured intent from this ERP database query.

        Conversation history (most recent last):
        {conversation_context or "<none>"}

        Current user query: "{user_input}"
        Context: {json.dumps(analysis)}
        The question may use German (DE) or English (EN) terminology. Preserve meaningful German nouns/phrases in the output. You may include English equivalents only if they appear explicitly in the question, but never drop or translate away the original vocabulary.

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
            if not self._can_use_llm():
                raise ValueError("LLM not available - API key missing or disabled")
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
            intent["raw_query"] = user_input

            # Derived action hints for downstream agents (discovery/planning/execution)
            derived = self._derive_action_hints(state.get("user_input", ""), intent)
            intent.update(derived)
            
            # Infer analytic template using comprehensive template-based classifier
            template_name, required_action, template_params = infer_template_and_action(
                user_input=state.get("user_input", ""),
                primary_entities=intent.get("primary_entities", []),
                metrics=intent.get("metrics", []),
                filters=intent.get("filters", []),
                time_window=intent.get("time_window")
            )
            if template_name:
                intent["analytic_template"] = template_name
                intent["template_params"] = template_params
                intent["required_action"] = required_action
                logger.info(f"🎯 [TEMPLATE] Inferred template: {template_name}, action: {required_action}, params: {template_params}")
            
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
            logger.warning(f"🧠 [EXTRACT] LLM extraction failed: {e}. Marking intent for clarification.")
            intent.setdefault("primary_entities", [])
            intent.setdefault("metrics", [])
            intent.setdefault("filters", [])
            intent["keywords_for_discovery"] = (intent.get("keywords_for_discovery") or [])[:10]
            intent["extraction_confidence"] = 0.0
            intent["needs_clarification"] = True
            intent["clarification_question"] = intent.get(
                "clarification_question",
                "Ich konnte nicht eindeutig erkennen, welche Daten du brauchst. Kannst du das genauer beschreiben?"
            )
            intent["ambiguity_reason"] = intent.get("ambiguity_reason", "Intent extraction failed")
            intent["raw_query"] = user_input
            return {**state, "intent": intent}

    async def _validate_intent_node(self, state: BaseState) -> BaseState:
        """
        Node 4: Validate intent completeness and score overall confidence.

        Checks if the extracted intent is complete and coherent.
        """
        intent = state.get("intent", {})

        if intent.get("operation") != "query":
            logger.info(f"🧠 [VALIDATE] Skipping validation for operation '{intent.get('operation')}'")
            return {**state, "intent": intent}

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
            if not self._can_use_llm():
                raise ValueError("LLM not available - API key missing or disabled")
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

    def _detect_derived_metrics(self, text: str, metrics: List[str]) -> List[str]:
        """
        Detect derived metrics (profit_margin, ROI, contribution_margin, etc.)
        that require computation from base columns rather than direct selection.
        
        Returns list of derived metric names to append to metrics.
        """
        derived = []
        text_lower = text.lower()
        
        profit_keywords = ["profit margin", "profit_margin", "marge", "margin", "profitabilität", "profitability"]
        if any(kw in text_lower for kw in profit_keywords) and "profit_margin" not in metrics:
            derived.append("profit_margin")
        
        roi_keywords = ["roi", "return on investment", "return-on-investment", "rentabilität"]
        if any(kw in text_lower for kw in roi_keywords) and "roi" not in metrics:
            derived.append("roi")
        
        contrib_keywords = ["contribution margin", "contribution_margin", "deckungsbeitrag"]
        if any(kw in text_lower for kw in contrib_keywords) and "contribution_margin" not in metrics:
            derived.append("contribution_margin")
        
        cogs_keywords = ["cogs margin", "cogs_margin", "cost margin"]
        if any(kw in text_lower for kw in cogs_keywords) and "cogs_margin" not in metrics:
            derived.append("cogs_margin")
        
        return derived

    def _detect_analytic_template(self, user_input: str, intent: dict) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        Detect if the user query matches a known analytic template archetype.
        
        Templates:
        - COUNT_ENTITY: "How many X do we have?"
        - TOP_K_BY_METRIC: "Which X have the highest/lowest Y?"
        - PERIOD_COMPARISON: "Compare X vs Y across time periods"
        
        Returns:
            (template_name, template_params) or (None, None) if no template matches
        """
        user_lower = user_input.lower()
        metrics = intent.get("metrics", [])
        entities = intent.get("primary_entities", [])
        
        en_count_keywords = ["how many", "count", "total", "number of"]
        de_count_keywords = ["wie viele", "wie viel", "insgesamt", "gesamt"]
        
        en_topk_keywords = ["highest", "lowest", "top", "most", "best", "worst", "largest", "biggest", "smallest"]
        de_topk_keywords = ["höchsten", "höchste", "niedrigsten", "niedrigste", "top", "beste", "besten", "größten", "kleinsten"]
        
        en_comparison_keywords = ["compare", "versus", "vs", "between", "difference", "vs.", "compared to"]
        de_comparison_keywords = ["vergleich", "versus", "gegenüber", "zwischen", "unterschied", "im vergleich"]
        
        en_derived_metrics = ["profit margin", "roi", "contribution margin", "revenue per", "cost per", "ratio"]
        de_derived_metrics = ["gewinn", "gewinnmarge", "marge", "beitrag", "rentabilität", "rendite"]
        
        has_count_keyword = any(kw in user_lower for kw in en_count_keywords + de_count_keywords)
        has_topk_keyword = any(kw in user_lower for kw in en_topk_keywords + de_topk_keywords)
        has_comparison_keyword = any(kw in user_lower for kw in en_comparison_keywords + de_comparison_keywords)
        has_derived_metric = any(dm in user_lower for dm in en_derived_metrics + de_derived_metrics)
        
        required_action = intent.get("required_action", "").lower()
        top_k = intent.get("top_k")
        group_by = intent.get("group_by")
        
        if has_count_keyword and not has_topk_keyword and not has_comparison_keyword:
            return ("COUNT_ENTITY", {
                "entity": entities[0] if entities else "rows"
            })
        
        if (has_topk_keyword or required_action == "ranked_metrics") and (group_by or entities):
            template_params = {
                "metric": metrics[0] if metrics else (entities[0] if entities else "value"),
                "group_by": group_by or (entities[0] if entities else None),
                "top_k": top_k or 10,
                "order": "desc" if has_topk_keyword and not any(x in user_lower for x in ["lowest", "niedrigsten"]) else "asc"
            }
            return ("TOP_K_BY_METRIC", template_params)
        
        if has_comparison_keyword and intent.get("time_window"):
            time_window = intent.get("time_window", {})
            return ("PERIOD_COMPARISON", {
                "periods": intent.get("filters", []),
                "metric": metrics[0] if metrics else "count",
                "group_by": group_by,
                "time_window": time_window
            })
        
        return (None, None)

    def _derive_action_hints(self, user_input: str, intent: dict) -> dict:
        """Derive structured action hints from user input and extracted intent.

        Produces fields to guide discovery and planning:
        - required_action: one of ["count", "topk_sum_by_customer", "sum_with_period", "trend_series", "month_count", "ranked_metrics", "interpret_previous"]
        - group_by: e.g., "customer" or "product"
        - top_k: integer if applicable
        - time_granularity: "year"|"month" for trends
        """
        text = (user_input or "").lower()
        entities = [e.lower() for e in (intent.get("primary_entities") or [])]
        metrics = [m.lower() for m in (intent.get("metrics") or [])]
        
        if any(m in ["sales", "umsatz", "revenue", "verkauf", "total_sales"] for m in metrics) and "sum" not in metrics:
            metrics.append("sum")

        # Detect derived metrics (profit margin, ROI, contribution margin, etc.)
        derived_metrics = self._detect_derived_metrics(text, metrics)
        if derived_metrics:
            metrics.extend(derived_metrics)

        # Heuristic enrichment if metrics missing
        if not metrics:
            if any(k in text for k in ["sum", "total", "umsatz", "verkauf", "revenue", "improved"]):
                metrics.append("sum")
            if any(k in text for k in ["count", "how many", "wie viele", "number of"]):
                metrics.append("count")
            if any(k in text for k in ["average", "avg", "mean", "durchschnitt", "mittelwert"]):
                metrics.append("avg")

        # Detect ranking keywords (highest, top, most, best, largest, biggest, smallest, lowest)
        ranking_keywords = ["highest", "top", "most", "best", "largest", "biggest", "smallest", "lowest", "best performing", "worst performing"]
        has_ranking_keyword = any(kw in text for kw in ranking_keywords)

        # top_k detection - enhanced with ranking keywords
        top_k = None
        try:
            m = re.search(r"top\s+(\d{1,3})", text)
            if m:
                top_k = int(m.group(1))
            elif has_ranking_keyword and top_k is None:
                top_k = 10
        except Exception:
            top_k = None

        # group_by detection for customers and products
        group_by = None
        if any(e in ["customer", "customers", "kunde", "kunden", "client", "clients"] for e in entities):
            group_by = "customer"
        elif any(e in ["product", "products", "produkt", "produkte", "artikel", "items"] for e in entities):
            group_by = "product"

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
        
        metrics_lower = [m.lower() for m in metrics]
        
        # NEW: Handle derived metrics with ranking (profit_margin, roi, contribution_margin, etc.)
        if has_ranking_keyword and group_by and any(dm in metrics_lower for dm in ["profit_margin", "roi", "contribution_margin", "margin", "cogs_margin"]):
            required_action = "ranked_metrics"
            if top_k is None:
                top_k = 10
        
        wants_sum = (
            "sum" in metrics_lower
            or "total" in metrics_lower
            or "sales" in metrics_lower
            or "revenue" in metrics_lower
            or "umsatz" in text
            or "verkauf" in text
            or "sales" in text
        )
        
        if required_action is None:
            if wants_sum and group_by == "customer":
                required_action = "topk_sum_by_customer" if ("top" in text or top_k or has_ranking_keyword) else "sum_by_customer"
            elif wants_sum and group_by == "product":
                required_action = "topk_sum_by_product" if ("top" in text or top_k or has_ranking_keyword) else "sum_by_product"
            elif ("count" in metrics) and any(m in text for m in ["october", "oktober", "january", "februar", "march", "april", "mai", "juni", "juli", "august", "september", "november", "dezember"]):
                required_action = "month_count"
            elif any(kw in text for kw in ["over the last", "last \\d+ years", "last \\d+ months", "entwickel", "trend"]):
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
            # Temporal queries with words like "improved", "changed", "from X to Y"
            elif any(k in text for k in ["improved", "changed", "growth", "increased", "decreased", "from", "between"]) and \
                 any(m in text for m in ["october", "oktober", "september", "juni", "juli", "august", "januar", "februar", "march", "april", "mai", "november", "dezember"]):
                required_action = "sum_with_period"
            elif "count" in metrics or "how many" in text or "wie viele" in text:
                required_action = "count"

        # Ensure top_k is set for ranking queries
        if required_action in ["topk_sum_by_customer", "topk_sum_by_product", "ranked_metrics"] and top_k is None:
            if has_ranking_keyword or "top" in text:
                top_k = 10
            elif required_action == "topk_sum_by_customer" or required_action == "topk_sum_by_product":
                top_k = 5

        # PHASE 6: Clarification loop for ambiguous queries
        needs_clarification = self._check_needs_clarification(text, entities, metrics, required_action)

        # Enrich discovery keywords for specific actions (kept within intent parsing)
        extra_keywords: list[str] = []
        try:
            if required_action in [
                "topk_sum_by_customer",
                "sum_by_customer",
                "topk_sum_by_product",
                "sum_by_product",
                "sum_with_period",
            ]:
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


    def _format_message_history(self, messages: List[Dict[str, Any]], limit: int = 6) -> str:
        """Format recent conversation turns so LLM prompts have context."""
        if not messages:
            return ""

        formatted: List[str] = []
        for message in messages[-limit:]:
            role = (message.get("role") or "user").lower()
            content = message.get("content") or ""
            if not content:
                continue
            formatted.append(f"{role}: {content}")
        return "\n".join(formatted)

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
            "what table", "what tables", "schema", "database structure", "what columns",
            "what fields", "list table", "list tables", "how many table", "how many tables",
            "show table", "show tables", "describe", "structure"
        ]
        return any(kw in user_lower for kw in schema_keywords)

    def _is_health_check(self, user_lower: str) -> bool:
        """Detect health/status queries."""
        health_keywords = [
            "health", "healthy", "status", "working", "running", "online", "available",
            "connected", "connection", "alive"
        ]
        return any(kw in user_lower for kw in health_keywords)

    def _empty_intent(self, user_input: str) -> dict:
        """Return empty intent for empty input."""
        return {
            "operation": "clarify",
            "primary_entities": [],
            "metrics": [],
            "filters": [],
            "time_window": None,
            "keywords_for_discovery": [],
            "raw_query": user_input or "",
            "confidence": 0.0,
            "needs_clarification": True,
            "clarification_question": "Ich habe keine Frage erhalten. Kannst du formulieren, was du wissen möchtest?",
            "ambiguity_reason": "empty_query"
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
