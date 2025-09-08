"""
Pydantic models for MCP JSON-RPC 2.0 protocol.
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel


class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 request model."""
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 response model."""
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 error model."""
    code: int
    message: str
    data: Optional[Any] = None


class MCPTool(BaseModel):
    """MCP Tool definition."""
    name: str
    description: str
    inputSchema: Dict[str, Any]


class MCPInitializeParams(BaseModel):
    """MCP initialize method parameters."""
    protocolVersion: str
    capabilities: Dict[str, Any]
    clientInfo: Dict[str, str]


class MCPInitializeResult(BaseModel):
    """MCP initialize method result."""
    protocolVersion: str
    capabilities: Dict[str, Any]
    serverInfo: Dict[str, str]


class MCPCallToolParams(BaseModel):
    """MCP call_tool method parameters."""
    name: str
    arguments: Optional[Dict[str, Any]] = None


class MCPToolResult(BaseModel):
    """MCP tool execution result."""
    content: List[Dict[str, Any]]
    isError: Optional[bool] = False