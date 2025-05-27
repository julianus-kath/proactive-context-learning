"""
Test the mock LLM implementation.
"""
import sys
from crawling_agent.models.task_instruction import TaskInstruction, DataSourceType, DataSourceQuery, QueryType
import uuid

def main():
    """Test the mock LLM with a simple query."""
    print("Testing Mock LLM...")
    
    # Create a sample TaskInstruction
    query = "Find all products with price greater than 100"
    task = TaskInstruction(
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
    
    # Print the task
    print(f"Task ID: {task.task_id}")
    print(f"Description: {task.description}")
    print(f"Data Sources: {[ds.value for ds in task.data_sources]}")
    print(f"Number of Queries: {len(task.queries)}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())