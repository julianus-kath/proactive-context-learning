# Debug Stream - Quick Reference Card

## Start Debugging in 30 Seconds

### Terminal 1: Start Debug Stream
```bash
cd /Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code
python debug_stream.py
```

### Terminal 2: Send Test Query
```bash
curl -X POST http://localhost:5001/process_conversation \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "how many customers do we have"}], "api_key": "supersecretapikey"}'
```

### Terminal 1: Watch the Output
Look for agent headers like:
```
================================================================================
         AGENT: parse_intent (Activity #1)
================================================================================
```

---

## Output Interpretation Cheat Sheet

### Agent Headers Show:
- **AGENT name** - Which node is running
- **Activity #N** - How many times it ran

### Log Lines Show:
- **[agent_name]** - Color-coded agent identifier
- **[HH:MM:SS.mmm]** - Timestamp when log occurred  
- **EMOJI** - Type of event (see legend below)
- **Message** - What happened
- **Indented data** - Details and context

### Emoji Legend:
| Emoji | Meaning | Example |
|-------|---------|---------|
| 📝 | Intent parsing | "Intent Analysis Complete" |
| 🔄 | SQL generation | "SQL Generated" |
| ⚡ | Query execution | "Query Executed" |
| ✅ | Success | Tool result, row count |
| ❌ | Error | Parse error, query failed |
| ⚠️ | Warning | Retry attempt, fallback |
| 🔍 | Schema discovery | Table search results |
| 🔧 | Tool call | MCP tool invoked |

---

## Expected Workflow Order

For "how many customers do we have":

```
1. INDEX_DATABASE    (setup)
   ↓
2. GET_SCHEMA        (get table list)
   ↓
3. PARSE_INTENT      (understand query)
   → operation: query
   → entities: [customers]
   ↓
4. GENERATE_SQL      (create SQL)
   → SELECT COUNT(*) FROM dbo.customers
   ↓
5. EXECUTE_QUERY     (run it)
   → rows_returned: 1
   ↓
6. FORMAT_RESULTS    (present to user)
   → "You have 42 customers"
```

---

## Quick Diagnostics

### ✅ Working Correctly
- See all 6 agents in order
- No ❌ red error marks
- "operation": "query" in parse_intent
- SQL looks reasonable
- Results appear formatted

### ⚠️ parse_intent has ⚠️ warnings
- Retry attempts are normal
- Check logs after all retries
- If retries succeed → OK
- If all retries fail → Error

### ❌ parse_intent has ❌ errors
- Check "problematic_response" field
- Options:
  - **"No JSON object found"** → Try simpler query
  - **"Missing 'operation' key"** → LLM format issue
  - **"JSONDecodeError"** → LLM response truncated

### ❌ generate_sql or execute_query fails
- See what SQL was generated
- Check if tables exist
- Is database connected?
- Is query valid SQL?

### ⏱️ Slow (> 5 seconds total)
- Check execute_query time
- If > 3 seconds → Database/query issue
- If < 3 seconds → LLM or network latency

---

## Debugging the "operation" Error

**Error Message:** `"I encountered an error while processing your request: '\n "operation"' "`

**What to do:**

1. Run debug_stream.py
2. Submit the failing query
3. Find the "AGENT: parse_intent" header
4. Look for ❌ or ⚠️ in that section
5. Check what error is shown:

| If You See | Do This |
|-----------|---------|
| ❌ No JSON object found | Try a simpler query |
| ❌ JSONDecodeError | Check LLM response length |
| ❌ 'operation' not in JSON | LLM ignored format |
| ⚠️ Attempt 1 failed, Attempt 2 succeeded | It's OK, retry worked |
| Multiple ⚠️ warnings then ❌ error | Query too complex, simplify |

---

## Common Queries That Work

Try these to verify system is working:

```
✅ "how many customers do we have"
✅ "count of products"
✅ "total orders"
✅ "what tables are available"
✅ "show me the database schema"
✅ "list all schemas"
```

---

## Performance Baseline

Normal timings:
- INDEX_DATABASE: 200-500ms
- GET_SCHEMA: 100-200ms
- PARSE_INTENT: 500-1000ms (has LLM call)
- GENERATE_SQL: 500-1000ms (has LLM call)
- EXECUTE_QUERY: 100-5000ms (varies by query)
- FORMAT_RESULTS: 300-500ms (has LLM call)

**Total: 2-8 seconds typical**

If significantly slower, check:
- OpenAI API status
- Network connectivity
- Database load
- LLM model availability

---

## Files to Know

| File | Purpose |
|------|---------|
| `debug_stream.py` | Run this to see debug output |
| `DEBUG_STREAMING_GUIDE.md` | Full guide to debug stream |
| `OPERATION_ERROR_DEBUGGING.md` | Detailed "operation" error guide |
| `ENHANCED_DEBUGGING_SUMMARY.md` | Overview of changes |
| `graph_definition.py` | Where agents/nodes are defined |
| `debug_logger.py` | Logging infrastructure |

---

## One-Minute Troubleshooting

### Problem: No output in debug stream
```bash
# Check service is running
curl http://localhost:5001/health

# If not running, start it first
```

### Problem: See agents but no data details
```bash
# Check that debug_logger is initialized
# Service needs to be restarted after code changes
```

### Problem: "operation" error keeps appearing
```bash
# 1. Run: python debug_stream.py
# 2. Check parse_intent section for ❌ errors
# 3. Try simpler query
# 4. Check OPENAI_API_KEY is set correctly
```

### Problem: Query takes 10+ seconds
```bash
# Check execute_query duration
# If > 5 seconds: database issue
# If < 5 seconds: LLM latency issue

# Try: simpler query, restart service, check API
```

---

## Copy-Paste Commands

### Start service (if not running)
```bash
cd /Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code
# Start appropriate service based on your setup
```

### Start debug stream
```bash
python debug_stream.py
```

### Test query #1 (simple count)
```bash
curl -X POST http://localhost:5001/process_conversation \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "how many customers"}], "api_key": "supersecretapikey"}'
```

### Test query #2 (schema)
```bash
curl -X POST http://localhost:5001/process_conversation \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "what tables"}], "api_key": "supersecretapikey"}'
```

### Test query #3 (your failing query)
```bash
curl -X POST http://localhost:5001/process_conversation \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "how many customers do we have"}], "api_key": "supersecretapikey"}'
```

---

## Pro Tips

💡 **Multiple Queries in One Session**
- Keep debug_stream running
- Activity numbers increment: Activity #2, #3, etc.
- Shows how many times each agent ran

💡 **Identify Slow Steps**
- Compare timestamps between log entries
- Shows exactly how long each step took
- Baseline to know what's normal

💡 **Catch Transient Issues**
- Run same query 3 times
- If it fails once, then works → transient issue
- If it always fails → systematic issue

💡 **Understand the Workflow**
- First time, just watch the flow
- Second time, look at data values
- Third time, focus on errors

💡 **Save Output for Analysis**
```bash
python debug_stream.py 2>&1 | tee debug_log.txt
# Saves output to debug_log.txt while displaying
```

---

## When to Check Each Guide

| Need | Guide |
|------|-------|
| How to use debug stream | `DEBUG_STREAMING_GUIDE.md` |
| Fix "operation" error | `OPERATION_ERROR_DEBUGGING.md` |
| See what changed | `ENHANCED_DEBUGGING_SUMMARY.md` |
| Quick lookup | This file (DEBUG_QUICK_REFERENCE.md) |

---

## Remember

- ✅ Debug stream shows **what each agent does**
- ✅ Agent headers show **which agent is active**
- ✅ Timestamps show **how long each step takes**
- ✅ Emojis show **what type of event occurred**
- ✅ Data fields show **what was processed**

**Most issues can be diagnosed in < 1 minute with debug stream!**

Happy debugging! 🎯