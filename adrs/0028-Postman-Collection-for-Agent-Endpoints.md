# ADR-0028: Postman Collection for Agent Endpoints
**Status**: Accepted
**Date**: 2025-12-27
**Author**: Julianus Kath

The HTTP Endpoints on the Agents in the Langgraph system are designed to work together seamlessly. They take a series of inputs, perform various tasks, and return outputs that can be passed along to subsequent endpoints. To make it easier for developers to understand and interact with these endpoints, we've created a comprehensive guide below.

## Requirements/ Prerequisites:
- Ensure MCP-Server & Langgraph Agent Endpoints are running locally. Use the following commands to run them: `bash start_all_services_mac.sh` (Langgraph and Frontend) and `python mcp_server/start_server.py.sh` (MCP Server). Ensure the SQL Database has been set up correctly and connected in the .env file.
- Install Postman Desktop App (https://www.postman.com/downloads/)
- Import the [agent_endpoints.postman_collection.json](../code/agent_endpoints.postman_collection.json) file into Postman using File -> Import -> Select Collection File
- You should now see the collection imported under Collections tab in Postman desktop app.
- Click on the collection name to open it up and click on the individual requests to test them out.
   ```bash
   # Run MCP Server
   cd mcp-server && npm install && npm start
   ```

Below is a compact “API docs + dummy payloads” style reference you can copy into a Markdown doc (or Postman collection description). Each endpoint has:

- A JSON example body.
- Inline comments (in a separate block) explaining what to adjust.
- Minimal fields only (you can always pass more state through if you want).

Use this as a template for bodies in your existing collection:
- [LangGraph Agent Endpoints](collection/49454877-3d1f6fa8-f7b5-48e1-825a-7f2ecbc29d3e)

---

## 1. Intent Parser – `POST /agent/intent_parser`

### Purpose

Parse the user’s input into a structured `intent` that downstream agents will use.

### Example Request Body

```jsonc
{
  "user_input": "Show me the top 10 customers by total revenue over the last 12 months",
  "messages": [
    {
      "role": "user",
      "content": "Show me the top 10 customers by total revenue over the last 12 months"
    }
  ]
}
```

### What to adjust

```text
user_input       REQUIRED
  - The raw NL question. This is the main thing to change each time.

messages         OPTIONAL
  - Only use for multi-turn context. Include previous assistant/user messages if you
    want the Intent Parser to see conversation history.
  - For single-shot queries, you can omit this entirely.
```

### Key Output Fields (for next step)

- `intent` (dict) – you pass this into Discovery:
  - `operation`
  - `primary_entities`
  - `metrics`
  - `required_action`
  - `time_window`
  - `top_k`
  - `keywords_for_discovery`
  - etc.

---

## 2. Discovery – `POST /agent/discovery`

### Purpose

Given `user_input` and `intent`, figure out which tables/columns matter and produce a compact schema view.

### Example Request Body

```jsonc
{
  "user_input": "Show me the top 10 customers by total revenue over the last 12 months",
  "intent": {
    "operation": "query",
    "primary_entities": ["customers"],
    "metrics": ["sum_revenue"],
    "required_action": "topk_sum_by_customer",
    "time_window": {
      "period": "last_12_months"
    },
    "top_k": 10,
    "keywords_for_discovery": ["customers", "revenue", "orders"]
  },
  "session_described_tables": [
    {
      "table": "fact_orders",
      "role_hints": {
        "kind": "fact",
        "metric_candidates": ["revenue", "order_amount"],
        "date_columns": ["order_date"],
        "entity_keys": ["customer_id"]
      },
      "foreign_keys": [
        {
          "from_table": "fact_orders",
          "from_column": "customer_id",
          "to_table": "dim_customers",
          "to_column": "id"
        }
      ]
    }
  ]
}
```

### What to adjust

```text
user_input                REQUIRED
  - Same as sent to Intent Parser; keep consistent with the intent.

intent                    REQUIRED
  - Copy directly from the Intent Parser output.
  - At minimum ensure:
      operation, primary_entities, metrics, required_action,
      time_window (if any), top_k (if any), keywords_for_discovery.

session_described_tables  OPTIONAL
  - Only pass this if you have cached metadata from previous Discovery calls
    in the same session. If you’re starting fresh, omit or send [].
```

### Key Output Fields (for next step)

Pass these to Join/SQL:

- `relevant_tables`
- `schema_snippet`
- `column_index`
- `session_described_tables` (updated/expanded)
- `discovery_role_hints`

---

## 3. Join & SQL – `POST /agent/join_sql`

### Purpose

Use intent + discovery output to build a join plan and candidate SQL query.

### Example Request Body

```jsonc
{
  "user_input": "Show me the top 10 customers by total revenue over the last 12 months",
  "intent": {
    "operation": "query",
    "primary_entities": ["customers"],
    "metrics": ["sum_revenue"],
    "required_action": "topk_sum_by_customer",
    "time_window": {
      "period": "last_12_months"
    },
    "top_k": 10
  },
  "relevant_tables": ["fact_orders", "dim_customers"],
  "schema_snippet": "fact_orders(order_id, customer_id, order_date, revenue, ...)\ndim_customers(id, customer_name, segment, ...)",
  "session_described_tables": [
    {
      "table": "fact_orders",
      "role_hints": {
        "kind": "fact",
        "metric_candidates": ["revenue"],
        "date_columns": ["order_date"],
        "entity_keys": ["customer_id"]
      }
    }
  ],
  "discovery_role_hints": {
    "fact_candidates": [
      {
        "table": "fact_orders",
        "metric_candidates": ["revenue"],
        "date_columns": ["order_date"],
        "entity_keys": ["customer_id"]
      }
    ],
    "dimensions": [
      {
        "table": "dim_customers",
        "entity_keys": ["id"],
        "label_columns": ["customer_name", "segment"]
      }
    ]
  },
  "column_index": {
    "fact_orders": ["order_id", "customer_id", "order_date", "revenue"],
    "dim_customers": ["id", "customer_name", "segment"]
  }
}
```

### What to adjust

```text
user_input, intent        REQUIRED
  - Copy directly from earlier steps; keep them in sync with the question.

relevant_tables           REQUIRED
  - Copy from Discovery output.

schema_snippet            REQUIRED
  - Copy from Discovery output. This is a human-readable schema; do not invent it.

session_described_tables  REQUIRED/RECOMMENDED
  - Copy from Discovery output (can be empty, but better with real metadata).

discovery_role_hints      REQUIRED/RECOMMENDED
  - Copy as-is from Discovery.

column_index              REQUIRED
  - Copy from Discovery. Used to map columns properly.
```

### Key Output Fields (for next step)

Pass these to SQL Validation:

- `join_plan`
- `sql_query`

(And KEEP all the discovery fields (`schema_snippet`, `column_index`, etc.)).

---

## 4. SQL Validation – `POST /agent/validate_sql`

### Purpose

Check/repair the SQL produced (or supplied by user) against the schema and join plan.

### Example Request Body

```jsonc
{
  "sql_query": "SELECT c.customer_name, SUM(o.revenue) AS total_revenue\nFROM fact_orders o\nJOIN dim_customers c ON o.customer_id = c.id\nWHERE o.order_date >= CURRENT_DATE - INTERVAL '12 months'\nGROUP BY c.customer_name\nORDER BY total_revenue DESC\nLIMIT 10;",
  "join_plan": {
    "fact_table": "fact_orders",
    "primary_table": "fact_orders",
    "metric_candidates": ["revenue"],
    "date_columns": ["order_date"],
    "entity_keys": ["customer_id"],
    "dimensions": {
      "customer": {
        "table": "dim_customers",
        "join_condition": "o.customer_id = c.id",
        "id_columns": ["id"],
        "label_columns": ["customer_name"],
        "self_join": false
      }
    },
    "joins": [
      {
        "table": "dim_customers",
        "join_type": "INNER",
        "on": "o.customer_id = c.id",
        "join_keys": ["customer_id", "id"]
      }
    ],
    "filters": [],
    "time_window": {
      "period": "last_12_months"
    },
    "required_action": "topk_sum_by_customer"
  },
  "column_index": {
    "fact_orders": ["order_id", "customer_id", "order_date", "revenue"],
    "dim_customers": ["id", "customer_name", "segment"]
  },
  "schema_snippet": "fact_orders(order_id, customer_id, order_date, revenue, ...)\ndim_customers(id, customer_name, segment, ...)",
  "relevant_tables": ["fact_orders", "dim_customers"],
  "intent": {
    "operation": "query",
    "primary_entities": ["customers"],
    "metrics": ["sum_revenue"],
    "required_action": "topk_sum_by_customer",
    "time_window": {
      "period": "last_12_months"
    },
    "top_k": 10
  }
}
```

### What to adjust

```text
sql_query                REQUIRED
  - If you start from Join/SQL output, copy it.
  - If the user provides raw SQL, you can inject it here and still give
    join_plan/schema to help validation/repair.

join_plan                REQUIRED
  - Copy from Join/SQL output.

column_index             REQUIRED
  - Copy from Discovery.

schema_snippet           REQUIRED
  - Copy from Discovery.

relevant_tables          REQUIRED
  - Copy from Discovery.

intent                   REQUIRED/RECOMMENDED
  - Copy from Intent Parser (and kept through Join).
  - Used for guardrails: e.g. metric alignment, time_window sanity, etc.
```

### Key Output Fields (for next step)

Pass these to Exec/Recovery:

- `validation_result` (SQL level)
- Potentially updated `sql_query` (if repair occurred)

---

## 5. Execution & Recovery – `POST /agent/exec_recovery`

### Purpose

Execute the (validated) SQL, recover from errors where possible, and enforce gatekeeping.

### Example Request Body

```jsonc
{
  "sql_query": "SELECT c.customer_name, SUM(o.revenue) AS total_revenue\nFROM fact_orders o\nJOIN dim_customers c ON o.customer_id = c.id\nWHERE o.order_date >= CURRENT_DATE - INTERVAL '12 months'\nGROUP BY c.customer_name\nORDER BY total_revenue DESC\nLIMIT 10;",
  "join_plan": {
    "fact_table": "fact_orders",
    "primary_table": "fact_orders"
  },
  "validation_result": {
    "is_valid": true,
    "error_type": null,
    "error_message": null,
    "warnings": [],
    "suggestions": [],
    "tables_used": ["fact_orders", "dim_customers"],
    "tables_used_canonical": ["fact_orders", "dim_customers"],
    "tables_used_base": ["fact_orders", "dim_customers"]
  },
  "schema_snippet": "fact_orders(order_id, customer_id, order_date, revenue, ...)\ndim_customers(id, customer_name, segment, ...)",
  "retry_count": 0
}
```

### What to adjust

```text
sql_query              REQUIRED
  - Use the (possibly repaired) SQL from Validate SQL.

join_plan              REQUIRED/RECOMMENDED
  - Copy from Join/SQL.

validation_result      REQUIRED
  - Copy from Validate SQL. Exec node uses this for gatekeeping.

schema_snippet         REQUIRED/RECOMMENDED
  - Copy from Discovery for error prompts and contextual repair.

retry_count            OPTIONAL
  - Start at 0. The agent can increment when retries happen.
```

### Key Output Fields (for next step)

Pass these to Result Validator and Answer:

- `exec_result`:
  - `ok`, `data`, `row_count`, `truncated`, `error`, `error_info`
- `retry_count` (updated)
- `error_info` (if execution fails / guardrail trips)

---

## 6. Result Validator – `POST /agent/result_validator`

### Purpose

Check whether the result makes semantic sense given the intent (e.g., no rows, obviously wrong sign, etc.).

### Example Request Body

```jsonc
{
  "exec_result": {
    "ok": true,
    "data": [
      { "customer_name": "ACME Corp", "total_revenue": 123456.78 },
      { "customer_name": "Globex", "total_revenue": 98765.43 }
    ],
    "row_count": 2,
    "truncated": false,
    "error": null,
    "error_info": null
  },
  "intent": {
    "operation": "query",
    "primary_entities": ["customers"],
    "metrics": ["sum_revenue"],
    "required_action": "topk_sum_by_customer",
    "time_window": {
      "period": "last_12_months"
    },
    "top_k": 10
  },
  "join_plan": {
    "fact_table": "fact_orders",
    "primary_table": "fact_orders"
  },
  "validation_result": {
    "is_valid": true
  }
}
```

### What to adjust

```text
exec_result           REQUIRED
  - Copy directly from Exec/Recovery.

intent                REQUIRED
  - Copy from earlier (Intent Parser); ensures the validator knows what we
    were trying to answer.

join_plan             REQUIRED/RECOMMENDED
  - Copy from Join/SQL; helps check joins/aggregations vs intent.

validation_result     OPTIONAL
  - SQL-level validation result from Validate SQL, for extra context.
```

### Key Output Fields (for next step)

Pass these to Answer:

- Result-level `validation_result` (or `result_validation_result`, depending on your schema)
- `warnings` (semantic)

---

## 7. Answer Shaping – `answer` node (internal / orchestrator)

### Purpose

Turn everything into a final user-facing answer string (plus optional metadata).

### Example Input Shape (from orchestrator, not HTTP)

```jsonc
{
  "user_input": "Show me the top 10 customers by total revenue over the last 12 months",
  "intent": {
    "operation": "query",
    "primary_entities": ["customers"],
    "metrics": ["sum_revenue"],
    "required_action": "topk_sum_by_customer",
    "time_window": {
      "period": "last_12_months"
    },
    "top_k": 10
  },
  "exec_result": {
    "ok": true,
    "data": [
      { "customer_name": "ACME Corp", "total_revenue": 123456.78 },
      { "customer_name": "Globex", "total_revenue": 98765.43 }
    ],
    "row_count": 2,
    "truncated": false,
    "error": null,
    "error_info": null
  },
  "error_info": null,
  "schema_snippet": "fact_orders(...), dim_customers(...)",
  "sql_query": "SELECT c.customer_name, SUM(o.revenue) AS total_revenue ...",
  "result_validation_result": {
    "ok": true
  },
  "warnings": []
}
```

### What to adjust

```text
user_input              REQUIRED
  - Original user question.

intent                  REQUIRED
  - Parsed intent from the first step.

exec_result             REQUIRED
  - From Exec/Recovery.

sql_query               REQUIRED/RECOMMENDED
  - Final SQL actually executed (possibly repaired).

schema_snippet          OPTIONAL/RECOMMENDED
  - For explanations / tooltips / debug UI.

error_info              OPTIONAL
  - If execution failed or we’re returning an errorful answer.

result_validation_result, warnings  OPTIONAL
  - From Result Validator; used to adjust how confident / cautious
    the final answer is.
```

### Key Output Fields

- `final_response` (str) – the text you show to the user.
- Optionally:
  - `answer_mode` (e.g. `"table"`, `"summary"`, `"error_explanation"`)
  - `sources` (e.g. table names, SQL snippet, etc.)

---

If you’d like, I can:

- Convert these into actual saved examples for each request in your [LangGraph Agent Endpoints](collection/49454877-3d1f6fa8-f7b5-48e1-825a-7f2ecbc29d3e) collection (so you can one-click send them and tweak only a few fields), or
- Generate TypeScript/JSON schemas for the shared `state` object across agents.

