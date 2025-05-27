#!/usr/bin/env python
"""
Script to load pre-generated MongoDB data from a JSON file into MongoDB.
This script is meant to be run when the MongoDB container starts.
"""
import argparse
import json
import logging
import sys
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from pymongo import MongoClient
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    logger.error("pymongo is not installed. Please install it with 'pip install pymongo'")

def load_mongodb_data(input_file: str, mongo_uri: str, db_name: str) -> None:
    """
    Load MongoDB data from a JSON file into MongoDB.
    
    Args:
        input_file: Path to the input JSON file
        mongo_uri: MongoDB connection URI
        db_name: MongoDB database name
    """
    if not PYMONGO_AVAILABLE:
        logger.error("Cannot load data: pymongo is not installed")
        return
    
    logger.info(f"Loading MongoDB data from {input_file} into {mongo_uri}/{db_name}...")
    
    try:
        # Load the data from the JSON file
        with open(input_file, 'r') as f:
            collections_data = json.load(f)
        
        # Connect to MongoDB
        client = MongoClient(mongo_uri)
        db = client[db_name]
        
        # Clear existing collections
        for collection_name in collections_data.keys():
            if collection_name in db.list_collection_names():
                logger.info(f"Dropping existing collection: {collection_name}")
                db[collection_name].drop()
        
        # Insert data into each collection
        for collection_name, documents in collections_data.items():
            logger.info(f"Inserting {len(documents)} documents into collection: {collection_name}")
            
            if documents:  # Only insert if there are documents
                result = db[collection_name].insert_many(documents)
                logger.info(f"Inserted {len(result.inserted_ids)} documents into {collection_name}")
            else:
                logger.warning(f"No documents to insert into {collection_name}")
        
        logger.info("MongoDB data loading completed successfully")
        
    except FileNotFoundError:
        logger.error(f"Input file not found: {input_file}")
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in input file: {input_file}")
    except Exception as e:
        logger.error(f"Error loading MongoDB data: {str(e)}")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Load MongoDB data from a JSON file")
    parser.add_argument("--input-file", type=str, default="mongodb_data.json", help="Path to the input JSON file")
    parser.add_argument("--mongo-uri", type=str, default="mongodb://localhost:27017/", help="MongoDB connection URI")
    parser.add_argument("--db-name", type=str, default="document_store", help="MongoDB database name")
    
    args = parser.parse_args()
    
    try:
        load_mongodb_data(args.input_file, args.mongo_uri, args.db_name)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()