# Performance Improvements – Semantic Correctness Contracts PRD

## 1. Problem Statement

The current system can:
- parse natural language questions,
- generate and execute SQL successfully,
- return non-empty result sets that pass basic structural validation,

yet still answer a *different* question than the user asked. In benchmark runs this means:
- a query is counted as “successful” if SQL executes and returns rows,
- even when the **entity**, **metric**, or **join path** are semantically wrong.

This invalidates H2a (performance claim), because latency/throughput numbers are meaningless if the agent is optimizing for plausible-but-wrong outputs instead of correct intent.

Root cause: there are no hard semantic contracts tying together:
- what the benchmark query *asks* (entity + metric + filters),
- what the system *plans* (tables, joins, dimensions, metrics),
- what the evaluation harness *accepts* as “valid”.

Correctness is emergent and fragile instead of structural and enforced.

## 2. Goals

Primary goals:
- G1: Define **explicit semantic contracts per benchmark query** (entity, metric, required tables / join path).
- G2: Enforce **semantic validation at runtime** so that answers violating the contract are rejected and force replanning, not counted as successes.
- G3: Ensure **discovery and join planning** cannot silently drop required entities/dimensions or fabricate joins not grounded in real foreign key paths.
- G4: Make **metric resolution deterministic** in benchmark mode (no LLM “creative” reinterpretation of metrics).
- G5: Reduce **LLM degrees of freedom** by using templates for common analytic patterns; LLM fills parameters rather than inventing SQL structure.
- G6: Upgrade **benchmark scoring** so that runs are evaluated on semantic correctness (entity + metric + join path), not just execution success.

Secondary goals:
- G7: Keep changes localized and observable via the existing evaluation harness (`eval/run_benchmark.py`, `eval/scoring/score_run.py`).
- G8: Preserve existing safety / guardrail guarantees (read-only SQL, required-relations guardrail, bounded queries).

## 3. Non‑Goals

- N1: Do not redesign the entire LangGraph architecture or MCP server.
- N2: Do not relax any existing SQL safety or validation checks.
- N3: Do not attempt to fully solve natural-language ambiguity; focus on **benchmark queries with curated ground truth**.
- N4: Do not change production-facing APIs or UI contracts beyond what is required to expose additional metadata for evaluation.

## 4. Users and Scenarios

### 4.1 Primary Users

- **Researcher / Thesis Author**
  - Runs benchmarks via `python -m eval.run_benchmark`.
  - Needs reliable evidence for H1 (autonomy) and H2a (performance).
  - Needs failures to be explainable and attributable to specific components (intent parsing, discovery, join planning, metric mapping, etc.).

- **System Developer / Maintainer**
  - Evolves prompts, templates, and guardrails.
  - Needs clear contract violations and diagnostics instead of opaque LLM errors.

### 4.2 Key Scenarios

1. **Top-K revenue by customer**
   - Query: “Show me the top 5 customers by total revenue this quarter.”
   - Expected entity: `customer`.
   - Expected metric: `total_revenue = SUM(order_total)` (or another canonical metric defined per dataset).
   - Required tables: `customers_dim`, `orders_fact` (names depend on catalog).
   - Expected pattern: `TOP_K_BY_METRIC` template with group-by on customer.
   - Failure examples:
     - Aggregates on `product` instead of `customer`.
     - Counts order *lines* or items instead of revenue.
     - Drops the customer dimension and returns raw order_ids.

2. **Count of orders placed**
   - Query: “How many orders did we ship last month?”
   - Expected entity: `order`.
   - Expected metric: `orders_placed = COUNT(DISTINCT order_id)` (or canonical equivalent).
   - Required tables: fact table with orders; shipping dimension table if needed.
   - Expected filters: time range aligned with “last month” interpretation.

3. **Items purchased / quantity-based metric**
   - Query: “How many items did customers purchase last week?”
   - Expected entity: `customer` or `order` (explicitly defined per benchmark).
   - Expected metric: `items_purchased = SUM(quantity)` from order lines.
   - Required tables: order lines fact; customer dimension; order header if required by FK path.

4. **Join-path sensitive queries**
   - Query: “Which suppliers have the highest average order value?”
   - Requires correct join chain `suppliers -> products -> order_items -> orders`.
   - Benchmark must fail if the agent:
     - skips a required hop,
     - uses an unconstrained ID match without FK justification,
     - or joins via an incorrect intermediary table.

## 5. Functional Requirements

### 5.1 Per‑Query Semantic Contracts (Correctness Contracts)

R1.1 For each benchmark query in `eval/datasets/*.jsonl`, there MUST be an accompanying machine-readable contract describing at minimum:
- canonical **requested entity** (e.g., `customer`, `order`, `supplier`),
- canonical **metric** key and its semantic meaning (e.g., `items_purchased`, `orders_placed`, `total_revenue`),
- canonical **metric expression** in terms of schema (e.g., `SUM(order_items.quantity)`, `COUNT(DISTINCT orders.order_id)`),
- required **dimension/fact tables** and allowed **join path(s)**,
- optional **expected analytic template** (e.g., `TOP_K_BY_METRIC`, `COUNT_ENTITY`, `AGGREGATE_OVER_PERIOD`),
- optional **filters** and time windows.

R1.2 Contracts MUST be stored alongside datasets (e.g., a parallel JSON/JSONL or manifest file) and versioned so scoring knows which contract to apply.

R1.3 Contracts MUST be human-readable enough for debugging and thesis documentation but structured for deterministic parsing.

### 5.2 Runtime Intent → Plan → Result Alignment

R2.1 The LangGraph service MUST expose, in its response payload for benchmark runs, sufficient metadata to evaluate semantic alignment:
- the parsed **intent** (`BaseState.intent` / `ParsedIntent`),
- **selected tables** and **join plan** (`join_plan`, `validator_tables_used`, `validator_tables_used_base`, `required_tables_from_kpi`, `forced_tables`),
- the final **sql_query** executed,
- **exec_result** with row-level data and metadata (existing structure reused),
- an explicit **answer contract summary** (e.g., resolved entity, metric, template, join path) for the final answer.

R2.2 `eval/run_benchmark.py` MUST persist this metadata into per-query artifacts (e.g., `Q1.json` / `results.json`) so scoring can evaluate semantic correctness offline.

R2.3 For each benchmark query, the system MUST compute or expose:
- the **resolved entity** driving the result grouping,
- the **resolved metric** and its SQL expression,
- the **join path** actually used (fact → dimensions via FK relationships).

### 5.3 Semantic Validation and Replanning

R3.1 A **semantic validator** component MUST compare:
- the per-query contract (R1),
- the runtime metadata (R2),
and determine whether the answer satisfies the contract.

R3.2 When the output dimension (entity) does not match the requested entity, validation MUST fail with a structured error (e.g., `ENTITY_MISMATCH`) containing:
- expected entity,
- resolved entity,
- diagnostic hints (e.g., grouped by product instead of customer).

R3.3 When the metric does not match the requested meaning (e.g., count of rows vs. sum of quantity), validation MUST fail with a structured error (e.g., `METRIC_MISMATCH`), including:
- expected metric key and expression,
- resolved metric expression,
- key differences (aggregation, column, distinctness).

R3.4 When the join path is not grounded in an allowed FK chain per contract (e.g., missing required dimension table or using ad-hoc ID equality without FK), validation MUST fail with `JOIN_PATH_INVALID`.

R3.5 On semantic validation failure during a benchmark run, the orchestrator MUST:
- treat this as a **recoverable error** on first occurrence,
- trigger **replanning** (back to discovery / join planning) with updated constraints (e.g., forced tables, stricter templates),
- respect existing loop safeguards (max graph cycles, required-relations guardrail),
- surface a final, user-facing explanation when replanning budget is exhausted.

R3.6 For benchmark runs, the evaluation harness MUST mark queries with semantic validation failures as **failed**, even if SQL executed and returned rows.

### 5.4 Discovery Table Retention for Required Entities

R4.1 If a contract declares an entity that maps to a dimension table (e.g., `customer` → `dim_customers`), that table MUST:
- remain in `relevant_tables` after discovery, and
- be present in the final join plan and `validator_tables_used`, unless the query is explicitly non-aggregated at that level and the contract allows omission.

R4.2 Discovery ranking and pruning logic MUST NOT drop such required entity tables purely based on low relevance scores or heuristics once a contract has marked them as required.

R4.3 When required tables are at risk of being dropped, the system SHOULD:
- log a targeted diagnostic event,
- surface this in evaluation artifacts for post-run analysis.

### 5.5 Join Planning Grounded in Schema Reality

R5.1 Joins used in benchmark-mode queries MUST be derived from **actual foreign key paths** provided by the catalog / MCP (`list_relations`, `DiscoveryRoleHints`, etc.), not only name-based ID heuristics.

R5.2 The join planner MUST be able to prove that there exists a connected FK path from the chosen fact table(s) to each required dimension table in the contract.

R5.3 If no valid FK path exists that satisfies the contract, the system MUST:
- fail the plan with a structured error (e.g., `NO_VALID_JOIN_PATH`),
- record this explicitly in evaluation artifacts,
- count the benchmark query as failed (not silently degraded).

R5.4 Ad-hoc joins on `...id = ...id` without catalog FK support MUST be disallowed in benchmark mode unless explicitly whitelisted in the contract.

### 5.6 Deterministic Metric Resolution

R6.1 For benchmark datasets, there MUST be a **deterministic mapping** from natural-language metric phrases to canonical metric definitions, e.g.:
- “items purchased” → `items_purchased = SUM(order_items.quantity)`
- “orders placed” → `orders_placed = COUNT(DISTINCT orders.order_id)`
- “revenue” → `total_revenue = SUM(order_items.unit_price * order_items.quantity)` or dataset-specific equivalent.

R6.2 The intent parser and/or a dedicated metric resolver MUST:
- select metrics from this closed set in benchmark mode,
- record the resolved metric key and expression in state.

R6.3 LLMs MUST NOT invent new metrics or reinterpret benchmark metrics outside the predefined mapping for a given dataset.

R6.4 When the metric phrase cannot be mapped (e.g., unsupported metric), the system MUST:
- fail fast with a clear error,
- not attempt to “best-effort” answer with a different metric.

### 5.7 Reduced LLM Degrees of Freedom (Templates)

R7.1 For common analytic query types in the benchmark (e.g., `TOP_K_BY_METRIC`, `COUNT_ENTITY`, `AGG_OVER_PERIOD`), there MUST be **SQL templates** that define:
- overall SQL structure,
- placeholders for fact/dimension tables,
- placeholders for grouping keys, filters, and order-by clauses.

R7.2 LLM agents in benchmark mode MUST:
- choose which template to use (via `analytic_template` / `required_action`),
- fill in parameters (tables, columns, filter conditions) consistent with contracts and catalog,
- but MUST NOT invent arbitrary SQL structures outside these templates.

R7.3 Template selection and parameterization MUST be recorded in state and evaluation artifacts so that failures can be traced back to specific templates or parameters.

### 5.8 Benchmark-Driven Regression Control

R8.1 `eval/scoring/score_run.py` MUST be extended to compute **semantic correctness metrics**, at minimum:
- entity correctness rate,
- metric correctness rate,
- join-path correctness rate,
- overall “semantically correct answer” rate.

R8.2 A benchmark query MUST only count as **“passed”** if:
- SQL executed successfully, **and**
- row_count satisfies minimal expectations (if defined), **and**
- entity + metric + join path satisfy the contract (R1–R7).

R8.3 Scoring output MUST include per-query semantic status and failure reasons, e.g.:
- `ENTITY_MISMATCH`, `METRIC_MISMATCH`, `JOIN_PATH_INVALID`, `NO_VALID_JOIN_PATH`, `UNSUPPORTED_METRIC`.

R8.4 These semantic metrics MUST be used as the primary evidence for H2a in thesis reporting; raw execution success rate can be reported but explicitly labeled as secondary.

## 6. UX / Developer Experience Requirements

R9.1 Running benchmarks MUST remain a single command (`python -m eval.run_benchmark ...`) with no additional steps beyond configuring dataset + contracts.

R9.2 When a benchmark query fails semantically, logs and artifacts MUST make the failure **localizable**:
- show the contract,
- show the resolved entity/metric/join path,
- show the specific mismatch reason.

R9.3 It SHOULD be possible to re-run a single query (or small subset) for debugging without recomputing the entire benchmark.

## 7. Constraints and Assumptions

- A1: Benchmark datasets are curated and can be extended with per-query contracts by hand.
- A2: Existing state contracts in `langgraph_integration/contracts/state.py` and guardrails in `langgraph_integration/guardrails/required_relations.py` remain the primary plumbing for sharing metadata between agents and validator.
- A3: Evaluation artifacts remain JSON-based and file-system-backed under `eval/runs/<run_id>/`.
- A4: A dedicated “benchmark mode” flag can be introduced if needed to avoid impacting production behavior while tightening semantics for evaluation.

## 8. Open Questions / Clarifications Needed

Q1: Should semantic contracts be **dataset-specific** (per benchmark corpus) or **global** across datasets with the same schema?

Q2: How strict should entity equality be?
- Exact match on dimension table name?
- Match on semantic role (e.g., `customer` role even if table is `dbo.clients`)?

Q3: For metrics involving expressions (e.g., revenue as price × quantity), should correctness be:
- exact expression match,
- or allow equivalent expressions (e.g., via normalization)?

Q4: Should join-path correctness require a **single canonical path**, or allow multiple equivalent FK paths declared in the contract?

Q5: Which subset of analytic templates is in scope for the first iteration (e.g., only `TOP_K_BY_METRIC` and `COUNT_ENTITY`), and which are deferred?

Q6: Do we want semantic validation to be enabled in normal (non-benchmark) interactive sessions, or only when `eval` headers / run IDs are present?

Q7: How should we handle queries whose answer is “no data” (e.g., zero rows or zero counts) while still satisfying entity/metric correctness?

