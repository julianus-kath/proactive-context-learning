# Enhanced Debug Streaming Guide

## Overview

The enhanced debugging system provides **per-agent visibility** into what each LangGraph node is doing, with clear visual separation, color-coding, and detailed data flow tracking.

---

## What's New

### 1. **Per-Agent Headers with Activity Tracking**

Each time an agent/node becomes active, you'll see a prominent colored header:

```
================================================================================
         AGENT: parse_intent (Activity #1)
================================================================================
```

This helps you visually identify:
- Which agent is currently working
- How many times this agent has been active in the workflow
- Clear visual boundaries between different agents

### 2. **Color-Coded Agent Identification**

Each agent gets a consistent color across all its logs:
- `index_database` → Purple
- `parse_intent` → Cyan  
- `get_schema` → Green
- `generate_sql` → Yellow
- `execute_query` → Blue
- `format_results` → Blue
- `handle_error` → Red

Logs from each agent are prefixed with the agent name in its assigned color.

### 3. **Detailed Data Flow Tracking**

Each node logs:
- **Input data** - What it receives (user message, schema, etc.)
- **Processing** - What it's doing (parsing, SQL generation, etc.)
- **Output data** - What it produces (intent analysis, SQL query, results, etc.)
- **Execution time** - How long each step takes
- **Errors** - Detailed error information with context

### 4. **Tool Calls with Context**

Tool calls are logged with:
- Tool name and arguments
- Tool ID for tracking
- Result or error
- Execution duration

---

## How to Use It

### Start the Debug Stream Monitor

```bash
python debug_stream.py
```

The monitor will:
1. Connect to the LangGraph service (default: `http://localhost:5001`)
2. Stream all debug logs in real-time
3. Display agent activities with color-coding and visual separation
4. Keep running until you stop it with `Ctrl+C`

### Interpreting the Output

#### Example: Parsing User Intent

```
================================================================================
         AGENT: parse_intent (Activity #1)
================================================================================
[parse_intent    ] [14:32:15.423] 📝 Intent Parsing Started
                    user_message: "how many customers do we have"
                    conversation_turns: 1

[parse_intent    ] [14:32:15.891] 📝 Intent Analysis Complete
                    operation: query
                    entities: ["customers"]
                    confidence: 0.95
```

**What this tells you:**
- The `parse_intent` agent received the message
- It extracted the intent as a "query" operation
- It identified "customers" as a key entity
- Confidence is high (0.95)

#### Example: SQL Generation

```
================================================================================
         AGENT: generate_sql (Activity #1)
================================================================================
[generate_sql    ] [14:32:16.234] 🔄 SQL Generation
                    source: schema_discovery
                    tables_used: ["dbo.customers"]
                    sql: SELECT COUNT(*) FROM dbo.customers

[generate_sql    ] [14:32:16.456] 🔄 SQL Generated
                    reason: Intent: query, Entities: customers
                    sql: SELECT COUNT(*) FROM dbo.customers
```

**What this tells you:**
- SQL was generated from schema discovery (not from intent parser)
- It uses the "dbo.customers" table
- The complete SQL query is shown
- Generation took ~222ms

#### Example: Query Execution

```
================================================================================
         AGENT: execute_query (Activity #1)
================================================================================
[execute_query   ] [14:32:16.712] ⚡ Query Execution Started
                    sql: SELECT COUNT(*) FROM dbo.customers
                    timeout_ms: 30000
                    max_rows: 1000

[execute_query   ] [14:32:17.145] ⚡ Query Executed
                    status: ✅ SUCCESS
                    rows_returned: 1
                    duration_ms: 433.0
```

**What this tells you:**
- Query executed successfully
- Returned 1 row (the count result)
- Took 433ms to execute
- Stayed within timeout and row limits

---

## Debugging the "operation" Error

The error you were seeing ("'\n "operation"' ") likely occurred during intent parsing. Here's how to debug it:

### 1. **Look for the parse_intent Agent Header**

```
================================================================================
         AGENT: parse_intent (Activity #1)
================================================================================
```

### 2. **Watch for Error Logs**

If you see:
```
[parse_intent    ] [14:32:15.891] ❌ Error parsing intent
                    error_type: intent_parsing_error
                    technical_error: JSON parsing failed
```

This means the LLM returned invalid JSON.

### 3. **Check What the LLM Actually Returned**

The logs will show:
```
[parse_intent    ] [14:32:15.850] ⚠️  Attempt 1 failed: JSON parsing error
                    problematic_response: [LLM output here]
```

### 4. **Common Causes**

| Error | Cause | Solution |
|-------|-------|----------|
| `No JSON object found` | LLM returned text without JSON | Retry, check prompt |
| `JSONDecodeError` | Incomplete or malformed JSON | LLM token limit, try simpler query |
| `Missing "operation" key` | JSON doesn't have required field | Prompt or LLM issue |
| `None` at operation.get() | intent_analysis is None | Check fallback logic |

---

## Understanding the Workflow Flow

Here's what a complete workflow looks like in the debug stream:

```
1. INDEX_DATABASE
   └─ Catalogs all tables and schemas
   └─ Duration: ~500ms

2. GET_SCHEMA
   └─ Retrieves lightweight schema overview
   └─ Duration: ~200ms

3. PARSE_INTENT
   └─ Analyzes user query
   └─ Extracts entities and operation type
   └─ Duration: ~500-1000ms (includes LLM call)

4. SELECT_TABLES (if needed)
   └─ Identifies relevant tables for the query
   └─ Duration: ~200ms

5. GENERATE_SQL
   └─ Creates SQL from intent and schema
   └─ Duration: ~500-1000ms (includes LLM call)

6. EXECUTE_QUERY
   └─ Runs the SQL against database
   └─ Duration: varies (depends on query complexity)

7. FORMAT_RESULTS
   └─ Formats results for user display
   └─ Duration: ~500ms (includes LLM call)

Total: ~3-5 seconds typical
```

---

## Monitoring Multiple Queries

The debug stream accumulates logs for multiple queries. Each agent/node will show Activity numbers incrementing:

```
================================================================================
         AGENT: parse_intent (Activity #1)
================================================================================
[parse_intent    ] ... first query

================================================================================
         AGENT: parse_intent (Activity #2)
================================================================================
[parse_intent    ] ... second query
```

This helps you track:
- How many times each agent was invoked
- Whether agents are being reused properly
- If there are unexpected agent invocations

---

## Performance Monitoring

Use the timing information to identify bottlenecks:

**Fast operations** (< 300ms):
- Schema discovery
- Table selection
- Database indexing

**Medium operations** (300-1000ms):
- Intent parsing (includes LLM)
- SQL generation (includes LLM)
- Result formatting (includes LLM)

**Variable operations**:
- Query execution (depends on query complexity)

If any operation is taking significantly longer than expected, check:
1. LLM latency (API timeout or model overload)
2. Network latency to MCP server
3. Database query complexity

---

## Common Issues and Solutions

### Issue: No logs appearing

**Solution:**
1. Ensure LangGraph service is running on `http://localhost:5001`
2. Check API key is correct (`supersecretapikey`)
3. Try hitting a test endpoint first: `curl http://localhost:5001/health`

### Issue: "operation" error keeps appearing

**Solution:**
1. Look at the `parse_intent` agent logs
2. Check the `problematic_response` field for what the LLM returned
3. Try a simpler query first (e.g., "how many customers")
4. Check OpenAI API key is valid

### Issue: JSON parsing errors

**Solution:**
1. The debug_stream shows exactly what was returned by the LLM
2. Check if there are truncation issues (LLM response too long)
3. Look for missing required fields (operation, sql, etc.)
4. Retry with a clearer/simpler query

### Issue: Too much output

**Solution:**
1. Filter logs by agent: look for headers like `AGENT: parse_intent`
2. Focus on ERROR and WARNING level logs (red and yellow)
3. Ignore INFO logs unless debugging

---

## Advanced: Parsing Logs for Analysis

Each log entry includes:
- `timestamp` - ISO format
- `type` - Log level (TOOL_CALL, SCOUT_MODE, ERROR, etc.)
- `message` - Main log text
- `node` - Agent/node name
- `session_id` - Session identifier

You can use this to:
- Extract logs for specific agents
- Calculate total time per agent
- Track error patterns
- Generate performance reports

---

## Next Steps

1. **Run a test query** - Try "how many customers do we have"
2. **Monitor the output** - Watch for the agent headers and flow
3. **Check the timing** - See where the bottlenecks are
4. **Review errors** - Look for any red flags in ERROR logs
5. **Fix issues** - Use the debug information to resolve problems

---

## Tips & Tricks

✅ **Do:**
- Run the debug stream in a separate terminal from the service
- Keep the stream running while testing multiple queries
- Focus on the `parse_intent` agent first (most issues occur here)
- Use timestamps to correlate with application logs

❌ **Don't:**
- Kill the debug stream between queries (logs buffer on server)
- Assume missing logs mean no activity (check network connectivity)
- Ignore ERROR and WARNING level logs
- Rely on old logs (run fresh stream before debugging)

---

## Contact & Feedback

If you encounter issues or have suggestions for improving the debug stream:
1. Check the agent headers and logs above
2. Review this guide for common solutions
3. Share the formatted debug output when reporting issues

Good luck debugging! 🎯