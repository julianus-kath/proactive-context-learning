"""
Result processor for combining and processing results from different data sources.
"""
from typing import Dict, List, Any


class ResultProcessor:
    """
    Processes and combines results from different data sources.
    """
    
    def __init__(self):
        """Initialize the result processor."""
        pass
    
    def process_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process and combine results from different data sources.
        
        Args:
            results: List of results from different data sources
            
        Returns:
            Combined and processed results
        """
        # Initialize the combined results
        combined_results = []
        
        # Process each result
        for result in results:
            # Extract the data source type
            source_type = result.get("source_type", "unknown")
            
            # Extract the data
            data = result.get("data", [])
            
            # Add source type to each data item
            for item in data:
                item["source"] = source_type
                combined_results.append(item)
        
        return combined_results