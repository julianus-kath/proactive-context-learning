"""
Models for the fusion agent.
"""
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class CrawlingResult(BaseModel):
    """
    Model for crawling results.
    """
    source_tool: str = Field(..., description="The tool that produced the result")
    query_text: str = Field(..., description="The query text that was executed")
    raw_result: List[Dict[str, Any]] = Field(..., description="The raw result data")
    nl_explanation: str = Field(..., description="Natural language explanation of the result")


class FusedAnswer(BaseModel):
    """
    Model for fused answers.
    """
    answer: str = Field(..., description="The fused answer text")
    sources: List[Dict[str, Any]] = Field(..., description="Sources used to produce the answer")
    confidence: float = Field(..., description="Confidence in the answer (0.0 to 1.0)")