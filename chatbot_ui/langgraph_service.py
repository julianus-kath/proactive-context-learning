"""
LangGraph Service - FastAPI wrapper for the LangGraph workflow
Provides HTTP endpoints for the chatbot UI to interact with the LangGraph workflow.
"""

import os
import sys
import asyncio
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv

# Add the parent directory and langgraph_integration to the path
parent_dir = os.path.join(os.path.dirname(__file__), '..')
langgraph_dir = os.path.join(parent_dir, 'langgraph_integration')
sys.path.append(parent_dir)
sys.path.append(langgraph_dir)

try:
    from langgraph_integration.graph_definition import create_database_workflow
except ImportError as e:
    print(f"Error importing LangGraph integration: {e}")
    print("Make sure you're running from the correct directory and langgraph_integration is available")
    print(f"Parent dir: {parent_dir}")
    print(f"LangGraph dir: {langgraph_dir}")
    sys.exit(1)

# Load environment variables from parent directory
env_path = os.path.join(parent_dir, '.env')
load_dotenv(env_path)

app = FastAPI(
    title="LangGraph Service",
    description="HTTP service wrapper for LangGraph database workflow",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class QueryRequest(BaseModel):
    user_input: str
    api_key: str

class ConversationRequest(BaseModel):
    messages: list  # [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    api_key: str

class QueryResponse(BaseModel):
    final_response: str
    status: str = "success"

class ConversationResponse(BaseModel):
    final_response: str = None
    operation: str = None  # "query" or "clarify"
    clarification: str = None
    clarify: bool = False  # For backward compatibility
    question: str = None   # For clarification questions
    response: str = None   # For final responses
    messages: list = []    # Updated conversation history
    status: str = "success"

class ErrorResponse(BaseModel):
    error: str
    status: str = "error"

# Global workflow instance
workflow = None

@app.on_event("startup")
async def startup_event():
    """Initialize the LangGraph workflow on startup."""
    global workflow
    try:
        print("🚀 Initializing LangGraph workflow...")
        workflow = create_database_workflow()
        print("✅ LangGraph workflow initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize LangGraph workflow: {e}")
        raise

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "LangGraph Service",
        "workflow_ready": workflow is not None
    }

@app.post("/process_query", response_model=QueryResponse)
async def process_query(request: QueryRequest = Body(...)):
    """
    Process a user query through the LangGraph workflow.
    
    Args:
        request: QueryRequest containing user_input and api_key
        
    Returns:
        QueryResponse with the final_response
    """
    global workflow
    
    # Validate API key
    expected_api_key = os.getenv("API_KEY", "supersecretapikey")
    if request.api_key != expected_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Validate input
    if not request.user_input or not request.user_input.strip():
        raise HTTPException(status_code=400, detail="user_input cannot be empty")
    
    # Check if workflow is initialized
    if workflow is None:
        raise HTTPException(status_code=503, detail="LangGraph workflow not initialized")
    
    try:
        print(f"📝 Processing query: {request.user_input[:100]}...")
        
        # Process the query through LangGraph workflow
        final_response = await workflow.process_query(request.user_input.strip())
        
        print(f"✅ Query processed successfully")
        
        return QueryResponse(
            final_response=final_response,
            status="success"
        )
        
    except Exception as e:
        print(f"❌ Error processing query: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error processing query: {str(e)}"
        )

@app.post("/process_conversation", response_model=ConversationResponse)
async def process_conversation(request: ConversationRequest = Body(...)):
    """
    Process a conversation with full context through the LangGraph workflow.
    
    Args:
        request: ConversationRequest containing messages and api_key
        
    Returns:
        ConversationResponse with the final_response or clarification
    """
    global workflow
    
    # Validate API key
    expected_api_key = os.getenv("API_KEY", "supersecretapikey")
    if request.api_key != expected_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Validate input
    if not request.messages or len(request.messages) == 0:
        raise HTTPException(status_code=400, detail="messages cannot be empty")
    
    # Check if workflow is initialized
    if workflow is None:
        raise HTTPException(status_code=503, detail="LangGraph workflow not initialized")
    
    try:
        print(f"📝 Processing conversation with {len(request.messages)} messages...")
        
        # Process the conversation through LangGraph workflow
        # For now, we'll extract the last user message and process it
        # TODO: Update workflow to handle full conversation context
        last_user_message = ""
        for msg in reversed(request.messages):
            if msg.get("role") == "user":
                last_user_message = msg.get("content", "")
                break
        
        if not last_user_message:
            raise HTTPException(status_code=400, detail="No user message found in conversation")
        
        print(f"📝 Last user message: {last_user_message[:100]}...")
        
        # Use the new conversation-aware processing
        result = await workflow.process_conversation(request.messages)
        
        operation = result.get("operation", "query")
        final_response = result.get("final_response", "")
        
        print(f"✅ Conversation processed successfully - Operation: {operation}")
        
        # Prepare updated messages array
        updated_messages = request.messages.copy()
        updated_messages.append({"role": "assistant", "content": final_response})
        
        # Determine response format based on operation
        if operation == "clarify":
            return ConversationResponse(
                final_response=final_response,
                operation=operation,
                clarification=final_response,
                clarify=True,
                question=final_response,
                messages=updated_messages,
                status=result.get("status", "success")
            )
        else:
            return ConversationResponse(
                final_response=final_response,
                operation=operation,
                clarify=False,
                response=final_response,
                messages=updated_messages,
                status=result.get("status", "success")
            )
        
    except Exception as e:
        print(f"❌ Error processing conversation: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error processing conversation: {str(e)}"
        )

@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "LangGraph Service",
        "version": "1.0.0",
        "description": "HTTP service wrapper for LangGraph database workflow",
        "endpoints": {
            "health": "/health",
            "process_query": "/process_query (POST)",
            "process_conversation": "/process_conversation (POST)",
            "docs": "/docs"
        }
    }

if __name__ == "__main__":
    print("🚀 Starting LangGraph Service...")
    print("📋 Make sure the following are running:")
    print("   - MCP Server (http://localhost:8000)")
    print("   - PostgreSQL database")
    print("   - OpenAI API key is set")
    print()
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5001,
        log_level="info"
    )