import asyncio
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import Body, FastAPI, Header, HTTPException
from pydantic import BaseModel, ValidationError

from langgraph_integration.contracts.response_envelope import (
    ErrorInfo as ErrorInfoModel,
    ResponseEnvelope,
)
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

        # Always return a stable, minimal envelope to external callers.
        if not isinstance(result, dict):
            # Fallback: coerce non-dict responses into a simple answer.
            return {"final_response": str(result)}

        # Normalize exec_result (optional, for callers that need raw rows).
        exec_result: Optional[Dict[str, Any]] = None
        exec_payload = result.get("exec_result")
        if exec_payload is not None:
            try:
                envelope = ResponseEnvelope.model_validate(exec_payload)
                exec_result = envelope.model_dump(exclude_none=True)
            except ValidationError:
                # On validation failure, surface a safe empty envelope.
                exec_result = ResponseEnvelope(ok=False, data=[]).model_dump(exclude_none=True)

        # Normalize error_info so callers see a consistent shape.
        error_info: Optional[Dict[str, Any]] = None
        error_payload = result.get("error_info")
        if error_payload:
            try:
                normalized_error = ErrorInfoModel.model_validate(error_payload)
                error_info = normalized_error.model_dump(exclude_none=True)
            except ValidationError:
                # Best-effort projection of arbitrary payloads.
                if isinstance(error_payload, dict):
                    error_info = ErrorInfoModel(
                        type=str(error_payload.get("type") or "UNKNOWN_ERROR"),
                        message=str(
                            error_payload.get("message")
                            or error_payload.get("error")
                            or "An unknown error occurred."
                        ),
                    ).model_dump(exclude_none=True)
                else:
                    error_info = ErrorInfoModel(
                        type="UNKNOWN_ERROR",
                        message=str(error_payload),
                    ).model_dump(exclude_none=True)

        # Prefer orchestrator's final_response/final_answer; fall back to error_info.
        final_response = (
            result.get("final_response")
            or result.get("final_answer")
        )
        if not final_response:
            if isinstance(error_info, dict):
                msg = error_info.get("message") or "An error occurred while processing your request."
                suggestion = error_info.get("suggestion")
                if suggestion:
                    final_response = f"{msg} {suggestion}"
                else:
                    final_response = msg
            else:
                final_response = (
                    "I couldn't process your request due to an internal error. "
                    "Please try again or adjust your question."
                )

        response: Dict[str, Any] = {"final_response": final_response}

        # Optional debug-oriented fields for callers that need extra context.
        if exec_result is not None:
            response["exec_result"] = exec_result
        sql_query = result.get("sql_query")
        if sql_query:
            response["sql_query"] = sql_query
        if error_info:
            response["error_info"] = error_info

        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def read_root():
    return {"message": "Welcome to the LangGraph API. Visit /docs for API documentation."}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
