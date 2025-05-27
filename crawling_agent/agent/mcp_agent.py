"""
MCP-based Crawling Agent implementation.
"""
import os
import json
import time
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

from crawling_agent.llm.provider import LLMProvider
from crawling_agent.tools.base import Tool, ToolRegistry
from crawling_agent.models.fusion_models import CrawlingResult

# Configure logging
logger = logging.getLogger(__name__)


class MCPCrawlingAgent:
    """
    MCP-based Crawling Agent implementation.
    
    This agent uses the Model-Context Protocol (MCP) to:
    1. Parse the user's natural language question
    2. Choose appropriate tools
    3. Generate the precise queries
    4. Run the queries via the tools
    5. Return the raw result set plus a short natural language explanation
    """
    
    def __init__(self, llm_provider: LLMProvider, tool_registry: ToolRegistry):
        """
        Initialize the MCP Crawling Agent.
        
        Args:
            llm_provider: LLM provider to use
            tool_registry: Tool registry containing available tools
        """
        self.llm_provider = llm_provider
        self.tool_registry = tool_registry
        
        # Create logs directory if it doesn't exist
        try:
            os.makedirs("/app/logs", exist_ok=True)
            self.log_dir = "/app/logs"
        except Exception as e:
            logger.warning(f"Could not create logs directory at /app/logs: {str(e)}")
            logger.warning("Logging to console only")
            self.log_dir = None
        
        logger.info(f"Initialized MCP Crawling Agent with LLM provider: {llm_provider.get_provider_name()}")
        logger.info(f"Available tools: {[tool.get_name() for tool in tool_registry.get_all_tools()]}")
    
    async def run(self, nl_query: str) -> CrawlingResult:
        """
        Process a natural language query using the MCP.
        
        Args:
            nl_query: Natural language query from the user if self.log_dir else None
            
        Returns:
            CrawlingResult object containing the results
        """
        # Create a log file for this run if log_dir exists
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"{self.log_dir}/agent_{timestamp}.jsonl" if self.log_dir else None
        
        # Log the start of the run
        self._log_to_file(log_file, {
            "timestamp": time.time(),
            "event": "run_start",
            "query": nl_query
        })
        
        try:
            logger.info(f"Processing query: {nl_query}")
            
            # Step 1: Get database metadata
            metadata = await self._get_database_metadata()
            
            # Log the metadata
            self._log_to_file(log_file, {
                "timestamp": time.time(),
                "event": "metadata_retrieved",
                "metadata": metadata
            })
            
            # Step 2: Generate SQL query using MCP
            sql_query, reasoning = await self._generate_sql_query(nl_query, metadata)
            
            # Log the generated SQL query
            self._log_to_file(log_file, {
                "timestamp": time.time(),
                "event": "sql_query_generated",
                "sql_query": sql_query,
                "reasoning": reasoning
            })
            
            # Step 3: Execute the SQL query with retry logic
            sql_tool = self.tool_registry.get_tool("sql")
            if not sql_tool:
                raise ValueError("SQL tool not found in registry")
            
            # First attempt
            result = await sql_tool.run({"query": sql_query})
            
            # Log the query results
            self._log_to_file(log_file, {
                "timestamp": time.time(),
                "event": "query_executed",
                "result": result
            })
            
            # Check if the query returned any results
            if not result.get("raw_result") and "error" not in result.get("metadata", {}):
                logger.info("Query returned no results. Analyzing schema and sample data to improve query...")
                
                # Get sample data from the tables mentioned in the query
                table_names = self._extract_table_names(sql_query)
                sample_data = {}
                
                for table_name in table_names:
                    try:
                        # Get sample data for this table
                        sample_query = f"SELECT * FROM {table_name} LIMIT 5"
                        sample_result = await sql_tool.run({"query": sample_query})
                        
                        if sample_result.get("raw_result"):
                            sample_data[table_name] = sample_result.get("raw_result")
                            logger.info(f"Retrieved sample data from {table_name}")
                        else:
                            logger.warning(f"No sample data retrieved from {table_name}")
                    except Exception as e:
                        logger.warning(f"Error retrieving sample data from {table_name}: {str(e)}")
                
                # If we got sample data, use it to improve the query
                if sample_data:
                    # Generate an improved query based on the sample data
                    improved_query, improved_reasoning = await self._generate_improved_query(
                        nl_query, sql_query, metadata, sample_data
                    )
                    
                    logger.info(f"Generated improved query: {improved_query}")
                    
                    # Log the improved query
                    self._log_to_file(log_file, {
                        "timestamp": time.time(),
                        "event": "query_improved",
                        "original_query": sql_query,
                        "improved_query": improved_query,
                        "reasoning": improved_reasoning
                    })
                    
                    # Execute the improved query
                    result = await sql_tool.run({"query": improved_query})
                    
                    # Log the improved query results
                    self._log_to_file(log_file, {
                        "timestamp": time.time(),
                        "event": "improved_query_executed",
                        "result": result
                    })
            
            # Step 4: Generate a natural language explanation
            nl_explanation = await self._generate_explanation(nl_query, sql_query, result)
            
            # Log the explanation
            self._log_to_file(log_file, {
                "timestamp": time.time(),
                "event": "explanation_generated",
                "explanation": nl_explanation
            })
            
            # Create the CrawlingResult
            crawling_result = CrawlingResult(
                source_tool="sql",
                query_text=sql_query,
                raw_result=result["raw_result"],
                nl_explanation=nl_explanation
            )
            
            # Log the final result
            self._log_to_file(log_file, {
                "timestamp": time.time(),
                "event": "run_complete",
                "crawling_result": crawling_result.dict()
            })
            
            return crawling_result
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            
            # Log the error
            self._log_to_file(log_file, {
                "timestamp": time.time(),
                "event": "run_error",
                "error": str(e)
            })
            
            # Create an error result
            error_result = CrawlingResult(
                source_tool="error",
                query_text=nl_query,
                raw_result=[],
                nl_explanation=f"Error processing query: {str(e)}"
            )
            
            return error_result
    
    async def _get_database_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the database.
        
        Returns:
            Dictionary containing database metadata
        """
        sql_tool = self.tool_registry.get_tool("sql")
        if not sql_tool:
            raise ValueError("SQL tool not found in registry")
        
        try:
            # Use the get_metadata method if available
            if hasattr(sql_tool, "get_metadata"):
                return await sql_tool.get_metadata()
            
            # Otherwise, fall back to a direct API call
            logger.info("Fetching database metadata")
            await sql_tool._ensure_session()
            
            async with sql_tool._session.get(f"{sql_tool.base_url}/metadata") as response:
                response.raise_for_status()
                metadata = await response.json()
                logger.info(f"Retrieved metadata for {len(metadata.get('tables', []))} tables")
                return metadata
                
        except Exception as e:
            logger.error(f"Error getting database metadata: {str(e)}")
            raise
    
    async def _generate_sql_query(self, nl_query: str, metadata: Dict[str, Any]) -> tuple[str, str]:
        """
        Generate an SQL query from a natural language query using the MCP.
        
        Args:
            nl_query: Natural language query
            metadata: Database metadata
            
        Returns:
            Tuple of (SQL query, reasoning)
        """
        logger.info("Generating SQL query from natural language query")
        
        # Create the MCP prompt
        system_message = """You are an AI assistant that translates natural language questions into SQL queries.
Follow these guidelines:
1. Analyze the user's question carefully
2. Use ONLY the tables and columns provided in the metadata
3. Generate a precise SQL query that answers the question
4. Be case-sensitive with table and column names
5. Be case-sensitive with string values (e.g., 'Sales' is different from 'sales')
6. Explain your reasoning step by step
7. Return both the SQL query and your reasoning

DO NOT make assumptions about tables or columns that aren't in the metadata.
DO NOT use any mock data or fabricated results.
"""
        
        # Format the metadata for the prompt
        formatted_metadata = "Database Metadata:\n"
        for table in metadata.get("tables", []):
            formatted_metadata += f"Table: {table['name']}\n"
            formatted_metadata += "Columns:\n"
            for column in table.get("columns", []):
                formatted_metadata += f"  - {column['name']} ({column['type']})"
                if column.get("primary_key"):
                    formatted_metadata += " (PRIMARY KEY)"
                formatted_metadata += "\n"
            formatted_metadata += "\n"
        
        # Create the prompt
        prompt = f"""
User Question: {nl_query}

{formatted_metadata}

Please translate this question into a valid SQL query that can be executed against this database.
First, explain your reasoning step by step.
Then, provide the final SQL query.

IMPORTANT: Be case-sensitive with string values. For example, 'Sales' is different from 'sales'.
SQLite is case-sensitive for string comparisons by default.

Your response should be in this format:
REASONING:
[Your step-by-step reasoning here]

SQL:
[The final SQL query here]
"""
        
        # Generate the SQL query
        response = await self.llm_provider.generate(
            prompt=prompt,
            system_message=system_message,
            temperature=0.2
        )
        
        # Extract the SQL query and reasoning from the response
        reasoning = ""
        sql_query = ""
        
        if "REASONING:" in response and "SQL:" in response:
            parts = response.split("SQL:")
            reasoning_part = parts[0].strip()
            sql_part = parts[1].strip()
            
            reasoning = reasoning_part.replace("REASONING:", "").strip()
            sql_query = sql_part
        else:
            # Fallback if the response doesn't follow the expected format
            logger.warning("Response doesn't follow the expected format, attempting to extract SQL query")
            
            # Look for SQL code block
            if "```sql" in response and "```" in response.split("```sql")[1]:
                sql_query = response.split("```sql")[1].split("```")[0].strip()
            elif "```" in response and "```" in response.split("```")[1]:
                sql_query = response.split("```")[1].strip()
            else:
                # Just use the whole response as the SQL query
                sql_query = response.strip()
            
            reasoning = "Could not extract reasoning from response."
        
        # Clean up the SQL query by removing any markdown formatting
        if sql_query.startswith("```sql"):
            sql_query = sql_query.replace("```sql", "", 1)
            if sql_query.endswith("```"):
                sql_query = sql_query[:-3]
        elif sql_query.startswith("```"):
            sql_query = sql_query.replace("```", "", 1)
            if sql_query.endswith("```"):
                sql_query = sql_query[:-3]
        
        # Remove any leading/trailing whitespace
        sql_query = sql_query.strip()
        
        logger.info(f"Generated SQL query: {sql_query}")
        return sql_query, reasoning
    
    async def _generate_explanation(self, nl_query: str, sql_query: str, result: Dict[str, Any]) -> str:
        """
        Generate a natural language explanation of the query results.
        
        Args:
            nl_query: Original natural language query
            sql_query: SQL query that was executed
            result: Query results
            
        Returns:
            Natural language explanation
        """
        logger.info("Generating explanation for query results")
        
        # Create the MCP prompt
        system_message = """You are an AI assistant that explains SQL query results in natural language.
Your task is to provide a clear, concise explanation of the query results that directly answers the user's original question.
Focus on the key insights from the data and present them in a way that's easy to understand.
"""
        
        # Format the result data for the prompt
        result_data = result.get("raw_result", [])
        if not result_data:
            return "No results were found for your query."
        
        # Limit the number of results to include in the prompt to avoid token limits
        max_results = 10
        truncated = len(result_data) > max_results
        
        formatted_results = json.dumps(result_data[:max_results], indent=2)
        if truncated:
            formatted_results += f"\n\n[Note: Showing {max_results} of {len(result_data)} results]"
        
        # Create the prompt
        prompt = f"""
Original Question: {nl_query}

SQL Query: {sql_query}

Query Results:
{formatted_results}

Please provide a clear, concise explanation of these results that directly answers the original question.
Focus on the key insights and present them in a way that's easy to understand.
"""
        
        # Generate the explanation
        explanation = await self.llm_provider.generate(
            prompt=prompt,
            system_message=system_message,
            temperature=0.7
        )
        
        logger.info(f"Generated explanation: {explanation[:100]}...")
        return explanation
    
    def _extract_table_names(self, sql_query: str) -> List[str]:
        """
        Extract table names from an SQL query.
        
        Args:
            sql_query: SQL query to extract table names from
            
        Returns:
            List of table names
        """
        # Simple regex-based extraction - this is a basic implementation
        # A more robust implementation would use a proper SQL parser
        import re
        
        # Convert to lowercase for case-insensitive matching
        query_lower = sql_query.lower()
        
        # Look for FROM and JOIN clauses
        from_tables = re.findall(r'from\s+([a-zA-Z0-9_]+)', query_lower)
        join_tables = re.findall(r'join\s+([a-zA-Z0-9_]+)', query_lower)
        
        # Combine and remove duplicates
        all_tables = list(set(from_tables + join_tables))
        
        # Convert back to the original case using the original query
        result = []
        for table_lower in all_tables:
            # Find the table name with original capitalization
            # This is a simple approach and might not work for all cases
            pattern = re.compile(r'(?i)(?:from|join)\s+(' + table_lower + r')\b')
            matches = pattern.findall(sql_query)
            
            if matches:
                result.append(matches[0])
            else:
                # Fallback to the lowercase version if we can't find the original
                result.append(table_lower)
        
        logger.info(f"Extracted table names from query: {result}")
        return result
    
    async def _generate_improved_query(
        self, 
        nl_query: str, 
        original_query: str, 
        metadata: Dict[str, Any],
        sample_data: Dict[str, List[Dict[str, Any]]]
    ) -> tuple[str, str]:
        """
        Generate an improved SQL query based on sample data.
        
        Args:
            nl_query: Original natural language query
            original_query: Original SQL query that returned no results
            metadata: Database metadata
            sample_data: Sample data from tables mentioned in the query
            
        Returns:
            Tuple of (improved SQL query, reasoning)
        """
        logger.info("Generating improved SQL query based on sample data")
        
        # Create the MCP prompt
        system_message = """You are an AI assistant that helps improve SQL queries that returned no results.
Your task is to analyze the original query, the database schema, and sample data to identify why the query returned no results.
Common issues include:
1. Case sensitivity in string comparisons (e.g., 'sales' vs 'Sales')
2. Typos in column or table names
3. Incorrect join conditions
4. Overly restrictive WHERE clauses
5. Data format issues (e.g., date formats)

Provide a detailed explanation of the issue and an improved query that will return results.
"""
        
        # Format the metadata for the prompt
        formatted_metadata = "Database Metadata:\n"
        for table in metadata.get("tables", []):
            formatted_metadata += f"Table: {table['name']}\n"
            formatted_metadata += "Columns:\n"
            for column in table.get("columns", []):
                formatted_metadata += f"  - {column['name']} ({column['type']})"
                if column.get("primary_key"):
                    formatted_metadata += " (PRIMARY KEY)"
                formatted_metadata += "\n"
            formatted_metadata += "\n"
        
        # Format the sample data for the prompt
        formatted_sample_data = "Sample Data:\n"
        for table_name, data in sample_data.items():
            formatted_sample_data += f"Table: {table_name}\n"
            if data:
                # Get column names from the first row
                columns = list(data[0].keys())
                formatted_sample_data += "Columns: " + ", ".join(columns) + "\n"
                
                # Add a few sample rows
                formatted_sample_data += "Rows:\n"
                for i, row in enumerate(data[:3]):  # Limit to 3 rows to avoid token limits
                    formatted_sample_data += f"  Row {i+1}: {json.dumps(row)}\n"
            else:
                formatted_sample_data += "No data available\n"
            formatted_sample_data += "\n"
        
        # Create the prompt
        prompt = f"""
Original Question: {nl_query}

Original SQL Query (returned no results):
{original_query}

{formatted_metadata}

{formatted_sample_data}

Please analyze why the original query returned no results and provide an improved query.
First, explain the issue with the original query.
Then, provide an improved SQL query that will return results.

Your response should be in this format:
REASONING:
[Your analysis of why the original query returned no results]

IMPROVED SQL:
[The improved SQL query]
"""
        
        # Generate the improved query
        response = await self.llm_provider.generate(
            prompt=prompt,
            system_message=system_message,
            temperature=0.2
        )
        
        # Extract the improved query and reasoning from the response
        reasoning = ""
        improved_query = ""
        
        if "REASONING:" in response and "IMPROVED SQL:" in response:
            parts = response.split("IMPROVED SQL:")
            reasoning_part = parts[0].strip()
            sql_part = parts[1].strip()
            
            reasoning = reasoning_part.replace("REASONING:", "").strip()
            improved_query = sql_part
        else:
            # Fallback if the response doesn't follow the expected format
            logger.warning("Response doesn't follow the expected format, attempting to extract improved SQL query")
            
            # Look for SQL code block
            if "```sql" in response and "```" in response.split("```sql")[1]:
                improved_query = response.split("```sql")[1].split("```")[0].strip()
            elif "```" in response and "```" in response.split("```")[1]:
                improved_query = response.split("```")[1].strip()
            else:
                # Just use the whole response as the SQL query
                improved_query = response.strip()
            
            reasoning = "Could not extract reasoning from response."
        
        # Clean up the improved query by removing any markdown formatting
        if improved_query.startswith("```sql"):
            improved_query = improved_query.replace("```sql", "", 1)
            if improved_query.endswith("```"):
                improved_query = improved_query[:-3]
        elif improved_query.startswith("```"):
            improved_query = improved_query.replace("```", "", 1)
            if improved_query.endswith("```"):
                improved_query = improved_query[:-3]
        
        # Remove any leading/trailing whitespace
        improved_query = improved_query.strip()
        
        logger.info(f"Generated improved SQL query: {improved_query}")
        return improved_query, reasoning
    
    def _log_to_file(self, log_file: str, data: Dict[str, Any]) -> None:
        """
        Log data to a JSONL file.
        
        Args:
            log_file: Path to the log file
            data: Data to log
        """
        # If log_file is None or log_dir is None, just log to console
        if log_file is None or self.log_dir is None:
            logger.info(f"Log entry: {json.dumps(data)}")
            return
            
        try:
            with open(log_file, "a") as f:
                f.write(json.dumps(data) + "\n")
        except Exception as e:
            logger.error(f"Error logging to file: {str(e)}")
            logger.info(f"Log entry: {json.dumps(data)}")