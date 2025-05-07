"""
Fusion Agent implementation (stub).
"""
import logging
from typing import Dict, List, Any, Optional

from crawling_agent.models.fusion_models import CrawlingResult, FusedAnswer

# Configure logging
logger = logging.getLogger(__name__)


class FusionAgent:
    """
    Fusion Agent implementation (stub).
    
    This is a minimal, transparent passthrough implementation that will be
    replaced in a later sprint with a more sophisticated fusion agent.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Fusion Agent.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        logger.info("Initialized Fusion Agent (stub)")
    
    async def fuse(self, results: List[CrawlingResult]) -> FusedAnswer:
        """
        Fuse multiple crawling results into a single answer.
        
        For now, this is a simple passthrough that returns the first result.
        
        Args:
            results: List of CrawlingResult objects
            
        Returns:
            FusedAnswer object
        """
        if not results:
            logger.warning("No results to fuse")
            return FusedAnswer(
                answer="No results were found for your query.",
                sources=[],
                confidence=0.0
            )
        
        # Log the number of results
        logger.info(f"Fusing {len(results)} results (currently just passing through the first result)")
        
        # For now, just return the first result
        first_result = results[0]
        
        # Create a FusedAnswer
        fused_answer = FusedAnswer(
            answer=first_result.nl_explanation,
            sources=[
                {
                    "tool": first_result.source_tool,
                    "query": first_result.query_text
                }
            ],
            confidence=1.0  # Placeholder confidence value
        )
        
        return fused_answer