"""
IntentParserAgent - Semantic Intent Analysis (Phase 9)

This agent replaces the naive `_simple_intent_parser()` function with semantic,
LLM-based intent understanding. Instead of naive regex keyword extraction, it:

1. Understands the user's semantic intent (query type, entities, metrics, filters)
2. Extracts clean keywords for discovery (NO noise from "which", "how", "many")
3. Returns a structured ParsedIntent with full typing
4. Confidence scoring to flag ambiguous queries

This FIXES the double-keyword-extraction problem where discovery was being called
per word instead of with clean semantic keywords.

BEFORE (Problem):
  User: "Which products have inventory below 100?"
  _simple_intent_parser returns: entities=["Which", "products", "have", "inventory"]
  discovery._extract_keywords re-extracts: adds more words
  Result: 5+ discovery calls, 943 candidates each → state pollution

AFTER (Fixed):
  User: "Which products have inventory below 100?"
  IntentParserAgent returns: ParsedIntent(
    primary_entities=["products"],
    metrics=["inventory"],
    filters=[{"field": "inventory", "operator": "<", "value": 100}],
    keywords_for_discovery=["products", "inventory", "stock"],  ← CLEAN
    operation="query",
    confidence=0.95
  )
  discovery uses ONLY keywords_for_discovery
  Result: 1 discovery call, ~3 candidates → clean state
"""

import logging
import json
import re
import asyncio
import concurrent.futures
from typing import Any, Dict, Optional, List, Literal

from langchain_openai import ChatOpenAI
from langgraph_integration.contracts.state import ParsedIntent

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
    Semantic intent parser using LLM to understand user queries deeply.
    
    Returns structured ParsedIntent (typed, not loose dict) with:
    - operation type (query/schema_query/health_check)
    - primary entities (2-3 clean nouns)
    - metrics (what to measure)
    - filters (structured conditions)
    - clean keywords for discovery (NO function words)
    - confidence score
    """

    def __init__(self, llm_model: str = "gpt-4o", llm_temp: float = 0.0):
        """
        Initialize IntentParserAgent.
        
        Args:
            llm_model: LLM model name (e.g., "gpt-4o")
            llm_temp: Temperature for LLM (0.0 = deterministic)
        """
        self.llm = ChatOpenAI(model=llm_model, temperature=llm_temp)

    async def parse(self, user_input: str) -> ParsedIntent:
        """
        Parse user input into structured intent.
        
        Args:
            user_input: The user's natural language query
            
        Returns:
            ParsedIntent: Structured, typed intent with clean keywords for discovery
        """
        if not user_input or not user_input.strip():
            logger.warning("Empty user input for intent parsing")
            return self._empty_intent(user_input)

        user_lower = user_input.lower()

        # Fast path: Detect special operations first
        if self._is_schema_query(user_lower):
            logger.info("🧠 Detected schema query")
            return {
                "operation": "schema_query",
                "primary_entities": [],
                "metrics": [],
                "filters": [],
                "time_window": None,
                "keywords_for_discovery": [],
                "raw_query": user_input,
                "confidence": 1.0
            }

        if self._is_health_check(user_lower):
            logger.info("🧠 Detected health check")
            return {
                "operation": "health_check",
                "primary_entities": [],
                "metrics": [],
                "filters": [],
                "time_window": None,
                "keywords_for_discovery": [],
                "raw_query": user_input,
                "confidence": 1.0
            }

        # Semantic parsing: Use LLM for data queries
        logger.info(f"🧠 Parsing intent with LLM: {user_input}")
        return await self._parse_with_llm(user_input)

    async def _parse_with_llm(self, user_input: str) -> ParsedIntent:
        """
        Use LLM to semantically parse the query.
        
        Args:
            user_input: The user's query
            
        Returns:
            ParsedIntent with semantic structure
        """
        prompt = f"""
Analyze this ERP query and extract structured intent. Return ONLY valid JSON (no markdown).

QUERY: "{user_input}"

Return JSON with these fields:
{{
  "primary_entities": ["noun1", "noun2"],  # 2-3 max, cleaned (NOT "Which", "how", "many")
  "metrics": ["count", "total", "average"],  # What to measure (or [] if not applicable)
  "filters": [{{"field": "column_name", "operator": "<|>|=|!=", "value": "...", "description": "..."}}],  # Structured conditions
  "time_window": {{"period": "last_30_days", "start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}} or null,  # If temporal
  "keywords_for_discovery": ["clean1", "clean2"],  # Keywords for table search (semantically relevant, no noise)
  "confidence": 0.95  # [0.0..1.0] how confident the parsing is correct
}}

EXAMPLES:
Query: "How many customers do we have?"
=> {{"primary_entities": ["customers"], "metrics": ["count"], "filters": [], "time_window": null, "keywords_for_discovery": ["customers"], "confidence": 1.0}}

Query: "Which products have inventory below 100?"
=> {{"primary_entities": ["products"], "metrics": ["inventory"], "filters": [{{"field": "inventory", "operator": "<", "value": 100, "description": "below 100"}}], "time_window": null, "keywords_for_discovery": ["products", "inventory", "stock"], "confidence": 0.95}}

Query: "Show me sales last quarter"
=> {{"primary_entities": ["sales"], "metrics": [], "filters": [], "time_window": {{"period": "last_quarter", "start": "2024-10-01", "end": "2024-12-31"}}, "keywords_for_discovery": ["sales", "orders"], "confidence": 0.85}}

Respond ONLY with the JSON object, no other text. Do NOT include markdown code blocks (no ```json```, just the raw JSON object).
"""
        try:
            # 🔧 CRITICAL FIX (Phase 9 Hotfix): Use ainvoke() instead of invoke()
            # invoke() is sync and blocks the event loop in async context
            # This was causing the intent parser to fail silently, breaking downstream agents
            response = await self.llm.ainvoke(prompt)
            response_text = response.content.strip()
            
            # 🔧 FIX: Strip markdown code blocks if LLM returns them despite instructions
            # Some LLMs return ```json ... ``` even when asked not to
            response_text = self._strip_markdown_blocks(response_text)
            
            # Try to parse JSON response
            try:
                parsed = json.loads(response_text)
                logger.info(f"✅ LLM parsed intent: {parsed}")
                
                # Build ParsedIntent, ensuring all required fields
                # 🔧 FIX: raw_query should be the original user_input, not the response_text!
                intent = {
                    "operation": "query",
                    "primary_entities": parsed.get("primary_entities", [])[:3],
                    "metrics": parsed.get("metrics", [])[:5],
                    "filters": parsed.get("filters", [])[:10],
                    "time_window": parsed.get("time_window"),
                    "keywords_for_discovery": parsed.get("keywords_for_discovery", [])[:10],
                    "raw_query": user_input,  # 🔧 FIX: Use user_input, not response_text
                    "confidence": float(parsed.get("confidence", 0.5))
                }
                return intent
                
            except json.JSONDecodeError as je:
                logger.warning(f"Failed to parse LLM JSON response: {je}")
                logger.debug(f"Raw response: {response_text[:500]}")
                # 🔧 FIX: Pass user_input to fallback, not response_text!
                # This prevents extracting keywords from the JSON structure itself
                return self._fallback_parse(user_input)
                
        except Exception as e:
            logger.error(f"LLM intent parsing failed: {e}")
            return self._fallback_parse(user_input)
    
    def _strip_markdown_blocks(self, text: str) -> str:
        """
        Strip markdown code blocks (```json ... ```) from LLM response.
        
        Some LLMs return markdown despite being asked not to.
        This extracts just the JSON content.
        
        Args:
            text: Raw response from LLM
            
        Returns:
            Cleaned text with markdown removed
        """
        # Check for markdown code blocks
        if "```" in text:
            # Try to extract JSON between code blocks
            # Match ```json ... ``` or just ``` ... ```
            pattern = r'```(?:json)?\s*(.*?)\s*```'
            matches = re.findall(pattern, text, re.DOTALL)
            if matches:
                # Return first matched JSON block
                return matches[0].strip()
        return text

    def _fallback_parse(self, user_input: str) -> ParsedIntent:
        """
        Fallback heuristic parsing when LLM fails.
        
        Still better than naive _simple_intent_parser because it:
        - Filters common words aggressively
        - Doesn't re-extract from user_input later
        - Returns structured ParsedIntent
        """
        logger.info(f"⚠️  Falling back to heuristic parsing for: {user_input}")
        
        # Aggressively filter noise words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "by", "of", "for", "to", "and", "or", "in", "on", "at",
            "how", "many", "show", "me", "please", "get", "list", "find", "search", "what",
            "have", "has", "had", "do", "does", "did", "with", "from", "as", "it",
            "we", "you", "they", "he", "she", "this", "that", "there",
            "where", "when", "why", "which", "who", "can", "could", "will", "would",
            "should", "must", "may", "might", "um", "uh", "like", "really", "very"
        }
        
        words = user_input.lower().split()
        keywords = []
        for word in words:
            word = word.strip("?,.!;:")
            if word not in stop_words and len(word) > 2:
                keywords.append(word)
        
        # Take first 2-3 keywords as entities, rest as discovery keywords
        entities = keywords[:2]
        all_keywords = list(dict.fromkeys(keywords))[:5]  # Dedupe, limit to 5
        
        return {
            "operation": "query",
            "primary_entities": entities,
            "metrics": [],
            "filters": [],
            "time_window": None,
            "keywords_for_discovery": all_keywords,
            "raw_query": user_input,
            "confidence": 0.6  # Lower confidence for fallback
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

    def _empty_intent(self, user_input: str) -> ParsedIntent:
        """Return empty intent for empty input."""
        return {
            "operation": "query",
            "primary_entities": [],
            "metrics": [],
            "filters": [],
            "time_window": None,
            "keywords_for_discovery": [],
            "raw_query": user_input or "",
            "confidence": 0.0
        }