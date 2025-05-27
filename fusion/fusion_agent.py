"""
Fusion Agent implementation.
"""
import json
import logging
from typing import Dict, List, Any, Optional

from crawling_agent.models.fusion_models import CrawlingResult, FusedAnswer
from crawling_agent.llm.provider import LLMProvider

# Configure logging
logger = logging.getLogger(__name__)


class FusionAgent:
    """
    Fusion Agent implementation.
    
    This agent fuses multiple crawling results into a single coherent answer.
    """
    
    def __init__(self, llm_provider: LLMProvider, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Fusion Agent.
        
        Args:
            llm_provider: LLM provider to use
            config: Optional configuration dictionary
        """
        self.llm_provider = llm_provider
        self.config = config or {}
        logger.info("Initialized Fusion Agent")
    
    async def fuse(self, results: List[CrawlingResult]) -> FusedAnswer:
        """
        Fuse multiple crawling results into a single answer.
        
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
        logger.info(f"Fusing {len(results)} results")
        
        # If there's only one result, just return it
        if len(results) == 1:
            result = results[0]
            return FusedAnswer(
                answer=result.nl_explanation,
                sources=[
                    {
                        "tool": result.source_tool,
                        "query": result.query_text
                    }
                ],
                confidence=1.0
            )
        
        # If there are multiple results, fuse them
        fused_answer = await self._generate_fused_answer(results)
        
        # Create sources list
        sources = [
            {
                "tool": result.source_tool,
                "query": result.query_text
            }
            for result in results
        ]
        
        return FusedAnswer(
            answer=fused_answer,
            sources=sources,
            confidence=1.0  # Placeholder confidence value
        )
    
    async def _generate_fused_answer(self, results: List[CrawlingResult]) -> str:
        """
        Generate a fused answer from multiple crawling results.
        
        Args:
            results: List of CrawlingResult objects
            
        Returns:
            Fused answer text
        """
        logger.info("Generating fused answer")
        
        # Create the prompt
        system_message = """You are an AI assistant that fuses multiple data source results into a single coherent answer.
Your task is to analyze the results from different data sources and provide a comprehensive answer that combines the insights from all sources.
Focus on creating a clear, concise response that directly addresses the user's original question.
"""
        
        # Format the results for the prompt
        formatted_results = ""
        for i, result in enumerate(results):
            formatted_results += f"Result {i+1} (from {result.source_tool}):\n"
            formatted_results += f"Query: {result.query_text}\n"
            formatted_results += f"Explanation: {result.nl_explanation}\n"
            
            # Add a sample of the raw results if available
            if result.raw_result:
                # Limit to 3 items to avoid token limits
                sample_data = result.raw_result[:3]
                formatted_results += "Sample data:\n"
                formatted_results += json.dumps(sample_data, indent=2) + "\n"
                
                if len(result.raw_result) > 3:
                    formatted_results += f"[Note: Showing 3 of {len(result.raw_result)} items]\n"
            
            formatted_results += "\n"
        
        # Create the prompt
        prompt = f"""
Please fuse the following results from different data sources into a single coherent answer:

{formatted_results}

Provide a comprehensive answer that combines the insights from all sources.
Focus on creating a clear, concise response that addresses the user's question.
"""
        
        # Generate the fused answer
        fused_answer = await self.llm_provider.generate(
            prompt=prompt,
            system_message=system_message,
            temperature=0.7
        )
        
        logger.info(f"Generated fused answer: {fused_answer[:100]}...")
        return fused_answer