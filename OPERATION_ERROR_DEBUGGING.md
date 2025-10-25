# Debugging the "operation" Error

## Error Message

```
I encountered an error while processing your request: '\n "operation"' 
```

This error indicates that the **intent parsing failed** because the `operation` field was either missing or inaccessible from the intent analysis result.

---

## Root Causes

This error can occur in three scenarios:

### 1. **JSON Parsing Failed in LLM Response**
The LLM returned invalid or incomplete JSON, so `intent_analysis` becomes `None`.

### 2. **Missing "operation" Field**
The LLM returned valid JSON but without the required `operation` field.

### 3. **State Management Error**
The state object was corrupted or `intent_analysis` wasn't properly initialized.

---

## Step-by-Step Debugging

### Step 1: Run the Debug Stream

Open a terminal and run:

```bash
cd /Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code
python debug_stream.py
```

### Step 2: Submit Your Test Query

In another terminal or UI, send the query that produces the error:

```bash
curl -X POST http://localhost:5001/process_conversation \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "how many customers do we have"}],
    "api_key": "supersecretapikey"
  }'
```

### Step 3: Look for the parse_intent Agent Header

In the debug stream, you should see:

```
================================================================================
         AGENT: parse_intent (Activity #1)
================================================================================
```

### Step 4: Check for Errors

Look for error messages in the `parse_intent` section. Common patterns:

**Pattern A: JSON Parsing Error**
```
[parse_intent    ] [HH:MM:SS.mmm] ⚠️  Attempt 1 failed: JSON parsing error
                    error: No JSON object found
                    problematic_response: "some text without JSON"
```

**Pattern B: Missing "operation" Field**
```
[parse_intent    ] [HH:MM:SS.mmm] ❌ Error parsing intent
                    error: 'operation' key not found in JSON
```

**Pattern C: Incomplete JSON**
```
[parse_intent    ] [HH:MM:SS.mmm] ⚠️  Attempt 1 failed: JSON parsing error
                    error: Expecting value: line 1 column 1 (char 0)
```

---

## Quick Fixes by Scenario

### Scenario 1: JSON Parsing Issues

**Symptom:**
```
No JSON object found
or
JSONDecodeError
```

**Debugging Steps:**

1. Check if the error mentions **truncation**:
   ```
   problematic_response: [truncated]
   ```
   
2. Look at what was returned instead of JSON:
   - Is it plain text?
   - Is it incomplete?
   - Is it malformed?

3. **Fixes to try:**
   - Try a **simpler query**: "How many customers?" instead of "What is the total revenue for Q3?"
   - Check **OpenAI API status** - might be rate-limited or down
   - Verify **OPENAI_API_KEY** is set and valid in `.env`:
     ```bash
     echo $OPENAI_API_KEY
     ```

**Root Cause Analysis:**

| Observation | Likely Cause | Fix |
|-------------|--------------|-----|
| Response is completely empty | API call failed silently | Check network/API key |
| Response is plain text, no JSON | LLM didn't follow format | Check prompt in prompts.py |
| Response ends abruptly | Token limit exceeded | Use fewer schema tables |
| Response has `"operation"` but invalid JSON | Incomplete JSON | Increase max tokens or simplify |

---

### Scenario 2: Missing "operation" Field

**Symptom:**
```
[parse_intent    ] [HH:MM:SS.mmm] ❌ Error parsing intent
                    technical_error: 'operation' (KeyError)
```

**Debugging Steps:**

1. Check what JSON was actually parsed:
   ```
   intent_analysis: {...actual JSON content...}
   ```

2. Look for missing fields:
   - Should have: `operation`, `reasoning`, `missing_fields` (if clarify), `sql` (if query)
   - Check what's actually there

3. **Fixes to try:**
   - The intent parser prompt might be unclear - check `langgraph_integration/prompts.py`
   - LLM might be ignoring the format requirements
   - Try updating the prompt to be more explicit about required fields

**Checking the Prompt:**

```bash
# View the intent parser prompt
grep -A 50 "INTENT_PARSER_PROMPT" langgraph_integration/prompts.py

# Key line to check:
# Output JSON with fields:
# - operation: "clarify" or "query"
```

---

### Scenario 3: State Management Error

**Symptom:**
```
[parse_intent    ] ... no logs for intent parsing result
[generate_sql    ] [HH:MM:SS.mmm] ❌ Error: intent_analysis is None
```

**Debugging Steps:**

1. Check if `_parse_intent` is even being called:
   - Should see the agent header
   - If not, check the workflow routing

2. Verify the fallback logic:
   - Line 334 in graph_definition.py has default: `{"operation": "query", "requirements": "", "entities": []}`
   - This should prevent None errors

3. **Fixes to try:**
   - Restart the service (may have stale state)
   - Check for concurrent request issues (race conditions)
   - Verify database connection is working

---

## Complete Debugging Checklist

Use this checklist when you encounter the "operation" error:

```
[ ] 1. Run debug_stream.py in a separate terminal
[ ] 2. Submit the problematic query
[ ] 3. Look for "AGENT: parse_intent" header
[ ] 4. Find the error message in parse_intent logs
[ ] 5. Identify which scenario applies:
      [ ] JSON parsing error
      [ ] Missing "operation" field
      [ ] State management issue
[ ] 6. Apply the corresponding fix
[ ] 7. Re-submit the query
[ ] 8. Check if error is resolved
[ ] 9. If not, collect:
      - Exact query that fails
      - Full debug output from parse_intent agent
      - .env settings
      - Recent error logs
```

---

## Example: Complete Debug Session

### Query That Fails:
```json
{
  "messages": [{"role": "user", "content": "how many customers do we have"}],
  "api_key": "supersecretapikey"
}
```

### Expected Debug Output (Success):
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
                    confidence: 0.95
                    reasoning: Count query for customer entity

[generate_sql    ] [14:32:16.200] 🔄 SQL Generated
                    sql: SELECT COUNT(*) FROM dbo.customers
                    reason: Intent: query, Entities: customers
```

### Debug Output (With Error):
```
================================================================================
         AGENT: parse_intent (Activity #1)
================================================================================
[parse_intent    ] [14:32:15.423] 📝 Intent Parsing Started
                    user_message: "how many customers do we have"
                    conversation_turns: 1

[parse_intent    ] [14:32:15.600] ⚠️  Attempt 1 failed: JSON parsing error
                    error: No JSON object found
                    problematic_response: "I'll help you count customers..."

[parse_intent    ] [14:32:15.800] ⚠️  Attempt 2 failed: JSON parsing error
                    error: Expecting value: line 1 column 1
                    problematic_response: [truncated]

[parse_intent    ] [14:32:15.950] ❌ Error parsing intent
                    error_type: intent_parsing_error
                    technical_error: Failed to parse intent after 2 retries
```

---

## Verification Steps

After applying a fix, verify it works:

1. **Check parse_intent logs don't show errors**
2. **Check operation field has a valid value** (query, clarify, etc.)
3. **Check confidence is > 0.5**
4. **Check no technical_error field in logs**

If all pass ✅, the error is fixed!

---

## Common "operation" Query Patterns

These queries work well and should NOT produce errors:

✅ **Simple count queries:**
```
"how many customers do we have"
"count of products"
"total orders"
```

✅ **Filter queries:**
```
"show customers from New York"
"orders in January 2024"
"products under $50"
```

✅ **Schema queries:**
```
"what tables are available"
"show me the database schema"
"what columns do we have"
```

❌ **Complex queries** (may fail, try simpler version):
```
"complex multi-table join with aggregations"
"machine learning prediction model"
```

---

## Next Level: Manual Prompt Testing

If the error persists, you can test the prompt directly:

```bash
# In Python shell
from langgraph_integration.prompts import format_intent_parser_prompt

messages = [{"role": "user", "content": "how many customers do we have"}]
schema = "Available Tables:\n  - dbo.customers (1000 rows)"

prompt = format_intent_parser_prompt(messages, schema)
print(prompt)

# Then manually call GPT-4 with this prompt
# and verify it returns valid JSON with "operation" field
```

---

## Getting Help

When reporting the issue, include:

1. **The exact query** that triggers the error
2. **Full parse_intent agent section** from debug output
3. **Your .env settings** (without API key)
4. **Error message** exactly as shown
5. **Steps to reproduce**

This will help identify the exact cause quickly!

---

## Prevention: Best Practices

To avoid this error in the future:

1. ✅ **Keep queries simple** - Start basic, then add complexity
2. ✅ **Monitor debug stream** - Watch for warnings before errors
3. ✅ **Check API key** - Verify OPENAI_API_KEY before running
4. ✅ **Run health check** - `curl http://localhost:5001/health`
5. ✅ **Read prompt** - Understand what format LLM should return
6. ✅ **Test incrementally** - Add features one at a time

---

Good luck! The debug stream should give you all the information needed to fix this. 🎯