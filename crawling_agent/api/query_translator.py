"""
Query translator for converting natural language queries to structured queries.
"""
import re
import time
from typing import Dict, List, Any, Tuple

from crawling_agent.models.task_instruction import DataSourceQuery, QueryType


class QueryTranslator:
    """
    Translates natural language queries into structured queries for different data sources.
    """
    
    def __init__(self):
        """Initialize the query translator."""
        pass
    
    def translate(self, query: str) -> Tuple[str, List[DataSourceQuery]]:
        """
        Translate a natural language query into structured queries for different data sources.
        
        Args:
            query: The natural language query
            
        Returns:
            A tuple containing:
            - The thought process used to translate the query
            - A list of structured queries for different data sources
        """
        # Start timing
        start_time = time.time()
        
        # Initialize the thought process
        thought_process = f"Analyzing query: '{query}'\n\n"
        
        # Initialize the list of structured queries
        structured_queries = []
        
        # Check for product-related queries
        if re.search(r'(expensive|costly|pricey|high.?price|premium)', query, re.IGNORECASE):
            thought_process += "This query is about expensive products. I'll query all data sources for products with high prices.\n\n"
            
            # Add SQL query for ERP
            thought_process += "For the ERP system, I'll use SQL to query the products table for items with price > 100:\n"
            sql_query = "SELECT * FROM products WHERE price > 100 ORDER BY price DESC"
            thought_process += f"SQL Query: {sql_query}\n\n"
            
            structured_queries.append(
                DataSourceQuery(
                    source_type="erp",
                    query_type=QueryType.SQL,
                    query=sql_query,
                    parameters={}
                )
            )
            
            # Add MongoDB query for Document Storage
            thought_process += "For the Document Storage, I'll use MongoDB query to find documents with price > 100:\n"
            mongodb_query = '{"price": {"$gt": 100}}'
            thought_process += f"MongoDB Query: {mongodb_query}\n\n"
            
            structured_queries.append(
                DataSourceQuery(
                    source_type="document_storage",
                    query_type=QueryType.MONGODB,
                    query=mongodb_query,
                    parameters={"collection": "products"}
                )
            )
            
            # Add SPARQL query for Knowledge Graph
            thought_process += "For the Knowledge Graph, I'll use SPARQL to query for products with price > 100:\n"
            sparql_query = """
            PREFIX product: <http://example.org/product#>
            SELECT ?product ?name ?price
            WHERE {
                ?product product:price ?price .
                ?product product:name ?name .
                FILTER (?price > 100)
            }
            ORDER BY DESC(?price)
            """
            thought_process += f"SPARQL Query: {sparql_query}\n\n"
            
            structured_queries.append(
                DataSourceQuery(
                    source_type="knowledge_graph",
                    query_type=QueryType.SPARQL,
                    query=sparql_query,
                    parameters={}
                )
            )
        
        # Check for employee-related queries
        elif re.search(r'(employee|staff|worker|personnel)', query, re.IGNORECASE):
            thought_process += "This query is about employees. I'll query all data sources for employee information.\n\n"
            
            # Add SQL query for ERP
            thought_process += "For the ERP system, I'll use SQL to query the employees table:\n"
            sql_query = "SELECT * FROM employees"
            
            # Check for department filter
            if re.search(r'(sales|marketing|engineering)', query, re.IGNORECASE):
                department = re.search(r'(sales|marketing|engineering)', query, re.IGNORECASE).group(1)
                sql_query += f" WHERE department = '{department.capitalize()}'"
                thought_process += f"Adding filter for {department.capitalize()} department.\n"
            
            thought_process += f"SQL Query: {sql_query}\n\n"
            
            structured_queries.append(
                DataSourceQuery(
                    source_type="erp",
                    query_type=QueryType.SQL,
                    query=sql_query,
                    parameters={}
                )
            )
            
            # Add SPARQL query for Knowledge Graph
            thought_process += "For the Knowledge Graph, I'll use SPARQL to query for employees:\n"
            sparql_query = """
            PREFIX employee: <http://example.org/employee#>
            SELECT ?employee ?name ?position ?department
            WHERE {
                ?employee a employee:Employee .
                ?employee employee:name ?name .
                ?employee employee:position ?position .
                ?employee employee:department ?department .
            """
            
            # Check for department filter
            if re.search(r'(sales|marketing|engineering)', query, re.IGNORECASE):
                department = re.search(r'(sales|marketing|engineering)', query, re.IGNORECASE).group(1)
                sparql_query += f'    FILTER(CONTAINS(STR(?department), "{department.capitalize()}"))\n'
                thought_process += f"Adding filter for {department.capitalize()} department.\n"
            
            sparql_query += "}"
            thought_process += f"SPARQL Query: {sparql_query}\n\n"
            
            structured_queries.append(
                DataSourceQuery(
                    source_type="knowledge_graph",
                    query_type=QueryType.SPARQL,
                    query=sparql_query,
                    parameters={}
                )
            )
        
        # Check for order-related queries
        elif re.search(r'(order|purchase|transaction|sale)', query, re.IGNORECASE):
            thought_process += "This query is about orders. I'll query all data sources for order information.\n\n"
            
            # Add SQL query for ERP
            thought_process += "For the ERP system, I'll use SQL to query the orders table:\n"
            sql_query = "SELECT * FROM orders"
            
            # Check for status filter
            if re.search(r'(completed|processing|pending)', query, re.IGNORECASE):
                status = re.search(r'(completed|processing|pending)', query, re.IGNORECASE).group(1)
                sql_query += f" WHERE status = '{status.capitalize()}'"
                thought_process += f"Adding filter for {status.capitalize()} status.\n"
            
            thought_process += f"SQL Query: {sql_query}\n\n"
            
            structured_queries.append(
                DataSourceQuery(
                    source_type="erp",
                    query_type=QueryType.SQL,
                    query=sql_query,
                    parameters={}
                )
            )
            
            # Add MongoDB query for Document Storage
            thought_process += "For the Document Storage, I'll use MongoDB query to find order documents:\n"
            mongodb_query = '{}'
            
            # Check for status filter
            if re.search(r'(completed|processing|pending)', query, re.IGNORECASE):
                status = re.search(r'(completed|processing|pending)', query, re.IGNORECASE).group(1)
                mongodb_query = f'{{"status": "{status.capitalize()}"}}'
                thought_process += f"Adding filter for {status.capitalize()} status.\n"
            
            thought_process += f"MongoDB Query: {mongodb_query}\n\n"
            
            structured_queries.append(
                DataSourceQuery(
                    source_type="document_storage",
                    query_type=QueryType.MONGODB,
                    query=mongodb_query,
                    parameters={"collection": "orders"}
                )
            )
        
        # Default case - query all data sources with basic queries
        else:
            thought_process += "This is a general query. I'll query all data sources with basic queries.\n\n"
            
            # Add SQL query for ERP
            thought_process += "For the ERP system, I'll use SQL to query the products table:\n"
            sql_query = "SELECT * FROM products LIMIT 5"
            thought_process += f"SQL Query: {sql_query}\n\n"
            
            structured_queries.append(
                DataSourceQuery(
                    source_type="erp",
                    query_type=QueryType.SQL,
                    query=sql_query,
                    parameters={}
                )
            )
            
            # Add MongoDB query for Document Storage
            thought_process += "For the Document Storage, I'll use MongoDB query to find product documents:\n"
            mongodb_query = '{}'
            thought_process += f"MongoDB Query: {mongodb_query}\n\n"
            
            structured_queries.append(
                DataSourceQuery(
                    source_type="document_storage",
                    query_type=QueryType.MONGODB,
                    query=mongodb_query,
                    parameters={"collection": "products"}
                )
            )
            
            # Add SPARQL query for Knowledge Graph
            thought_process += "For the Knowledge Graph, I'll use SPARQL to query for products:\n"
            sparql_query = """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            SELECT ?s ?p ?o
            WHERE {
                ?s ?p ?o .
            }
            LIMIT 5
            """
            thought_process += f"SPARQL Query: {sparql_query}\n\n"
            
            structured_queries.append(
                DataSourceQuery(
                    source_type="knowledge_graph",
                    query_type=QueryType.SPARQL,
                    query=sparql_query,
                    parameters={}
                )
            )
        
        # Calculate execution time
        execution_time = (time.time() - start_time) * 1000  # in milliseconds
        thought_process += f"Query translation completed in {execution_time:.2f}ms.\n"
        
        return thought_process, structured_queries