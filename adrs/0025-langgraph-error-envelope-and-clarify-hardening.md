# ADR-0025: LangGraph Error Envelope & Clarification Hardening

**Status**: Accepted
**Date**: 2025-11-15
**Author**: Julianus Kath

## Context
The ERP assistant’s LangGraph orchestrator relied on loosely structured dictionaries across agents for execution results and error propagation. Result envelopes often deviated from the expected `{ok, data, error_info}` shape, causing downstream handling bugs, double-wrapping of errors, and unhelpful UI responses.  

In parallel, several query flows (discovery guardrails, clarification routing, growth/comparative templates, interpretation follow-ups) lacked deterministic metadata hand-offs and produced inconsistent user messaging. These gaps prevented us from closing Bug Bash items B–H, and they hampered MCP server integration tests.

## Decision
We:

- Introduced Pydantic contracts (`ResponseEnvelope`, `ErrorInfo`) and plumbed them through orchestrator nodes, agents, and the FastAPI wrapper to normalize `exec_result`/`error_info`, logging payload violations without crashing.
- Added deterministic clarification envelopes: discovery now flags empty-table scenarios, `process_query` returns `{clarify, clarification_question}` responses, AnswerAgent attaches clarification metadata, and the web API surfaces it to the UI.
- Persisted previous execution results in-memory (with disk fallback) so interpretation follow-ups work reliably after success.
- Extended deterministic MSSQL templates for `growth_analysis` and `comparative_analysis`, ensuring `intent.required_action` drives template selection and metadata.
- Added unit coverage for discovery guardrails, clarification envelopes, response envelope coercion, and new templates; verified orchestrator integration tests.

## Consequences
- Error handling is now predictable, enabling MCP clients to rely on structured envelopes.  
- Clarification flows no longer mis-route through discovery/join nodes, improving UX and reducing wasted retries.  
- Growth/comparative intents produce deterministic SQL, eliminating LLM variance.  
- Interpretation workflows survive process restarts thanks to cached exec state.  
- Additional validation/logging may surface payload violations that were previously silent; consumers should monitor the new warnings.  

## Testing
- `PYTHONPATH=. pytest tests/test_mssql_template_builder.py tests/test_orchestrator_integration.py tests/test_response_envelope.py`
- Manual MCP server verification remains required after each deployment iteration.

