"""
Test IntentParserAgent (Phase 9) - Semantic Intent Parsing

Verifies that:
1. Intent parsing produces structured ParsedIntent (not loose dict)
2. Keywords are clean (no function words like "which", "how", "many")
3. Double-extraction problem is fixed
4. Confidence scoring works
5. Special operations detected correctly
"""

import json
import os
import pytest
from langgraph_integration.agents.intent_parser.agent import IntentParserAgent
from langgraph_integration.contracts.state import ParsedIntent

# Provide a dummy API key so ChatOpenAI initialization does not fail during tests
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")


class DummyLLMResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class StubLLM:
    def __init__(self, responses, assertions=None):
        self._responses = iter(responses)
        self._assertions = assertions or []
        self.prompt_log = []

    async def ainvoke(self, prompt: str):
        call_index = len(self.prompt_log)
        self.prompt_log.append(prompt)
        if call_index < len(self._assertions) and self._assertions[call_index] is not None:
            self._assertions[call_index](prompt)
        try:
            payload = next(self._responses)
        except StopIteration as exc:  # pragma: no cover - sanity guard
            raise AssertionError("LLM called more times than expected") from exc
        return DummyLLMResponse(payload)


def configure_llm_mock(parser: IntentParserAgent, responses, prompt_assertions=None):
    """Attach an AsyncMock to parser.llm that yields provided responses."""
    stub = StubLLM(responses, prompt_assertions or [])
    parser.llm = stub  # type: ignore[attr-defined]
    return stub.prompt_log


def build_responses(
    *,
    key_topics,
    primary_entities,
    keywords,
    metrics=None,
    filters=None,
    confidence=0.95,
    operation="query",
):
    analysis = json.dumps({
        "query_type": "data_query",
        "broad_category": "analysis",
        "key_topics": key_topics,
        "intent_indicators": ["lookup"],
        "complexity": "simple",
        "confidence": confidence,
    })
    classification = json.dumps({
        "operation": operation,
        "confidence": confidence,
        "reasoning": "classified via mock",
        "alternative_operations": [],
    })
    extraction = json.dumps({
        "primary_entities": primary_entities,
        "secondary_entities": [],
        "metrics": metrics or [],
        "filters": filters or [],
        "time_window": None,
        "keywords_for_discovery": keywords,
        "confidence": confidence,
    })
    return [analysis, classification, extraction]


class TestIntentParserAgent:
    """Test suite for IntentParserAgent."""

    @pytest.fixture
    def parser(self):
        """Create IntentParserAgent instance."""
        return IntentParserAgent(llm_model="gpt-4o", llm_temp=0.0)

    @pytest.mark.asyncio
    async def test_parse_data_query(self, parser):
        """Test parsing a basic data query."""
        user_input = "Which products have inventory below 100?"
 
        responses = build_responses(
            key_topics=["products"],
            primary_entities=["products"],
            keywords=["products", "inventory"],
            filters=[{"field": "inventory", "operator": "<", "value": "100", "description": "below 100"}],
        )
        configure_llm_mock(parser, responses)

        intent = await parser.parse(user_input)
 
        # Verify structure
        assert isinstance(intent, dict)
        assert "operation" in intent
        assert "primary_entities" in intent
        assert "keywords_for_discovery" in intent
        assert "confidence" in intent
        
        # Verify operation
        assert intent["operation"] == "query"
        
        # Verify no noise in keywords
        keywords_lower = [k.lower() for k in intent["keywords_for_discovery"]]
        assert "which" not in keywords_lower, "Function word 'which' should not be in keywords"
        assert "how" not in keywords_lower, "Function word 'how' should not be in keywords"
        assert "have" not in keywords_lower, "Function word 'have' should not be in keywords"
        
        # Verify semantic content is present
        assert any("product" in k.lower() or "inventory" in k.lower() or "stock" in k.lower() 
                  for k in keywords_lower), "Should have semantic keywords"
        
        # Verify confidence is reasonable
        assert 0.0 <= intent["confidence"] <= 1.0
        assert intent["confidence"] > 0.5, "Confidence should be decent for clear query"

    @pytest.mark.asyncio
    async def test_parse_schema_query(self, parser):
        """Test detection of schema query."""
        user_input = "What tables do we have?"
        
        responses = build_responses(
            key_topics=["tables"],
            primary_entities=[],
            keywords=[],
            metrics=[],
            operation="schema_query",
        )
        configure_llm_mock(parser, responses)

        intent = await parser.parse(user_input)
        
        assert intent["operation"] == "schema_query"
        assert intent["keywords_for_discovery"] == []
        assert intent["primary_entities"] == []

    @pytest.mark.asyncio
    async def test_parse_health_check(self, parser):
        """Test detection of health check query."""
        user_input = "Is the database healthy?"
        
        responses = build_responses(
            key_topics=["health"],
            primary_entities=[],
            keywords=[],
            metrics=[],
            operation="health_check",
        )
        configure_llm_mock(parser, responses)

        intent = await parser.parse(user_input)
        
        assert intent["operation"] == "health_check"
        assert intent["keywords_for_discovery"] == []

    @pytest.mark.asyncio
    async def test_parse_complex_filter(self, parser):
        """Test parsing query with filter conditions."""
        user_input = "Show me sales in the last month with revenue above $10,000"
 
        responses = build_responses(
            key_topics=["sales"],
            primary_entities=["sales"],
            keywords=["sales", "revenue", "last month"],
            metrics=["sum"],
            filters=[{"field": "revenue", "operator": ">", "value": "10000", "description": "above 10k"}],
        )
        configure_llm_mock(parser, responses)

        intent = await parser.parse(user_input)
 
        assert intent["operation"] == "query"
        # Should have semantic entities and filters
        assert len(intent["primary_entities"]) > 0
        assert len(intent["keywords_for_discovery"]) > 0
        # Verify no noise keywords
        keywords_lower = [k.lower() for k in intent["keywords_for_discovery"]]
        assert "above" not in keywords_lower
        assert "month" in keywords_lower or "sales" in keywords_lower

    @pytest.mark.asyncio
    async def test_empty_input(self, parser):
        """Test handling of empty input."""
        intent = await parser.parse("")
        
        assert isinstance(intent, dict)
        assert intent["operation"] == "clarify"
        assert intent["needs_clarification"] is True
        assert intent["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_structured_output_type(self, parser):
        """Test that output has all ParsedIntent fields."""
        user_input = "Count customers by region"
 
        responses = build_responses(
            key_topics=["customers"],
            primary_entities=["customers"],
            keywords=["customers", "region"],
            metrics=["count"],
        )
        configure_llm_mock(parser, responses)

        intent = await parser.parse(user_input)
 
        # Check all required fields exist
        required_fields = [
            "operation",
            "primary_entities",
            "metrics",
            "filters",
            "time_window",
            "keywords_for_discovery",
            "raw_query",
            "confidence"
        ]
        
        for field in required_fields:
            assert field in intent, f"Missing required field: {field}"
            assert intent[field] is not None or field in ["time_window"]

    @pytest.mark.asyncio
    async def test_keywords_are_cleaned(self, parser):
        """Test that keywords don't include function words."""
        test_cases = [
            ("Which customers do we have?", ["customers"]),
            ("How many products are below 100?", ["products"]),
            ("Show me sales with revenue above 10000", ["sales", "revenue"]),
        ]
        
        for user_input, expected_core_words in test_cases:
            responses = build_responses(
                key_topics=expected_core_words,
                primary_entities=expected_core_words,
                keywords=expected_core_words,
            )
            configure_llm_mock(parser, responses)

            intent = await parser.parse(user_input)
            keywords_lower = [k.lower() for k in intent["keywords_for_discovery"]]
            
            # Check no function words
            function_words = {"which", "how", "many", "do", "are", "show", "me", "with", "above"}
            for fw in function_words:
                assert fw not in keywords_lower, f"Function word '{fw}' in keywords for: {user_input}"

    @pytest.mark.asyncio
    async def test_llm_failure_triggers_clarification(self, parser):
        """If the LLM cannot be reached, the agent should request clarification."""

        class FailingLLM:
            async def ainvoke(self, prompt: str):  # pragma: no cover - simple stub
                raise RuntimeError("LLM unavailable")

        parser.llm = FailingLLM()

        intent = await parser.parse("Wie viele Kunden haben wir?")

        assert intent["needs_clarification"] is True
        assert intent["operation"] == "clarify"
        assert intent.get("clarification_question")

    @pytest.mark.asyncio
    async def test_parse_german_count_query(self, parser):
        responses = build_responses(
            key_topics=["kunden"],
            primary_entities=["kunden"],
            keywords=["kunden"],
            metrics=["count"],
        )
        configure_llm_mock(parser, responses)

        intent = await parser.parse("Wie viele Kunden habe ich?")

        assert intent["operation"] == "query"
        assert "kunden" in [e.lower() for e in intent["primary_entities"]]
        assert "count" in [m.lower() for m in intent["metrics"]]

    @pytest.mark.asyncio
    async def test_follow_up_inherits_context(self, parser):
        responses = build_responses(
            key_topics=["kunden"],
            primary_entities=["kunden"],
            keywords=["kunden", "namen"],
        )

        def assert_history(prompt: str):
            assert "Wie viele Kunden habe ich?" in prompt

        configure_llm_mock(parser, responses, prompt_assertions=[assert_history, assert_history, assert_history])

        messages = [
            {"role": "user", "content": "Wie viele Kunden habe ich?"},
            {"role": "assistant", "content": "Sie haben 120 Kunden."},
        ]

        intent = await parser.parse("Und deren Namen?", messages=messages)

        assert intent["operation"] == "query"
        assert "kunden" in [e.lower() for e in intent["primary_entities"]]
        assert "namen" in [k.lower() for k in intent["keywords_for_discovery"]]


class TestKeywordExtractionPhase9:
    """Test the Phase 9 fix: no more double extraction."""

    @pytest.fixture
    def parser(self):
        """Create IntentParserAgent instance."""
        return IntentParserAgent(llm_model="gpt-4o", llm_temp=0.0)

    @pytest.mark.asyncio
    async def test_single_extraction_point(self, parser):
        """
        Verify that intent parsing is the SINGLE extraction point.
        
        Before Phase 9: Extraction happened in TWO places
        - Orchestrator._simple_intent_parser
        - DiscoveryAgent._extract_keywords
        
        After Phase 9: ONLY in IntentParserAgent
        """
        user_input = "Which products have inventory below 100?"
 
        responses = build_responses(
            key_topics=["products"],
            primary_entities=["products"],
            keywords=["products", "inventory"],
        )
        configure_llm_mock(parser, responses)

        intent = await parser.parse(user_input)
        keywords = intent["keywords_for_discovery"]
        
        keywords_lower = [k.lower() for k in keywords]
        assert "products" in keywords_lower
        # Should not have common words
        common_words = {"which", "how", "many", "show", "have", "do", "get"}
        assert not any(cw in keywords_lower for cw in common_words)

    @pytest.mark.asyncio
    async def test_discovery_can_use_keywords_as_is(self, parser):
        """
        Verify keywords from intent can be used directly without re-extraction.
        
        This is the key Phase 9 contract: discovery uses intent.keywords_for_discovery
        as-is, without calling _extract_keywords again.
        """
        user_input = "Show me top products by revenue"
 
        responses = build_responses(
            key_topics=["products"],
            primary_entities=["products"],
            keywords=["products", "revenue"],
            metrics=["sum"],
        )
        configure_llm_mock(parser, responses)

        intent = await parser.parse(user_input)
        keywords = intent["keywords_for_discovery"]
        
        # These keywords should be ready for discovery search_tables calls
        assert isinstance(keywords, list)
        assert all(isinstance(k, str) for k in keywords)
        assert all(len(k) > 1 for k in keywords)
        assert len(keywords) > 0


class TestIntentParserLocalization:
    """Localization-specific behaviour for IntentParserAgent."""

    @pytest.fixture
    def parser(self):
        return IntentParserAgent(llm_model="gpt-4o", llm_temp=0.0)

    def test_expand_keywords_includes_german_synonyms(self, parser):
        expanded = parser._expand_keywords_with_translations(["customers"], ["customers"])
        lowered = [kw.lower() for kw in expanded]
        assert "kunde" in lowered
        assert "kunden" in lowered

    def test_derive_action_hints_german_count(self, parser):
        user_input = "Wie viele Kunden hatten wir letztes Jahr?"
        intent = {"primary_entities": ["customers"], "metrics": []}
        hints = parser._derive_action_hints(user_input, intent)
        assert hints["required_action"] == "count"

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])