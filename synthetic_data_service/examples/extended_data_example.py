"""
Example script demonstrating how to work with the extended data (documents and graphs).
"""

import json
import os
import sys
from pprint import pprint
from typing import Dict, List, Any

# Add the parent directory to the path so we can import the synthetic_data_service package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


def load_json_file(file_path: str) -> Any:
    """Load a JSON file.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        The loaded JSON data
    """
    with open(file_path, 'r') as f:
        return json.load(f)


def explore_document_collection(collection_path: str, limit: int = 5) -> None:
    """Explore a document collection.
    
    Args:
        collection_path: Path to the collection JSON file
        limit: Maximum number of documents to display
    """
    collection_name = os.path.basename(collection_path).replace('.json', '')
    print(f"\n=== {collection_name.upper()} COLLECTION ===\n")
    
    documents = load_json_file(collection_path)
    
    print(f"Total documents: {len(documents)}")
    print(f"Sample document (showing first {limit}):")
    
    for i, doc in enumerate(documents[:limit]):
        print(f"\nDocument {i+1}:")
        pprint(doc, depth=2, compact=True)  # Limit depth to keep output manageable
    
    print("\nDocument structure:")
    if documents:
        print_document_structure(documents[0])


def print_document_structure(document: Dict[str, Any], prefix: str = '') -> None:
    """Print the structure of a document.
    
    Args:
        document: The document to print the structure of
        prefix: Prefix for nested fields
    """
    for key, value in document.items():
        if isinstance(value, dict):
            print(f"{prefix}{key}: <object>")
            print_document_structure(value, prefix + '  ')
        elif isinstance(value, list):
            if value and isinstance(value[0], dict):
                print(f"{prefix}{key}: <array of objects>")
            else:
                print(f"{prefix}{key}: <array>")
        else:
            print(f"{prefix}{key}: <{type(value).__name__}>")


def explore_graph_network(graph_path: str) -> None:
    """Explore a graph network.
    
    Args:
        graph_path: Path to the graph JSON file
    """
    graph_name = os.path.basename(graph_path).replace('.json', '')
    print(f"\n=== {graph_name.upper()} ===\n")
    
    graph = load_json_file(graph_path)
    
    print(f"Nodes: {len(graph['nodes'])}")
    print(f"Edges: {len(graph['edges'])}")
    
    # Count node labels
    label_counts = {}
    for node in graph['nodes']:
        for label in node['labels']:
            label_counts[label] = label_counts.get(label, 0) + 1
    
    print("\nNode labels:")
    for label, count in label_counts.items():
        print(f"  {label}: {count}")
    
    # Count edge types
    edge_type_counts = {}
    for edge in graph['edges']:
        edge_type = edge['type']
        edge_type_counts[edge_type] = edge_type_counts.get(edge_type, 0) + 1
    
    print("\nEdge types:")
    for edge_type, count in edge_type_counts.items():
        print(f"  {edge_type}: {count}")
    
    # Sample nodes and edges
    print("\nSample nodes (showing first 3):")
    for i, node in enumerate(graph['nodes'][:3]):
        print(f"\nNode {i+1}:")
        pprint(node)
    
    print("\nSample edges (showing first 3):")
    for i, edge in enumerate(graph['edges'][:3]):
        print(f"\nEdge {i+1}:")
        pprint(edge)


def main():
    """Main function to explore the extended data."""
    # Check if extended data exists
    extended_data_dir = os.path.join(os.path.dirname(__file__), '../../extended_data')
    if not os.path.exists(extended_data_dir):
        print("Extended data directory not found. Please generate the extended data first:")
        print("python -m synthetic_data_service.extended_data_generator")
        return 1
    
    # Explore document collections
    document_dir = os.path.join(extended_data_dir, 'documents')
    if os.path.exists(document_dir):
        collections = [f for f in os.listdir(document_dir) if f.endswith('.json') and f != 'collections_summary.json']
        
        print(f"\nFound {len(collections)} document collections:")
        for collection in collections:
            print(f"  - {collection}")
        
        # Explore a few collections as examples
        for collection in ['product_details.json', 'customer_feedback.json']:
            if collection in collections:
                explore_document_collection(os.path.join(document_dir, collection))
    
    # Explore graph networks
    graph_dir = os.path.join(extended_data_dir, 'graphs')
    if os.path.exists(graph_dir):
        networks = [f for f in os.listdir(graph_dir) if f.endswith('.json') and f != 'graphs_summary.json']
        
        print(f"\nFound {len(networks)} graph networks:")
        for network in networks:
            print(f"  - {network}")
        
        # Explore a few networks as examples
        for network in ['employee_network.json', 'product_network.json']:
            if network in networks:
                explore_graph_network(os.path.join(graph_dir, network))
    
    print("\nFor more information on the extended data models, see:")
    print("synthetic_data_service/docs/extended_data.md")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())