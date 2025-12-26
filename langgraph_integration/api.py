import asyncio
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import Body, FastAPI, Header, HTTPException
from pydantic import BaseModel

from langgraph_integration.orchestrator import QueryOrchestrator


class InvokeRequest(BaseModel):
    """Legacy endpoint: direct state-based invocation."""

    input_state: Dict[str, Any]


class ProcessQueryRequest(BaseModel):
    """High-level query endpoint that uses QueryOrchestrator.process_query()."""

    user_input: str
    messages: Optional[List[Dict[str, Any]]] = None
    conversation_id: Optional[str] = None
    # Optional free-form metadata payload; merged into orchestrator state.
    metadata: Optional[Dict[str, Any]] = None
    # Optional per-query semantic contract (benchmark mode).
    query_contract: Optional[Dict[str, Any]] = None


app = FastAPI(
    title="LangGraph ERP Assistant API",
    description="API for interacting with the multi-agent ERP assistant.",
    version="1.0.0",
)

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


async def invoke_orchestrator_agent(
    agent_name: str,
    state: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Thin helper around QueryOrchestrator.invoke_agent for reuse from
    HTTP services, tests, or other tools.

    This provides a stable import path so callers don't have to
    construct their own orchestrator instances when they only need to
    exercise a single agent node.
    """
    return await orchestrator.invoke_agent(agent_name=agent_name, state=state, options=options)


@app.post("/invoke", response_model=Dict[str, Any])
async def invoke_agent(request: InvokeRequest = Body(...)):
    """
    Invoke the main orchestrator graph with a given state.

    This endpoint is primarily intended for low-level debugging.
    """
    try:
        result = await orchestrator.ainvoke(request.input_state)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process_query", response_model=Dict[str, Any])
async def process_query(
    request: ProcessQueryRequest = Body(...),
    x_eval_run_id: Optional[str] = Header(default=None, alias="X-Eval-Run-Id"),
    x_eval_query_id: Optional[str] = Header(default=None, alias="X-Eval-Query-Id"),
):
    """
    High-level query endpoint that flows eval headers and query contracts into BaseState.

    - Reads X-Eval-Run-Id / X-Eval-Query-Id headers on benchmark requests.
    - Sets metadata={"eval_run_id", "eval_query_id", "eval_mode": "benchmark"} when present.
    - Accepts optional query_contract payload and passes it through metadata.
    """
    try:
        # Start from any caller-provided metadata so this endpoint remains extensible.
        metadata: Dict[str, Any] = {}
        if request.metadata:
            metadata.update(request.metadata)

        if request.query_contract is not None:
            metadata["query_contract"] = request.query_contract

        if x_eval_run_id:
            metadata["eval_run_id"] = x_eval_run_id
        if x_eval_query_id:
            metadata["eval_query_id"] = x_eval_query_id

        # If any eval identifiers are present, mark this as a benchmark run.
        if x_eval_run_id or x_eval_query_id:
            metadata.setdefault("eval_mode", "benchmark")

        result = await orchestrator.process_query(
            user_input=request.user_input,
            messages=request.messages,
            conversation_id=request.conversation_id,
            metadata=metadata or None,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def read_root():
    return {"message": "Welcome to the LangGraph API. Visit /docs for API documentation."}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
