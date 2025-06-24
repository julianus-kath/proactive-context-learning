"""
Test script for the multi-source agent.
"""
import asyncio
import logging
from crawling_agent.agent.multi_source_agent import MultiSourceAgent
from crawling_agent.connectors.mcp_erp_connector import MCPERPConnector
from crawling_agent.connectors.mcp_document_storage_connector import MCPDocumentStorageConnector
from crawling_agent.connectors.mcp_knowledge_graph_connector import MCPKnowledgeGraphConnector
from crawling_agent.llm.llm_client_factory import LLMClientFactory
from crawling_agent.config import (
    OPENAI_API_KEY,
    DEFAULT_LLM_TYPE,
    DEFAULT_LLM_MODEL,
    ERP_SERVER_URL,
    DOCUMENT_STORAGE_SERVER_URL,
    KNOWLEDGE_GRAPH_SERVER_URL,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TestAgent")

async def main():
    """Main function to test the agent."""
    try:
        # Create the LLM client
        llm_client = LLMClientFactory.create_client(
            client_type=DEFAULT_LLM_TYPE,
            api_key=OPENAI_API_KEY,
            model=DEFAULT_LLM_MODEL,
        )
        
        # Create the connectors
        erp_connector = MCPERPConnector(server_url=ERP_SERVER_URL)
        document_connector = MCPDocumentStorageConnector(server_url=DOCUMENT_STORAGE_SERVER_URL)
        knowledge_connector = MCPKnowledgeGraphConnector(server_url=KNOWLEDGE_GRAPH_SERVER_URL)
        
        # Create the agent
        agent = MultiSourceAgent(
            llm_client=llm_client,
            erp_connector=erp_connector,
            document_connector=document_connector,
            knowledge_connector=knowledge_connector,
            debug=True,
        )
        
        # Test query
        query = "What tables are available in the ERP database?"
        logger.info(f"Processing query: {query}")
        
        # Process the query
        response = await agent.process_query(query)
        
        # Print the response
        logger.info(f"Response: {response}")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())