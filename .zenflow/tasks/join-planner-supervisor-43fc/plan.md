# Spec and build

## Configuration
- **Artifacts Path**: {@artifacts_path} → `.zenflow/tasks/{task_id}`

---

## Agent Instructions

Ask the user questions when anything is unclear or needs their input. This includes:
- Ambiguous or incomplete requirements
- Technical decisions that affect architecture or user experience
- Trade-offs that require business context

Do not make assumptions on important decisions — get clarification first.

---

## Workflow Steps

### [x] Step: Technical Specification
<!-- chat-id: 8e70279f-751d-4f4d-83dd-a818bde72b01 -->

Assess the task's difficulty, as underestimating it leads to poor outcomes.
- easy: Straightforward implementation, trivial bug fix or feature
- medium: Moderate complexity, some edge cases or caveats to consider
- hard: Complex logic, many caveats, architectural considerations, or high-risk changes

Create a technical specification for the task that is appropriate for the complexity level:
- Review the existing codebase architecture and identify reusable components.
- Define the implementation approach based on established patterns in the project.
- Identify all source code files that will be created or modified.
- Define any necessary data model, API, or interface changes.
- Describe verification steps using the project's test and lint commands.

Save the output to `{@artifacts_path}/spec.md` with:
- Technical context (language, dependencies)
- Implementation approach
- Source code structure changes
- Data model / API / interface changes
- Verification approach

If the task is complex enough, create a detailed implementation plan based on `{@artifacts_path}/spec.md`:
- Break down the work into concrete tasks (incrementable, testable milestones)
- Each task should reference relevant contracts and include verification steps
- Replace the Implementation step below with the planned tasks

Rule of thumb for step size: each step should represent a coherent unit of work (e.g., implement a component, add an API endpoint, write tests for a module). Avoid steps that are too granular (single function).

Save to `{@artifacts_path}/plan.md`. If the feature is trivial and doesn't warrant this breakdown, keep the Implementation step below as is.

---

### [x] Step: JoinPlan contract & metadata wiring
<!-- chat-id: 8643b063-8a21-477d-b777-81be1f9d96a0 -->

DO:
- Extend the `JoinPlan` TypedDict (in `contracts/state.py`) with optional metadata fields (`plan_status`, `plan_confidence`, `plan_issues`, `template`) that match `spec.md`.
- Update `JoinPlanAndSQLAgent` to populate these fields consistently in `_build_join_plan_node` and `_generate_sql_node`.
- Ensure planning failures (e.g. fact or required dimensions missing) result in `plan_status="incomplete"`/`"unsupported"` plus clear entries in `plan_issues`.

DON'T:
- Don’t introduce new dataset-specific fields or flags tied to a particular ERP dataset.
- Don’t “fake” success by setting `plan_status="ok"` when the intent clearly cannot be satisfied.

---

### [x] Step: Planner behavior & removal of legacy fallbacks
<!-- chat-id: 6e7787d8-2f56-486b-973c-91134e2e9e31 -->

DO:
- Refactor `_generate_sql_node` so analytic templates are **hard‑gated**: if required pieces are missing, fail with structured `error_info` and no `sql_query` instead of emitting weak SQL.
- Keep simple `SELECT` samples only for genuinely exploratory/detail cases (no analytic template, metrics empty, or supervisor explicitly asks for exploratory mode), marked with `plan_status="exploratory"`.
- Use the new metadata (`plan_status`, `plan_issues`) everywhere the planner declines to answer so the supervisor can see “I don’t know”.

DON'T:
- Don’t add new heuristic branches that try to “guess” a SUM/GROUP BY or fallback table when templates fail.
- Don’t emit `SELECT *` or random `SUM(...)` for analytic queries just to avoid returning an error.
- Don’t add fuzzy keyword heuristics in Python to compensate for poor discovery or intent parsing; that belongs in the LLM.

---

### [x] Step: Supervisor ↔ planner instruction channel
<!-- chat-id: 3f1db7fd-59a6-4ac8-9239-767b49c75ac6 -->

DO:
- Design a small, documented field on `BaseState` (e.g. `plan_sql_instructions`) for supervisor‑generated hints (preferred fact table, exploratory vs analytic mode, discovery focus, etc.).
- Make `_build_join_plan_node` / `_generate_sql_node` read and respect these hints when present, without changing default behavior when they are absent.
- Ensure instructions are simple, structured data that the supervisor LLM can populate and the planner can safely ignore if unsupported.

DON'T:
- Don’t encode “smart” routing or query understanding in Python conditionals; the supervisor LLM should decide *when* and *how* to set `plan_sql_instructions`.
- Don’t leak chain‑of‑thought into state; keep instructions purely as high‑level hints (no natural language reasoning blobs).

---

### [x] Step: Capability tool envelopes & progress signals
<!-- chat-id: 7d3f4dbd-0a99-4e8f-aaff-92a10a2db12b -->

DO:
- Update `plan_sql_tool` in `capability_tools.py` to include `join_plan` metadata in `tool_output` and to derive `progress_signal`/`suggested_next_actions` from `plan_status` and join‑specific `error_info.type`.
- Treat failed or incomplete plans (`plan_status` in `{"incomplete","unsupported"}` or join errors) as negative progress and suggest rediscovery/replanning/clarification instead of execution.
- Treat exploratory plans as neutral (not positive) when the intent is clearly analytic.

DON'T:
- Don’t embed dataset‑specific routing rules (e.g. special‑case table names) in `_derive_progress_and_actions`.
- Don’t treat “non‑empty `sql_query`” as a success signal without checking `plan_status`.

---

### [x] Step: Supervisor summaries & LLM prompt updates
<!-- chat-id: 1ce2711b-df1c-42cd-804a-9c41c2ad3f09 -->

DO:
- Extend the supervisor’s `_llm_select_next_tool` summary payload to include join plan metadata, last planning error types, and any `plan_sql_instructions` already used.
- Update the supervisor system prompt so the LLM:
  - Chooses next tools (interpret, discover, plan, validate, execute, evaluate, finalize) based on these signals.
  - Decides when to re‑call `plan_sql` with new instructions vs rediscover vs ask the user.
- Keep `_select_initial_tool` / `_select_next_tool` as minimal guardrails (ordering, budgets) and fallbacks when the LLM selection fails.

DON'T:
- Don’t add new Python‑side routing heuristics beyond safety guards; the “brain” for next‑tool decisions must be the LLM.
- Don’t special‑case individual error messages or table names in `_select_next_tool`—push that reasoning into the LLM’s prompt instead.

---

### [x] Step: Dialect awareness & validator semantics (only where touched)
<!-- chat-id: 8ad2eee8-ccac-48d5-90ea-4ada6d44a76c -->

DO:
- Where this task changes SQL generation or validation, branch on `DB_DIALECT` instead of hardcoding MSSQL (e.g. `TOP` vs `LIMIT`, `DATEADD` vs Postgres equivalents).
- Keep SQLValidator/ResultValidator changes minimal and focused on surfacing better semantic signals (tables used, retry reasons) to the supervisor and planner.

DON'T:
- Don’t rewrite the entire dialect layer in this task; only adjust code paths you must touch to avoid introducing new MSSQL‑only assumptions.
- Don’t add new validator heuristics that mask real failures; prefer clear, structured errors the supervisor can reason about.

---

### [x] Step: Tests, UX sanity checks & report
<!-- chat-id: 2c3a795f-d45d-411d-88a5-e23dcecd48a1 -->

DO:
- Add or extend tests for:
  - `JoinPlanAndSQLAgent` behavior under success vs incomplete/unsupported plans.
  - `plan_sql_tool` envelopes and progress signals for ok/incomplete/exploratory plans.
  - (Optionally) basic supervisor interactions where planning fails (using stubs/mocks as needed).
- Manually inspect a few representative scenarios (“Top 5 customers by revenue”, “How many customers do we have?”, exploratory samples) to ensure the planner either produces robust SQL or clearly declines, instead of emitting misleading queries.
- Write `{@artifacts_path}/report.md` summarizing implementation, key decisions, and how behavior was verified.

DON'T:
- Don’t add brittle tests that depend on specific table names or one-off heuristics; focus on contract‑level behavior (plan_status, error types, supervisor-visible signals).
- Don’t hide UX issues behind opaque fallbacks—if behavior is ambiguous or surprising, prefer explicit errors that bubble up to the supervisor.

### [x] Step: Reviewing the work
<!-- chat-id: 15a8ead5-ab9d-4fe4-b204-5dfcf93483eb -->
<!-- agent: CODEX -->

I merged your changes and ran some test queries in the frontend, to see how the agent behaves. Ultimately, I got the output:
I wasn't able to retrieve the information needed to answer your question. This could be because:
• The query was too vague
• The requested data doesn't exist in the database
• The relevant tables couldn't be identified

Please try rephrasing your question with more specific details.

I want to sue this step to analyse whats going on and fix the underlying issues behind this symptom.
