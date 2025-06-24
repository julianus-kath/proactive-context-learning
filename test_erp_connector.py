"""
Test script for the ERP connector.
"""
import asyncio
import logging
from crawling_agent.connectors.mcp_erp_connector import MCPERPConnector
from crawling_agent.config import ERP_SERVER_URL

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TestERPConnector")

async def main():
    """Main function to test the ERP connector."""
    try:
        # Create the connector
        connector = MCPERPConnector(server_url=ERP_SERVER_URL)
        
        # Connect to the server
        logger.info("Connecting to the ERP server...")
        await connector.connect()
        
        # List the tables
        logger.info("Listing tables...")
        tables = await connector.list_tables()
        logger.info(f"Tables: {tables}")
        
        # Disconnect from the server
        logger.info("Disconnecting from the ERP server...")
        await connector.disconnect()
        
    except Exception as e:
        import traceback
        logger.error(f"Error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(main())