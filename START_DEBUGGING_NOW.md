# Start Debugging Your "operation" Error RIGHT NOW

## 30-Second Quick Start

### Step 1: Open Terminal A (for debug stream)
```bash
cd /Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code
python debug_stream.py
```

Wait for: `Connecting to http://localhost:5001...` ✓

### Step 2: Open Terminal B (for test queries)
```bash
# Test the exact query that's failing
curl -X POST http://localhost:5001/process_conversation \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "how many customers do we have"}
    ],
    "api_key": "supersecretapikey"
  }'
```

### Step 3: Look at Terminal A
You should see something like:

```
================================================================================
         AGENT: parse_intent (Activity #1)
================================================================================
[parse_intent    ] [14:32:15.423] 📝 Intent Parsing Started
                    user_message: "how many customers do we have"
                    conversation_turns: 1

[parse_intent    ] [14:32:16.050] 📝 Intent Analysis Complete
                    operation: query
                    entities: ["customers"]
```

**If you see this** ✅ System is working! Error was transient.

**If you see red ❌** Continue below to fix it.

---

## Fixing the Error: 5-Minute Debugging Session

### What You're Looking For

In the debug output, find the section with RED text like:

```
[parse_intent    ] [14:32:15.950] ❌ Error parsing intent
                    error_type: intent_parsing_error
                    technical_error: ...
```

### Read the technical_error

It will say one of:

#### Error A: "No JSON object found"
```
[parse_intent    ] [14:32:15.600] ⚠️  Attempt 1 failed: JSON parsing error
                    error: No JSON object found
                    problematic_response: "I'll help you count..."
```

**Fix:** The LLM returned text instead of JSON. Try a simpler query.

**Action:**
```bash
# Try this instead:
curl -X POST http://localhost:5001/process_conversation \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "count customers"}
    ],
    "api_key": "supersecretapikey"
  }'
```

#### Error B: "Expecting value: line 1 column 1"
```
[parse_intent    ] [14:32:15.800] ⚠️  Attempt 2 failed: JSON parsing error
                    error: Expecting value: line 1 column 1 (char 0)
                    problematic_response: [truncated]
```

**Fix:** LLM response was incomplete/truncated. Try simpler query or check API.

**Action:**
```bash
# 1. Verify OpenAI API key is set
echo $OPENAI_API_KEY

# 2. Try simpler query
curl -X POST http://localhost:5001/process_conversation \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "how many customers"}
    ],
    "api_key": "supersecretapikey"
  }'

# 3. Check service is responding
curl http://localhost:5001/health
```

#### Error C: "'operation' KeyError" or "key not found"
```
[parse_intent    ] [14:32:15.950] ❌ Error parsing intent
                    technical_error: 'operation' (KeyError)
```

**Fix:** JSON was parsed but missing the "operation" field.

**Action:**
1. This is a prompt issue
2. The LLM isn't following the required format
3. Try: `echo $OPENAI_API_KEY` to verify API key
4. If key looks wrong, set it: `export OPENAI_API_KEY="sk-..."`
5. Restart the service
6. Try again

---

## Quickest Workaround

If fixing takes too long, try **simpler queries** that work:

```bash
# These almost always work
"count customers"
"how many products"
"list tables"
"what tables do we have"
```

---

## What Success Looks Like

After each terminal command, Terminal A should show:

```
================================================================================
         AGENT: index_database (Activity #1)
================================================================================
[index_database  ] [14:32:14.891] 🔍 Database indexed: 12 tables

================================================================================
         AGENT: get_schema (Activity #1)
================================================================================
[get_schema      ] [14:32:15.123] 📊 Schema retrieved

================================================================================
         AGENT: parse_intent (Activity #1)
================================================================================
[parse_intent    ] [14:32:15.423] 📝 Intent Parsing Started
[parse_intent    ] [14:32:16.050] ✅ Intent Analysis Complete
                    operation: query

================================================================================
         AGENT: generate_sql (Activity #1)
================================================================================
[generate_sql    ] [14:32:16.234] 🔄 SQL Generated
                    sql: SELECT COUNT(*) FROM dbo.customers

================================================================================
         AGENT: execute_query (Activity #1)
================================================================================
[execute_query   ] [14:32:16.712] ⚡ Query Executed
                    rows_returned: 1
                    status: ✅ SUCCESS

================================================================================
         AGENT: format_results (Activity #1)
================================================================================
[format_results  ] [14:32:17.145] ✅ Results formatted
```

**See this?** ✅ You're done! System works!

**Don't see this?** ❌ Follow the error fixing steps above.

---

## Checklist: Did You Try?

```
[ ] 1. Run python debug_stream.py
[ ] 2. Run a test query in another terminal
[ ] 3. Look for agent headers in debug stream
[ ] 4. Find any red ❌ errors
[ ] 5. Read the error message
[ ] 6. Apply the fix for that error type
[ ] 7. Try a simpler query
[ ] 8. Check OPENAI_API_KEY is set
[ ] 9. Restart the service if changed config
[ ] 10. Run test query again
```

---

## 2-Minute Debugging If Still Stuck

### Copy this script and run it:

```bash
#!/bin/bash

echo "🔍 Starting diagnostic..."

echo ""
echo "1. Checking API key..."
if [ -z "$OPENAI_API_KEY" ]; then
  echo "   ❌ OPENAI_API_KEY not set!"
  echo "   Run: export OPENAI_API_KEY='your-key-here'"
else
  echo "   ✅ API key is set (length: ${#OPENAI_API_KEY})"
fi

echo ""
echo "2. Checking service..."
if curl -s http://localhost:5001/health > /dev/null 2>&1; then
  echo "   ✅ Service is running"
else
  echo "   ❌ Service not responding"
  echo "   Make sure LangGraph service is started"
fi

echo ""
echo "3. Running test query..."
curl -s -X POST http://localhost:5001/process_conversation \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "count customers"}
    ],
    "api_key": "supersecretapikey"
  }' | jq . 2>/dev/null || echo "   ⚠️ No response or JSON error"

echo ""
echo "🔍 Diagnostic complete. Check debug_stream.py output above."
```

Save as `diagnose.sh`, then:
```bash
chmod +x diagnose.sh
./diagnose.sh
```

---

## If You're STILL Getting the Error

### Nuclear Option: Restart Everything

```bash
# Terminal A: Stop debug stream
# Press Ctrl+C

# Terminal B: Kill any Python processes
pkill -f "python debug_stream"
pkill -f "langgraph_service"
pkill -f "uvicorn"

# Terminal B: Verify fresh start
curl http://localhost:5001/health
# If fails, you need to start the service

# Terminal B: Start fresh debug stream
python debug_stream.py

# Terminal C: Try simple query
curl -X POST http://localhost:5001/process_conversation \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "count"}], "api_key": "supersecretapikey"}'
```

---

## Understanding the Debug Output

### Good Signs ✅
- See agent headers: `AGENT: parse_intent`
- See green checkmarks: ✅
- See "operation": "query"
- See SQL query
- See row counts

### Bad Signs ❌
- See red X marks: ❌
- Error messages in red
- No agent headers (at all)
- "operation" field missing

### Neutral Signs ⚠️
- Yellow warnings: Often OK if followed by success
- Retry attempts: Normal, as long as final attempt succeeds

---

## Real Example: Step by Step

**Your Query:** "how many customers do we have"

**Terminal A Output:**
```
[parse_intent    ] [14:32:15.600] ⚠️  Attempt 1 failed: JSON parsing error
```

**What this means:** First try didn't work, retrying...

```
[parse_intent    ] [14:32:15.850] ⚠️  Attempt 2 failed: JSON parsing error  
```

**What this means:** Still not working, one more try...

```
[parse_intent    ] [14:32:16.050] ❌ Error parsing intent
                    error_type: intent_parsing_error
                    technical_error: Failed to parse intent after 2 retries
```

**What this means:** All retries failed. LLM returned bad JSON.

**Your Fix:**
```bash
# Try simpler
curl ... -d '{"messages": [{"role": "user", "content": "customers"}], ...}'
```

**If It Works:**
```
[parse_intent    ] [14:32:16.050] ✅ Intent Analysis Complete
                    operation: query
```

**Success!** ✅

---

## Reference Guides

Need more details? Read these:

| Guide | When | Link |
|-------|------|------|
| Quick Ref | Quick lookup | `DEBUG_QUICK_REFERENCE.md` |
| Full Guide | Understanding debug stream | `DEBUG_STREAMING_GUIDE.md` |
| Error Guide | Understanding "operation" error | `OPERATION_ERROR_DEBUGGING.md` |
| Summary | Seeing all changes | `ENHANCED_DEBUGGING_SUMMARY.md` |

---

## Still Stuck?

### Common Reasons:

1. **Service not running**
   - See: `❌ Cannot connect to service`
   - Fix: Start the LangGraph service

2. **Wrong API key**
   - See: `❌ Authentication failed`
   - Fix: Check `OPENAI_API_KEY` env var

3. **Query too complex**
   - See: `❌ JSON parsing error: Expecting value`
   - Fix: Try simpler query

4. **LLM returning wrong format**
   - See: `❌ 'operation' KeyError`
   - Fix: Retry, or check LLM prompt

### Getting Help:

Save this info from debug_stream:
1. Your exact query
2. The full error section from parse_intent
3. The "problematic_response" field
4. Your OPENAI_API_KEY prefix (just first 20 chars)

Then:
- Check `OPERATION_ERROR_DEBUGGING.md` again
- Or restart service and retry

---

## You've Got This! 💪

**The debug stream shows you EXACTLY what's happening.**

- See agent headers? ✅
- See your operation? ✅  
- See errors? Now you know how to fix them ✅

Start with `python debug_stream.py` and take it from there.

Good luck! 🎯
