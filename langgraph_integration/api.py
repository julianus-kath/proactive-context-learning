import asyncio
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
import uvicorn
from typing import Dict, Any

from langgraph_integration.orchestrator import QueryOrchestrator

# 1. Define request body model
class InvokeRequest(BaseModel):
    input_state: Dict[str, Any]

# 2. Create FastAPI app
app = FastAPI(
    title="LangGraph ERP Assistant API",
    description="API for interacting with the multi-agent ERP assistant.",
    version="1.0.0",
)

# 3. Initialize orchestrator
# This is created once at startup
orchestrator = QueryOrchestrator()

@app.on_event("startup")
async def startup_event():
    # You can add any async startup logic for the orchestrator here
    # For example, connecting to services
    await orchestrator.__aenter__()
    print("Orchestrator started up.")

@app.on_event("shutdown")
async def shutdown_event():
    await orchestrator.close()
    print("Orchestrator shut down.")

# 4. Create the API endpoint
@app.post("/invoke", response_model=Dict[str, Any])
async def invoke_agent(request: InvokeRequest = Body(...)):
    """
    Invoke the main orchestrator graph with a given state.
    
    This endpoint allows you to run the entire multi-agent query process.
    """
    try:
        # Use the input_state from the request body
        result = await orchestrator.ainvoke(request.input_state)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Add a root endpoint for discoverability
@app.get("/")
def read_root():
    return {"message": "Welcome to the LangGraph API. Visit /docs for API documentation."}

# 5. Add a main block to run the server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
