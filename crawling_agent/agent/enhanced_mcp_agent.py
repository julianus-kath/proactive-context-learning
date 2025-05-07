"""
Enhanced MCP Crawling Agent implementation.
"""
import os
import json
import time
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple

from crawling_agent.llm.provider import LLMProvider
from crawling_agent.tools.base import ToolRegistry
from crawling_agent.models.fusion_models import CrawlingResult

# Configure logging
logger = logging.getLogger(__name__)


class EnhancedMCPCrawlingAgent:
    """
    Enhanced Multi-Channel Processing (MCP) Crawling Agent.
    
    This agent can determine which data sources to query based on the user's question
    and execute queries against multiple data sources.
    """
    
    def __init__(self, llm_provider: LLMProvider, tool_registry: ToolRegistry):
        """
        Initialize the Enhanced MCP Crawling Agent.
        
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
        
        logger.info(f"Initialized Enhanced MCP Crawling Agent with LLM provider: {llm_provider.get_provider_name()}")
        logger.info(f"Available tools: {[tool.get_name() for tool in tool_registry.get_all_tools()]}")
    
    async def run(self, nl_query: str) -> List[CrawlingResult]:
        """
        Process a natural language query using the MCP.
        
        Args:
            nl_query: Natural language query from the user
            
        Returns:
            List of CrawlingResult objects
        """
        logger.info(f"Processing query: {nl_query}")
        
        # Create a log file for this query
        log_file = f"{self.log_dir}/query_{int(time.time())}.jsonl" if self.log_dir else None
        
        # Log the query
        self._log_to_file(log_file, {
            "timestamp": time.time(),
            "event": "query_received",
            "query": nl_query
        })
        
        try:
            # Step 1: Determine which data sources to query
            data_sources = await self._determine_data_sources(nl_query)
            
            # Log the selected data sources
            self._log_to_file(log_file, {
                "timestamp": time.time(),
                "event": "data_sources_determined",
                "data_sources": data_sources
            })
            
            # Step 2: Query each data source
            results = []
            
            # Query SQL database if selected
            if "sql" in data_sources:
                sql_result = await self._query_sql_database(nl_query, log_file)
                results.append(sql_result)
            
            # Query document store if selected
            if "doc" in data_sources:
                doc_result = await self._query_document_store(nl_query, log_file)
                results.append(doc_result)
            
            # Log the final results
            self._log_to_file(log_file, {
                "timestamp": time.time(),
                "event": "query_completed",
                "results": [result.dict() for result in results]
            })
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            
            # Log the error
            self._log_to_file(log_file, {
                "timestamp": time.time(),
                "event": "query_error",
                "error": str(e)
            })
            
            # Return an error result
            return [CrawlingResult(
                source_tool="error",
                query_text=nl_query,
                raw_result=[],
                nl_explanation=f"Error processing query: {str(e)}"
            )]
    
    async def _determine_data_sources(self, nl_query: str) -> List[str]:
        """
        Determine which data sources to query based on the natural language query.
        
        Args:
            nl_query: Natural language query from the user
            
        Returns:
            List of data source names to query
        """
        logger.info("Determining data sources for query")
        
        # Create the MCP prompt
        system_message = """You are an AI assistant that determines which data sources to query based on a natural language question.
Follow these guidelines:
1. Analyze the user's question carefully
2. Determine which data sources would contain the information needed to answer the question
3. Return a list of data source names

Available data sources:
- sql: Relational database with structured data about products, customers, orders, employees, etc.
- doc: Document store with unstructured or semi-structured data like product descriptions, customer reviews, support tickets, etc.

Return ONLY the data source names separated by commas, without any explanation or additional text.
"""
        
        # Create the prompt
        prompt = f"""
User Question: {nl_query}

Which data sources should be queried to answer this question?
If you're uncertain, include all potentially relevant data sources.

Your response should be ONLY the data source names separated by commas, without any explanation or additional text.
For example: "sql,doc" or "sql" or "doc"
"""
        
        # Generate the data sources
        response = await self.llm_provider.generate(
            prompt=prompt,
            system_message=system_message,
            temperature=0.2
        )
        
        # Parse the response
        data_sources = [source.strip().lower() for source in response.split(",")]
        
        # Validate the data sources
        valid_sources = []
        for source in data_sources:
            if source in ["sql", "doc"]:
                valid_sources.append(source)
            else:
                logger.warning(f"Invalid data source: {source}")
        
        # If no valid sources were found, default to all sources
        if not valid_sources:
            logger.warning("No valid data sources found, defaulting to all sources")
            valid_sources = ["sql", "doc"]
        
        logger.info(f"Selected data sources: {valid_sources}")
        return valid_sources
    
    async def _query_sql_database(self, nl_query: str, log_file: Optional[str]) -> CrawlingResult:
        """
        Query the SQL database.
        
        Args:
            nl_query: Natural language query from the user
            log_file: Path to the log file
            
        Returns:
            CrawlingResult object
        """
        logger.info("Querying SQL database")
        
        # Get the SQL tool
        sql_tool = self.tool_registry.get_tool("sql")
        if not sql_tool:
            raise ValueError("SQL tool not found in registry")
        
        # Get metadata from the SQL tool
        metadata = await sql_tool.get_metadata()
        
        # Log the metadata
        self._log_to_file(log_file, {
            "timestamp": time.time(),
            "event": "metadata_retrieved",
            "metadata": metadata
        })
        
        # Generate an SQL query
        sql_query, reasoning = await self._generate_sql_query(nl_query, metadata)
        
        # Log the generated query
        self._log_to_file(log_file, {
            "timestamp": time.time(),
            "event": "query_generated",
            "sql_query": sql_query,
            "reasoning": reasoning
        })
        
        # Execute the SQL query
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
        
        # Generate a natural language explanation
        nl_explanation = await self._generate_explanation(nl_query, sql_query, result)
        
        # Log the explanation
        self._log_to_file(log_file, {
            "timestamp": time.time(),
            "event": "explanation_generated",
            "explanation": nl_explanation
        })
        
        # Return the result
        return CrawlingResult(
            source_tool="sql",
            query_text=sql_query,
            raw_result=result.get("raw_result", []),
            nl_explanation=nl_explanation
        )
    
    async def _query_document_store(self, nl_query: str, log_file: Optional[str]) -> CrawlingResult:
        """
        Query the document store.
        
        Args:
            nl_query: Natural language query from the user
            log_file: Path to the log file
            
        Returns:
            CrawlingResult object
        """
        logger.info("Querying document store")
        
        # Get the document tool
        doc_tool = self.tool_registry.get_tool("doc")
        if not doc_tool:
            raise ValueError("Document tool not found in registry")
        
        # Get metadata from the document tool
        metadata = await doc_tool.get_metadata()
        
        # Log the metadata
        self._log_to_file(log_file, {
            "timestamp": time.time(),
            "event": "doc_metadata_retrieved",
            "metadata": metadata
        })
        
        # Determine which collection to query
        collection, query_text = await self._determine_document_collection(nl_query, metadata)
        
        # Log the selected collection
        self._log_to_file(log_file, {
            "timestamp": time.time(),
            "event": "doc_collection_determined",
            "collection": collection,
            "query_text": query_text
        })
        
        # Execute the document query
        result = await doc_tool.run({
            "query": query_text,
            "collection": collection,
            "limit": 10
        })
        
        # Log the query results
        self._log_to_file(log_file, {
            "timestamp": time.time(),
            "event": "doc_query_executed",
            "result": result
        })
        
        # Generate a natural language explanation
        nl_explanation = await self._generate_doc_explanation(nl_query, query_text, collection, result)
        
        # Log the explanation
        self._log_to_file(log_file, {
            "timestamp": time.time(),
            "event": "doc_explanation_generated",
            "explanation": nl_explanation
        })
        
        # Return the result
        return CrawlingResult(
            source_tool="doc",
            query_text=f"Collection: {collection}, Query: {query_text}",
            raw_result=result.get("raw_result", []),
            nl_explanation=nl_explanation
        )
    
    async def _generate_sql_query(self, nl_query: str, metadata: Dict[str, Any]) -> Tuple[str, str]:
        """
        Generate an SQL query from a natural language query.
        
        Args:
            nl_query: Natural language query from the user
            metadata: Database metadata
            
        Returns:
            Tuple of (sql_query, reasoning)
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
    
    async def _determine_document_collection(self, nl_query: str, metadata: Dict[str, Any]) -> Tuple[str, str]:
        """
        Determine which document collection to query and generate a query.
        
        Args:
            nl_query: Natural language query from the user
            metadata: Document store metadata
            
        Returns:
            Tuple of (collection_name, query_text)
        """
        logger.info("Determining document collection and query")
        
        # Create the MCP prompt
        system_message = """You are an AI assistant that determines which document collection to query based on a natural language question.
Follow these guidelines:
1. Analyze the user's question carefully
2. Determine which document collection would contain the information needed to answer the question
3. Generate a search query that will find relevant documents in that collection

Return your response in this format:
COLLECTION: [collection_name]
QUERY: [search_query]
"""
        
        # Format the metadata for the prompt
        formatted_metadata = "Document Collections:\n"
        for collection in metadata.get("collections", []):
            formatted_metadata += f"- {collection['name']}: {collection['document_count']} documents\n"
            
            # Add sample document if available
            if collection.get("sample_document"):
                formatted_metadata += "  Sample document fields:\n"
                for key in collection["sample_document"].keys():
                    if key != "_id":  # Skip the MongoDB ID
                        formatted_metadata += f"    - {key}\n"
        
        # Create the prompt
        prompt = f"""
User Question: {nl_query}

{formatted_metadata}

Which document collection should be queried to answer this question?
Generate a search query that will find relevant documents in that collection.

Your response should be in this format:
COLLECTION: [collection_name]
QUERY: [search_query]
"""
        
        # Generate the collection and query
        response = await self.llm_provider.generate(
            prompt=prompt,
            system_message=system_message,
            temperature=0.2
        )
        
        # Parse the response
        collection = ""
        query_text = ""
        
        if "COLLECTION:" in response and "QUERY:" in response:
            parts = response.split("QUERY:")
            collection_part = parts[0].strip()
            query_part = parts[1].strip()
            
            collection = collection_part.replace("COLLECTION:", "").strip()
            query_text = query_part
        else:
            # Fallback if the response doesn't follow the expected format
            logger.warning("Response doesn't follow the expected format, using default collection and query")
            
            # Use the first collection as default
            collections = metadata.get("collections", [])
            if collections:
                collection = collections[0]["name"]
            else:
                collection = "product_details"  # Fallback default
            
            # Use the original query as the search query
            query_text = nl_query
        
        logger.info(f"Selected collection: {collection}, Query: {query_text}")
        return collection, query_text
    
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
    
    async def _generate_doc_explanation(
        self, 
        nl_query: str, 
        query_text: str, 
        collection: str, 
        result: Dict[str, Any]
    ) -> str:
        """
        Generate a natural language explanation of the document query results.
        
        Args:
            nl_query: Original natural language query
            query_text: Query text used for the document search
            collection: Collection that was queried
            result: Query results
            
        Returns:
            Natural language explanation
        """
        logger.info("Generating explanation for document query results")
        
        # Create the MCP prompt
        system_message = """You are an AI assistant that explains document search results in natural language.
Your task is to provide a clear, concise explanation of the search results that directly answers the user's original question.
Focus on the key insights from the documents and present them in a way that's easy to understand.
"""
        
        # Format the result data for the prompt
        result_data = result.get("raw_result", [])
        if not result_data:
            return "No documents were found that match your query."
        
        # Limit the number of results to include in the prompt to avoid token limits
        max_results = 5
        truncated = len(result_data) > max_results
        
        formatted_results = json.dumps(result_data[:max_results], indent=2)
        if truncated:
            formatted_results += f"\n\n[Note: Showing {max_results} of {len(result_data)} documents]"
        
        # Create the prompt
        prompt = f"""
Original Question: {nl_query}

Document Search:
- Collection: {collection}
- Query: {query_text}

Search Results:
{formatted_results}

Please provide a clear, concise explanation of these search results that directly answers the original question.
Focus on the key insights from the documents and present them in a way that's easy to understand.
"""
        
        # Generate the explanation
        explanation = await self.llm_provider.generate(
            prompt=prompt,
            system_message=system_message,
            temperature=0.7
        )
        
        logger.info(f"Generated document explanation: {explanation[:100]}...")
        return explanation
    
    async def _generate_improved_query(
        self, 
        nl_query: str, 
        original_query: str, 
        metadata: Dict[str, Any],
        sample_data: Dict[str, List[Dict[str, Any]]]
    ) -> Tuple[str, str]:
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