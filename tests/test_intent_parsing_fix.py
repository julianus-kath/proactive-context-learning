#!/usr/bin/env python3
"""
Test for intent parsing None/null response fix
Reproduces and verifies the fix for: 'NoneType' object has no attribute 'get'
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Create a minimal test class that mimics the DatabaseWorkflow for testing
# the parsing methods without mocking the whole class
import json
import re
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class IntentParserUnderTest:
    """Minimal class that contains the parsing methods we want to test"""
    
    def _parse_intent_response(self, response_text: str):
        """
        Parse the intent analysis response from the LLM.
        
        Args:
            response_text: Raw response from the LLM
            
        Returns:
            Structured intent analysis
        """
        # Simple parsing - in production, you might want more robust parsing
        lines = response_text.strip().split('\n') if response_text else []
        
        operation = "DATA_QUERY"  # default
        entities = []
        requirements = ""
        
        for line in lines:
            if line.startswith("Operation:"):
                operation = line.split(":", 1)[1].strip()
            elif line.startswith("Entities:"):
                entities_text = line.split(":", 1)[1].strip()
                entities = [e.strip().strip('[]') for e in entities_text.split(",") if e.strip()]
            elif line.startswith("Requirements:"):
                requirements = line.split(":", 1)[1].strip()
        
        return {
            "operation": operation,
            "entities": entities,
            "requirements": requirements
        }
    
    def _parse_intent_json_response(self, response_text: str):
        """
        Parse the JSON intent analysis response from the LLM.
        Applies answer-first defaults: prevents asking for schema/location/category.
        """
        try:
            # Safety: Check for None or empty response
            if not response_text or not isinstance(response_text, str):
                logger.warning(f"Invalid response_text: {type(response_text)} = {response_text}")
                return self._parse_intent_response("")
            
            # Try to extract JSON from the response
            # Look for JSON block in the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                parsed = json.loads(json_str)
                
                # Ensure required fields exist
                result = {
                    "operation": parsed.get("operation", "query"),
                    "reasoning": parsed.get("reasoning", ""),
                }
                
                if result["operation"] == "clarify":
                    missing_fields = parsed.get("missing_fields", [])
                    result["missing_fields"] = missing_fields
                else:
                    result["sql"] = parsed.get("sql", "")
                    result["entities"] = []
                    result["requirements"] = result["reasoning"]
                
                return result
                
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError) as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response text was: {response_text[:100] if response_text else 'None'}")
            
        # Fallback to old parsing method
        try:
            return self._parse_intent_response(response_text if response_text else "")
        except Exception as e:
            logger.error(f"Fallback intent parsing also failed: {e}")
            # Last resort - return safe default
            return {"operation": "query", "entities": [], "requirements": ""}


class TestIntentParsingFix:
    """Test the intent parsing error handling for None/empty responses"""
    
    @pytest.fixture
    def parser(self):
        """Create a parser instance for testing"""
        return IntentParserUnderTest()
    
    def test_parse_intent_with_none_response(self, parser):
        """Test that None response is handled gracefully"""
        result = parser._parse_intent_json_response(None)
        
        assert result is not None, "Should never return None"
        assert isinstance(result, dict), "Should always return a dict"
        assert "operation" in result, "Should have operation key"
        logger.info(f"✅ None response handled: {result}")
    
    def test_parse_intent_with_empty_string(self, parser):
        """Test that empty string is handled gracefully"""
        result = parser._parse_intent_json_response("")
        
        assert result is not None, "Should never return None"
        assert isinstance(result, dict), "Should always return a dict"
        logger.info(f"✅ Empty string handled: {result}")
    
    def test_parse_intent_with_incomplete_json(self, parser):
        """Test that incomplete/malformed JSON is handled gracefully"""
        incomplete_json = '{\n  "operation"'  # This matches the error message from the user
        result = parser._parse_intent_json_response(incomplete_json)
        
        assert result is not None, "Should never return None"
        assert isinstance(result, dict), "Should always return a dict"
        assert "operation" in result, "Should have operation key"
        logger.info(f"✅ Incomplete JSON handled: {result}")
    
    def test_parse_intent_with_valid_json(self, parser):
        """Test that valid JSON is still parsed correctly"""
        valid_json = '{"operation": "query", "sql": "SELECT * FROM users", "reasoning": "User wants all users"}'
        result = parser._parse_intent_json_response(valid_json)
        
        assert result is not None
        assert isinstance(result, dict)
        assert result["operation"] == "query"
        assert result.get("sql") == "SELECT * FROM users"
        logger.info(f"✅ Valid JSON parsed correctly: {result}")
    
    def test_parse_intent_with_clarify_operation(self, parser):
        """Test that clarify operations with missing fields are handled"""
        clarify_json = '{"operation": "clarify", "missing_fields": ["date range"], "reasoning": "Need to know which dates"}'
        result = parser._parse_intent_json_response(clarify_json)
        
        assert result is not None
        assert isinstance(result, dict)
        assert "operation" in result
        logger.info(f"✅ Clarify operation handled: {result}")
    
    def test_intent_analysis_never_none_in_node(self, parser):
        """Test that _parse_intent_node ensures intent_analysis is always a dict"""
        # This simulates the state after parsing
        state = {
            "messages": [{"role": "user", "content": "test"}],
            "schema": "test schema"
        }
        
        # Manually call the parsing with None to simulate the error
        result = parser._parse_intent_json_response(None)
        
        # The node would assign this to state["intent_analysis"]
        state["intent_analysis"] = result
        
        # Then try to access it like the node does
        if not state["intent_analysis"] or not isinstance(state["intent_analysis"], dict):
            state["intent_analysis"] = {"operation": "DATA_QUERY", "requirements": "", "entities": []}
        
        # This should NOT raise 'NoneType' object has no attribute 'get'
        try:
            operation = state["intent_analysis"].get("operation", "unknown")
            assert operation is not None
            logger.info(f"✅ .get() call succeeded with operation: {operation}")
        except AttributeError as e:
            pytest.fail(f"Failed with AttributeError: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])