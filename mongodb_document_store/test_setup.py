"""
Test script to verify MongoDB document store setup.
"""

import asyncio
import logging
import sys
from connection import mongodb_manager
from query_interface import mongo_query

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_connection():
    """Test MongoDB connection."""
    logger.info("Testing MongoDB connection...")
    
    try:
        success = await mongodb_manager.connect()
        if success:
            logger.info("✅ MongoDB connection successful")
            
            # Test health check
            health = await mongodb_manager.health_check()
            logger.info(f"Health status: {health['status']}")
            
            return True
        else:
            logger.error("❌ MongoDB connection failed")
            return False
    except Exception as e:
        logger.error(f"❌ Connection test failed: {e}")
        return False

async def test_basic_operations():
    """Test basic MongoDB operations."""
    logger.info("Testing basic operations...")
    
    try:
        # Test getting database stats
        stats = await mongodb_manager.get_database_stats()
        logger.info(f"Database stats: {stats}")
        
        # Test collection access
        products_collection = mongodb_manager.get_collection("product_catalog")
        count = await products_collection.count_documents({})
        logger.info(f"Products collection has {count} documents")
        
        logger.info("✅ Basic operations test passed")
        return True
    except Exception as e:
        logger.error(f"❌ Basic operations test failed: {e}")
        return False

async def test_query_interface():
    """Test the query interface."""
    logger.info("Testing query interface...")
    
    try:
        # Test product search (should work even with empty collection)
        products = await mongo_query.search_products(query="test", limit=5)
        logger.info(f"Product search returned {len(products)} results")
        
        # Test review analytics (should handle empty collection gracefully)
        analytics = await mongo_query.get_review_analytics()
        logger.info(f"Review analytics: {analytics}")
        
        # Test schema analysis
        try:
            schema = await mongo_query.get_collection_schema("products")
            if "error" in schema:
                logger.info(f"Schema analysis (empty collection): {schema['error']}")
            else:
                logger.info("Schema analysis successful")
        except Exception as schema_error:
            logger.info(f"Schema analysis (expected for empty collection): {schema_error}")
        
        logger.info("✅ Query interface test passed")
        return True
    except Exception as e:
        logger.error(f"❌ Query interface test failed: {e}")
        return False

async def run_all_tests():
    """Run all tests."""
    logger.info("Starting MongoDB Document Store tests...")
    
    tests = [
        ("Connection Test", test_connection),
        ("Basic Operations Test", test_basic_operations),
        ("Query Interface Test", test_query_interface)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"Running: {test_name}")
        logger.info(f"{'='*50}")
        
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info(f"\n{'='*50}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*50}")
    
    passed = 0
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\nOverall: {passed}/{len(results)} tests passed")
    
    # Cleanup
    await mongodb_manager.disconnect()
    
    return passed == len(results)

if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Tests cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        sys.exit(1)