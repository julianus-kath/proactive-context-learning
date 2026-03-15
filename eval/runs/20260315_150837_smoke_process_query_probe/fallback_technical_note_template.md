# H2b Fallback Technical Note (Template)

- Generated: `2026-03-15T15:08:37.827772Z`
- Probe verdict: `blocked`

## Claim

The intended H2b protocol requires full `/process_query` pipeline runs with recoverable
discovery/ranked stage traces. This was not technically feasible at probe time.

## Probe Evidence

### Endpoint `http://localhost:5001`

- `/health` success count: `0`
- `/process_query` success count: `0`

## Blocking Reasons

- No reachable `/process_query` endpoint with successful response.

## Fallback Scope (if approved)

Only use retrieval-only fallback as explicitly documented and mark it as non-equivalent to
full `/process_query` grounding evaluation. Keep this note with thesis artifacts.
