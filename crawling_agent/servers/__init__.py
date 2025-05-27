"""
MCP Servers package.
Provides server implementations for different data sources.
"""
from crawling_agent.servers.base_server import BaseMCPServer, QueryRequest, QueryResponse, ServerInfo
from crawling_agent.servers.erp_server import ERPServer
from crawling_agent.servers.document_storage_server import DocumentStorageServer
from crawling_agent.servers.knowledge_graph_server import KnowledgeGraphServer

__all__ = [
    'BaseMCPServer',
    'QueryRequest',
    'QueryResponse',
    'ServerInfo',
    'ERPServer',
    'DocumentStorageServer',
    'KnowledgeGraphServer'
]