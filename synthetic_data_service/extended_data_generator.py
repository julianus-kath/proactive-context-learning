"""
Extended data generator for document store and graph database.
This script generates synthetic document and graph data based on the relational database.
"""

import argparse
import json
import logging
import os
import sqlite3
from typing import Dict, List, Any, Tuple

from synthetic_data_service.document_store.generator import DocumentGenerator
from synthetic_data_service.graph_db.generator import GraphGenerator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def fetch_relational_data(db_path: str) -> Tuple[List[Dict[str, Any]], ...]:
    """Fetch data from the relational database.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        Tuple of lists containing employee, product, supplier, and sales data
    """
    logger.info(f"Fetching data from relational database at {db_path}...")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Fetch employee data
    employee_data = []
    cursor = conn.execute("SELECT * FROM employees")
    for row in cursor:
        employee_data.append({key: row[key] for key in row.keys()})
    
    # Fetch product data
    product_data = []
    cursor = conn.execute("SELECT * FROM products")
    for row in cursor:
        product_data.append({key: row[key] for key in row.keys()})
    
    # Fetch supplier data
    supplier_data = []
    cursor = conn.execute("SELECT * FROM suppliers")
    for row in cursor:
        supplier_data.append({key: row[key] for key in row.keys()})
    
    # Fetch sales data
    sales_data = []
    cursor = conn.execute("SELECT * FROM sales")
    for row in cursor:
        sales_data.append({key: row[key] for key in row.keys()})
    
    conn.close()
    
    logger.info(f"Fetched {len(employee_data)} employees, {len(product_data)} products, "
               f"{len(supplier_data)} suppliers, and {len(sales_data)} sales records.")
    
    return employee_data, product_data, supplier_data, sales_data


def generate_extended_data(db_path: str, output_dir: str, seed: int = None) -> Dict[str, Any]:
    """Generate extended document and graph data.
    
    Args:
        db_path: Path to the SQLite database file
        output_dir: Directory to save the generated data
        seed: Random seed for reproducibility
        
    Returns:
        Dictionary with summary of generated data
    """
    # Create output directories
    document_dir = os.path.join(output_dir, "documents")
    graph_dir = os.path.join(output_dir, "graphs")
    os.makedirs(document_dir, exist_ok=True)
    os.makedirs(graph_dir, exist_ok=True)
    
    # Fetch relational data
    employee_data, product_data, supplier_data, sales_data = fetch_relational_data(db_path)
    
    # Extract IDs
    product_ids = [p["product_id"] for p in product_data]
    customer_ids = list(set(s["customer_id"] for s in sales_data))
    
    # Generate document data
    logger.info("Generating document data...")
    doc_generator = DocumentGenerator(seed=seed)
    document_collections = doc_generator.generate_all_documents(
        num_products=min(len(product_ids), 30),
        num_feedback=min(len(customer_ids) * 3, 100),
        num_campaigns=20,
        num_tickets=50,
        num_articles=40,
        product_ids=product_ids,
        customer_ids=customer_ids,
        output_dir=document_dir
    )
    
    # Generate graph data
    logger.info("Generating graph data...")
    graph_generator = GraphGenerator(seed=seed)
    graph_networks = graph_generator.generate_all_graphs(
        employee_data=employee_data,
        product_data=product_data,
        supplier_data=supplier_data,
        sales_data=sales_data,
        output_dir=graph_dir
    )
    
    # Create summary
    summary = {
        "document_collections": document_collections,
        "graph_networks": graph_networks,
        "relational_data": {
            "employees": len(employee_data),
            "products": len(product_data),
            "suppliers": len(supplier_data),
            "sales": len(sales_data)
        }
    }
    
    # Save summary
    with open(os.path.join(output_dir, "extended_data_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"Extended data generation complete. Summary saved to {output_dir}/extended_data_summary.json")
    
    return summary


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Generate extended synthetic data (documents and graphs)")
    
    parser.add_argument("--db-path", type=str, default="synthetic_data.db",
                        help="Path to the SQLite database file (default: synthetic_data.db)")
    parser.add_argument("--output-dir", type=str, default="extended_data",
                        help="Directory to save the generated data (default: extended_data)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducibility (default: random)")
    
    return parser.parse_args()


def main():
    """Main function to run the extended data generator."""
    args = parse_args()
    
    try:
        # Check if the database file exists
        if not os.path.exists(args.db_path):
            logger.error(f"Database file not found: {args.db_path}")
            logger.error("Please run the relational data generator first:")
            logger.error("python -m synthetic_data_service.main")
            return 1
        
        # Generate extended data
        generate_extended_data(
            db_path=args.db_path,
            output_dir=args.output_dir,
            seed=args.seed
        )
        
        return 0
    
    except Exception as e:
        logger.error(f"Error generating extended data: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())