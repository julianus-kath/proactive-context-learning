# Fix bug

## Configuration
- **Artifacts Path**: {@artifacts_path} → `.zenflow/tasks/{task_id}`

---

## Workflow Steps

### [x] Step: Investigation and Planning
<!-- chat-id: 44215c00-0848-42ab-8b39-b8f0861b45de -->

Analyze the bug report and design a solution.

1. Review the bug description, error messages, and logs
2. Clarify reproduction steps with the user if unclear
3. Check existing tests for clues about expected behavior
4. Locate relevant code sections and identify root cause
5. Propose a fix based on the investigation
6. Consider edge cases and potential side effects

Save findings to `{@artifacts_path}/investigation.md` with:
- Bug summary
- Root cause analysis
- Affected components
- Proposed solution

### [x] Step: Implementation
<!-- chat-id: d14b0682-5e4e-462b-9622-fccc55001088 -->
Read `{@artifacts_path}/investigation.md`
Implement the bug fix.

1. Add/adjust regression test(s) that fail before the fix and pass after
2. Implement the fix
3. Run relevant tests
4. Update `{@artifacts_path}/investigation.md` with implementation notes and test results

If blocked or uncertain, ask the user for direction.

### [x] Step: Advanced Evaluation Stability & Semantics
<!-- chat-id: 9443fb1a-ea06-48b6-a86a-247ae69b564e -->

Deepen the implementation to address the remaining benchmark failures and prepare for MSSQL as the primary target:

1. Recursion Loop Fixes (Q1/Q2/Q9/Q8)
   - Instrument the orchestration graph around `result_validator`, `discovery`, and `join_sql` to pinpoint cycles.
   - Tighten retry policies and add explicit stop conditions so complex analytic queries either converge to a stable plan or fail fast with a structured non-recursive error.
   - Ensure the approach is dialect-agnostic so it works for both Postgres PoC and MSSQL ERP.

2. Supplier Risk Query Alignment (Q3)
   - Analyze Discovery + JoinPlan outputs for Q3 to understand why the pipeline falls back to `SELECT * FROM customers`.
   - Refine JoinPlanAndSQLAgent prompts and validation so supplier/shipments questions produce joins over suppliers/orders/shippers, and exploratory fallbacks are not accepted as “valid” when they clearly don’t answer the question.

3. Inventory Reorder Discovery & Health Handling (Q7)
   - Improve IntentParserAgent so inventory/reorder-style prompts reliably produce `keywords_for_discovery` (e.g., products, inventory, stock).
   - Decouple Scout health messaging from the MSSQL-only ScoutRunner so that catalog readiness is correctly detected for both Postgres (SchemaCatalog + PostgresCatalogBuilder) and MSSQL (ScoutRunner), and inventory flows no longer emit “scout not initialized” when a catalog is available.

4. Timeout & Client Robustness for Long-Running Queries (Q8)
   - Correlate Q8’s CLIENT_EXCEPTION timeout with internal graph stages to see where the pipeline stalls.
   - Introduce clearer server-side timeout/error reporting so the benchmark client receives a structured error (with `error_info.type`) instead of a bare timeout, and ensure this behavior is consistent across dialects.

### [x] Step: Recursion Fixes
<!-- chat-id: 1908a16b-4dd3-48ee-bbbd-b607183a1da6 -->

Recursion Loop Fixes (Q1, Q2, Q9, Q8)

Instrument the orchestration graph around result_validator, discovery, and join_sql to pinpoint where the graph cycles and why retry_action keeps sending control back into the pipeline.
Tighten retry policies:
Make the distinction between “try next candidate” vs “replan” vs “give up” explicit.
Enforce a strict maximum number of discovery/plan cycles per query (independent of LangGraph’s global recursion_limit) and surface a clear MAX_RETRIES_EXCEEDED error instead of hitting GRAPH_RECURSION_LIMIT.
Ensure this logic is dialect-neutral so the same policy applies when we switch the MCP connector to MSSQL.
