"""
Script to populate the MongoDB document store with synthetic data.
"""
import os
import json
import logging
import asyncio
import aiohttp
import argparse
import random
from typing import Dict, List, Any, Optional

from synthetic_data_service.document_store.generator import DocumentGenerator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def get_product_ids(erp_api_url: str) -> List[int]:
    """
    Get product IDs from the ERP API.
    
    Args:
        erp_api_url: URL of the ERP API
        
    Returns:
        List of product IDs
    """
    async with aiohttp.ClientSession() as session:
        try:
            # Query the products table to get product IDs
            query = "SELECT product_id FROM products"
            async with session.post(
                f"{erp_api_url}/query",
                json={"sql": query}
            ) as response:
                response.raise_for_status()
                result = await response.json()
                
                # Extract product IDs
                product_ids = [row["product_id"] for row in result.get("data", [])]
                logger.info(f"Retrieved {len(product_ids)} product IDs from ERP API")
                return product_ids
                
        except Exception as e:
            logger.error(f"Error getting product IDs: {str(e)}")
            return []


async def get_customer_ids(erp_api_url: str) -> List[int]:
    """
    Get customer IDs from the ERP API.
    
    Args:
        erp_api_url: URL of the ERP API
        
    Returns:
        List of customer IDs
    """
    async with aiohttp.ClientSession() as session:
        try:
            # Query the customers table to get customer IDs
            query = "SELECT customer_id FROM customers"
            async with session.post(
                f"{erp_api_url}/query",
                json={"sql": query}
            ) as response:
                response.raise_for_status()
                result = await response.json()
                
                # Extract customer IDs
                customer_ids = [row["customer_id"] for row in result.get("data", [])]
                logger.info(f"Retrieved {len(customer_ids)} customer IDs from ERP API")
                return customer_ids
                
        except Exception as e:
            logger.error(f"Error getting customer IDs: {str(e)}")
            return []


async def populate_collection(
    doc_api_url: str,
    collection_name: str,
    documents: List[Dict[str, Any]]
) -> bool:
    """
    Populate a collection in the document store.
    
    Args:
        doc_api_url: URL of the Document Store API
        collection_name: Name of the collection to populate
        documents: List of documents to insert
        
    Returns:
        True if successful, False otherwise
    """
    async with aiohttp.ClientSession() as session:
        try:
            # Populate the collection
            async with session.post(
                f"{doc_api_url}/populate",
                json={
                    "collection_name": collection_name,
                    "documents": documents
                }
            ) as response:
                response.raise_for_status()
                result = await response.json()
                
                logger.info(f"Populated collection {collection_name} with {result.get('inserted_count', 0)} documents")
                return True
                
        except Exception as e:
            logger.error(f"Error populating collection {collection_name}: {str(e)}")
            return False


async def main(
    erp_api_url: str,
    doc_api_url: str,
    seed: Optional[int] = None,
    num_products: int = 50,
    num_feedback: int = 100,
    num_campaigns: int = 20,
    num_tickets: int = 100,
    num_kb_articles: int = 30
):
    """
    Populate the document store with synthetic data.
    
    Args:
        erp_api_url: URL of the ERP API
        doc_api_url: URL of the Document Store API
        seed: Random seed for reproducibility
        num_products: Number of product documents to generate
        num_feedback: Number of customer feedback documents to generate
        num_campaigns: Number of marketing campaign documents to generate
        num_tickets: Number of support ticket documents to generate
        num_kb_articles: Number of knowledge base articles to generate
    """
    logger.info("Starting document store population")
    
    # Initialize the document generator
    generator = DocumentGenerator(seed=seed)
    logger.info(f"Initialized document generator with seed: {generator.seed}")
    
    # Get product and customer IDs from the ERP API
    product_ids = await get_product_ids(erp_api_url)
    customer_ids = await get_customer_ids(erp_api_url)
    
    if not product_ids:
        logger.error("No product IDs found, cannot generate product-related documents")
        return
    
    if not customer_ids:
        logger.error("No customer IDs found, cannot generate customer-related documents")
        return
    
    # Generate and populate product details
    product_details = generator.generate_product_details(
        num_products=min(num_products, len(product_ids)),
        product_ids=product_ids
    )
    await populate_collection(doc_api_url, "product_details", product_details)
    
    # Generate and populate customer feedback
    customer_feedback = generator.generate_customer_feedback(
        num_feedback=num_feedback,
        customer_ids=customer_ids,
        product_ids=product_ids
    )
    await populate_collection(doc_api_url, "customer_feedback", customer_feedback)
    
    # Generate and populate marketing campaigns
    marketing_campaigns = generator.generate_marketing_campaigns(
        num_campaigns=num_campaigns,
        product_ids=product_ids
    )
    await populate_collection(doc_api_url, "marketing_campaigns", marketing_campaigns)
    
    # Generate and populate support tickets
    support_tickets = generator.generate_support_tickets(
        num_tickets=num_tickets,
        customer_ids=customer_ids,
        product_ids=product_ids
    )
    await populate_collection(doc_api_url, "support_tickets", support_tickets)
    
    # Generate and populate knowledge base articles
    knowledge_base = generator.generate_knowledge_base_articles(
        num_articles=num_kb_articles,
        product_ids=product_ids
    )
    await populate_collection(doc_api_url, "knowledge_base", knowledge_base)
    
    logger.info("Document store population completed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Populate the document store with synthetic data")
    parser.add_argument("--erp-api-url", type=str, default="http://localhost:8001", help="URL of the ERP API")
    parser.add_argument("--doc-api-url", type=str, default="http://localhost:8002", help="URL of the Document Store API")
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    parser.add_argument("--num-products", type=int, default=50, help="Number of product documents to generate")
    parser.add_argument("--num-feedback", type=int, default=100, help="Number of customer feedback documents to generate")
    parser.add_argument("--num-campaigns", type=int, default=20, help="Number of marketing campaign documents to generate")
    parser.add_argument("--num-tickets", type=int, default=100, help="Number of support ticket documents to generate")
    parser.add_argument("--num-kb-articles", type=int, default=30, help="Number of knowledge base articles to generate")
    
    args = parser.parse_args()
    
    asyncio.run(main(
        erp_api_url=args.erp_api_url,
        doc_api_url=args.doc_api_url,
        seed=args.seed,
        num_products=args.num_products,
        num_feedback=args.num_feedback,
        num_campaigns=args.num_campaigns,
        num_tickets=args.num_tickets,
        num_kb_articles=args.num_kb_articles
    ))