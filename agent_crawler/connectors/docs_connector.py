"""
Document connector for querying document stores.
"""

import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DocumentConnector:
    """Connector for document stores."""
    
    def __init__(self, base_path: str):
        """Initialize the document connector.
        
        Args:
            base_path: Base path to the document store
        """
        self.base_path = Path(base_path)
        self.collections = self._discover_collections()
        
    def _discover_collections(self) -> List[str]:
        """Discover available collections in the document store.
        
        Returns:
            List of collection names
        """
        collections = []
        if self.base_path.exists() and self.base_path.is_dir():
            for file_path in self.base_path.glob("*.json"):
                if file_path.name != "collections_summary.json":
                    collections.append(file_path.stem)
        return collections
    
    def get_collections(self) -> List[str]:
        """Get a list of available collections.
        
        Returns:
            List of collection names
        """
        return self.collections
    
    def get_collection_schema(self, collection_name: str) -> Dict[str, Any]:
        """Get the schema for a specific collection.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Dictionary representing the collection schema
            
        Raises:
            FileNotFoundError: If the collection doesn't exist
            json.JSONDecodeError: If there's an error parsing the collection file
        """
        collection_path = self.base_path / f"{collection_name}.json"
        if not collection_path.exists():
            raise FileNotFoundError(f"Collection not found: {collection_name}")
        
        try:
            with open(collection_path, 'r') as f:
                data = json.load(f)
                if not data:
                    return {}
                
                # Infer schema from the first document
                schema = {}
                self._extract_schema(data[0], schema)
                return schema
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing collection file: {e}")
            raise
    
    def _extract_schema(self, obj: Any, schema: Dict[str, Any], prefix: str = "") -> None:
        """Extract schema from a document.
        
        Args:
            obj: Document or part of a document
            schema: Schema dictionary to update
            prefix: Prefix for nested fields
        """
        if isinstance(obj, dict):
            for key, value in obj.items():
                full_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, dict):
                    schema[full_key] = "object"
                    self._extract_schema(value, schema, full_key)
                elif isinstance(value, list):
                    if value and isinstance(value[0], dict):
                        schema[full_key] = "array of objects"
                        self._extract_schema(value[0], schema, full_key)
                    else:
                        schema[full_key] = "array"
                else:
                    schema[full_key] = type(value).__name__
    
    def query_collection(self, collection_name: str, query: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Query a collection and return matching documents.
        
        Args:
            collection_name: Name of the collection
            query: Query dictionary (field-value pairs to match)
            
        Returns:
            List of matching documents
            
        Raises:
            FileNotFoundError: If the collection doesn't exist
            json.JSONDecodeError: If there's an error parsing the collection file
        """
        collection_path = self.base_path / f"{collection_name}.json"
        if not collection_path.exists():
            raise FileNotFoundError(f"Collection not found: {collection_name}")
        
        try:
            with open(collection_path, 'r') as f:
                documents = json.load(f)
                
            if not query:
                return documents
            
            # Filter documents based on the query
            results = []
            for doc in documents:
                if self._matches_query(doc, query):
                    results.append(doc)
            
            return results
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing collection file: {e}")
            raise
    
    def _matches_query(self, document: Dict[str, Any], query: Dict[str, Any]) -> bool:
        """Check if a document matches a query.
        
        Args:
            document: Document to check
            query: Query dictionary
            
        Returns:
            True if the document matches the query, False otherwise
        """
        for key, value in query.items():
            if "." in key:
                # Handle nested fields
                parts = key.split(".")
                current = document
                for part in parts[:-1]:
                    if part not in current:
                        return False
                    current = current[part]
                
                if parts[-1] not in current or current[parts[-1]] != value:
                    return False
            elif key not in document or document[key] != value:
                return False
        
        return True
    
    def search_text(self, collection_name: str, text: str, fields: List[str] = None) -> List[Dict[str, Any]]:
        """Search for documents containing specific text.
        
        Args:
            collection_name: Name of the collection
            text: Text to search for
            fields: List of fields to search in (if None, search in all string fields)
            
        Returns:
            List of matching documents
            
        Raises:
            FileNotFoundError: If the collection doesn't exist
            json.JSONDecodeError: If there's an error parsing the collection file
        """
        collection_path = self.base_path / f"{collection_name}.json"
        if not collection_path.exists():
            raise FileNotFoundError(f"Collection not found: {collection_name}")
        
        try:
            with open(collection_path, 'r') as f:
                documents = json.load(f)
            
            # Search for documents containing the text
            results = []
            for doc in documents:
                if self._contains_text(doc, text, fields):
                    results.append(doc)
            
            return results
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing collection file: {e}")
            raise
    
    def _contains_text(self, document: Dict[str, Any], text: str, fields: List[str] = None) -> bool:
        """Check if a document contains specific text.
        
        Args:
            document: Document to check
            text: Text to search for
            fields: List of fields to search in (if None, search in all string fields)
            
        Returns:
            True if the document contains the text, False otherwise
        """
        text = text.lower()
        
        def search_in_value(value: Any) -> bool:
            if isinstance(value, str):
                return text in value.lower()
            elif isinstance(value, list):
                return any(search_in_value(item) for item in value)
            elif isinstance(value, dict):
                return search_in_dict(value)
            return False
        
        def search_in_dict(d: Dict[str, Any]) -> bool:
            for k, v in d.items():
                if fields is None or k in fields:
                    if search_in_value(v):
                        return True
            return False
        
        return search_in_dict(document)
    
    def search_all_collections(self, text: str, collections: List[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Search for documents containing specific text across all collections.
        
        Args:
            text: Text to search for
            collections: List of collections to search in (if None, search in all collections)
            
        Returns:
            Dictionary mapping collection names to lists of matching documents
        """
        results = {}
        collections_to_search = collections or self.collections
        
        for collection in collections_to_search:
            try:
                matches = self.search_text(collection, text)
                if matches:
                    results[collection] = matches
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.warning(f"Error searching collection {collection}: {e}")
        
        return results
    
    def get_document_by_id(self, collection_name: str, id_field: str, id_value: Any) -> Optional[Dict[str, Any]]:
        """Get a document by its ID.
        
        Args:
            collection_name: Name of the collection
            id_field: Name of the ID field
            id_value: Value of the ID
            
        Returns:
            The document if found, None otherwise
            
        Raises:
            FileNotFoundError: If the collection doesn't exist
            json.JSONDecodeError: If there's an error parsing the collection file
        """
        collection_path = self.base_path / f"{collection_name}.json"
        if not collection_path.exists():
            raise FileNotFoundError(f"Collection not found: {collection_name}")
        
        try:
            with open(collection_path, 'r') as f:
                documents = json.load(f)
            
            for doc in documents:
                if id_field in doc and doc[id_field] == id_value:
                    return doc
            
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing collection file: {e}")
            raise