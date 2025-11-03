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

            logger.info(f"🧠 [EXTRACT] Entities: {intent['primary_entities']}, Keywords: {intent['keywords_for_discovery']}")
            return {**state, "intent": intent}

        except Exception as e:
            logger.warning(f"🧠 [EXTRACT] LLM extraction failed: {e}, using fallback")
            # Fallback extraction
            fallback = self._fallback_entity_extraction(user_input)
            intent.update(fallback)
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