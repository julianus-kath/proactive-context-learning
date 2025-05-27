"""
Mock LLM implementation for testing the query translation without a real model.
"""
import uuid
from typing import Dict, Any

from crawling_agent.models.task_instruction import TaskInstruction, DataSourceType, DataSourceQuery, QueryType


class MockLLM:
    """
    Mock implementation of an LLM for testing purposes.
    Returns predefined responses for specific query patterns.
    """
    
    def __init__(self):
        """Initialize the mock LLM."""
        pass
    
    def translate_query(self, query: str) -> TaskInstruction:
        """
        Mock translation of a natural language query to a TaskInstruction.
        
        Args:
            query: The natural language query to translate
            
        Returns:
            A TaskInstruction object representing the structured task
        """
        # For product query
        if "product" in query.lower() and "price" in query.lower():
            return TaskInstruction(
                task_id=str(uuid.uuid4()),
                original_query=query,
                description="Retrieve products with price > 100 from ERP and related product documents",
                data_sources=[DataSourceType.ERP, DataSourceType.DOCUMENT_STORAGE],
                queries=[
                    DataSourceQuery(
                        source_type=DataSourceType.ERP,
                        query_type=QueryType.SQL,
                        query="SELECT * FROM products WHERE price > :price",
                        parameters={"price": 100}
                    ),
                    DataSourceQuery(
                        source_type=DataSourceType.DOCUMENT_STORAGE,
                        query_type=QueryType.MONGODB,
                        query='{"product_type": {"$exists": true}, "price": {"$gt": 100}}',
                        parameters={}
                    )
                ]
            )
        
        # For employee query
        elif "employee" in query.lower() or "department" in query.lower():
            return TaskInstruction(
                task_id=str(uuid.uuid4()),
                original_query=query,
                description="Retrieve employees in Sales department from ERP and knowledge graph",
                data_sources=[DataSourceType.ERP, DataSourceType.KNOWLEDGE_GRAPH],
                queries=[
                    DataSourceQuery(
                        source_type=DataSourceType.ERP,
                        query_type=QueryType.SQL,
                        query="SELECT e.* FROM employees e JOIN departments d ON e.department_id = d.id WHERE d.name = :dept_name",
                        parameters={"dept_name": "Sales"}
                    ),
                    DataSourceQuery(
                        source_type=DataSourceType.KNOWLEDGE_GRAPH,
                        query_type=QueryType.SPARQL,
                        query="""
                        PREFIX org: <http://example.org/organization\#\>
                        SELECT ?employee ?name ?position
                        WHERE {
                            ?employee org:worksIn ?department .
                            ?department org:name "Sales" .
                            ?employee org:name ?name .
                            ?employee org:position ?position .
                        }
                        """,
                        parameters={}
                    )
                ]
            )
        
        # Default generic response
        else:
            return TaskInstruction(
                task_id=str(uuid.uuid4()),
                original_query=query,
                description=f"Generic task for query: {query}",
                data_sources=[DataSourceType.ERP],
                queries=[
                    DataSourceQuery(
                        source_type=DataSourceType.ERP,
                        query_type=QueryType.SQL,
                        query="SELECT * FROM relevant_table LIMIT 10",
                        parameters={}
                    )
                ]
            )
