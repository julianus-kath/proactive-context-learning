# 📋 PHASE 9 - EXPECTED LOG OUTPUT

## What You Should See After The Fix

This is the **exact** log sequence you should see when running:

```bash
curl -X POST http://localhost:5001/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: supersecretapikey" \
  -d '{"user_input": "How many customers do we have?"}'
```

---

## Complete Expected Log Sequence

```
════════════════════════════════════════════════════════════════
📚 [INDEX_DATABASE] Indexing database...
════════════════════════════════════════════════════════════════

📚 [INDEX_DATABASE] Checking MCP availability...
📚 [INDEX_DATABASE] ✅ Database indexed, MCP available


════════════════════════════════════════════════════════════════
🧠 [PARSE_INTENT] Parsing intent with IntentParserAgent...
════════════════════════════════════════════════════════════════

🧠 [PARSE_INTENT] User query: "How many customers do we have?"
🧠 [PARSE_INTENT] 🧠 Parsing intent with LLM: How many customers do we have?
🧠 [PARSE_INTENT] ✅ LLM parsed intent: {
    'primary_entities': ['customers'],
    'metrics': ['count'],
    'filters': [],
    'time_window': None,
    'keywords_for_discovery': ['customers'],  ← CRITICAL - NOT EMPTY!
    'confidence': 1.0
}
🧠 [PARSE_INTENT] ✅ Intent parsed successfully:
    operation=query
    entities=['customers']
    keywords_for_discovery=['customers'] ← CRITICAL FOR DISCOVERY
    confidence=1.00
🧠 [PARSE_INTENT] ✅ Intent stored in state


════════════════════════════════════════════════════════════════
🚦 [ROUTE] Routing based on operation: query
════════════════════════════════════════════════════════════════

🚦 [ROUTE]   → Routing to: discovery (query pipeline)


════════════════════════════════════════════════════════════════
🔍 [DISCOVERY] Starting DiscoveryAgent...
════════════════════════════════════════════════════════════════

🔍 [DISCOVERY] Intent check:
🔍 [DISCOVERY]   - intent present? True
🔍 [DISCOVERY]   - keywords_for_discovery: ['customers']  ← SAME AS PARSE_INTENT!
🔍 [DISCOVERY] Invoking discovery subgraph with ainvoke()...

    🔎 [search_candidates_node] Searching for candidates...
    🔎 [search_candidates_node]   Keywords: ['customers']
    📡 MCP TOOL: search_tables with query: customers
    📊 MCP RESULT: 10 candidates found
    
    🔎 [rank_candidates_node] Ranking 10 candidates...
    🔎 [rank_candidates_node] ✅ Top 3 candidates by score
    
    🔎 [filter_to_limit_node] Keeping top 3 candidates
    
    📊 [describe_selected_node] Describing 3 tables...
    📊 [describe_selected_node] ✅ Described: dbo.KHKKunde, dbo.KHKArtikel, dbo.KHKBestellung
    
    📊 [build_schema_snippet_node] Building schema snippet...
    📊 [build_schema_snippet_node] Setting relevant_tables: ['dbo.KHKKunde', 'dbo.KHKArtikel', 'dbo.KHKBestellung']
    
    🔎 [fetch_column_index_node] Fetching column index...

🔍 [DISCOVERY] ✅ Discovery subgraph completed
🔍 [DISCOVERY] Extracting results from discovery subgraph...
🔍 [DISCOVERY]   relevant_tables count: 3
🔍 [DISCOVERY]   candidate_views count: 0
🔍 [DISCOVERY]   tables found: ['dbo.KHKKunde', 'dbo.KHKArtikel', 'dbo.KHKBestellung']
🔍 [DISCOVERY] ✅ Discovery complete: 3 table(s), 0 view(s)


════════════════════════════════════════════════════════════════
🔗 [JOIN_SQL] Starting JoinPlanAndSQLAgent...
════════════════════════════════════════════════════════════════

🔗 [JOIN_SQL] Received from discovery: 3 tables  ← NOT ZERO!
🔗 [JOIN_SQL] Invoking join_sql subgraph with ainvoke()...

    🔗 [plan_join_node] Planning join...
    🔗 [plan_join_node] No joins needed (single table query)
    
    📄 [generate_sql_node] Generating SQL...
    📄 [generate_sql_node] Query type: aggregate
    📄 [generate_sql_node] Generated SQL:
       SELECT COUNT(*) as customer_count FROM dbo.KHKKunde
    
    ✅ [validate_sql_node] Validating SQL...
    ✅ [validate_sql_node] ✅ SQL valid

🔗 [JOIN_SQL] ✅ join_sql subgraph completed
🔗 [JOIN_SQL] ✅ JoinSQL complete: 95 char SQL
🔗 [JOIN_SQL]   SQL preview: SELECT COUNT(*) as customer_count FROM dbo.KHKKunde


════════════════════════════════════════════════════════════════
⚡ [EXEC_RECOVERY] Starting ExecAndRecoveryAgent...
════════════════════════════════════════════════════════════════

⚡ [EXEC_RECOVERY] Received SQL: SELECT COUNT(*) as customer_count FROM dbo.KHKKunde
⚡ [EXEC_RECOVERY] Invoking exec_recovery subgraph with ainvoke()...

    ⚡ [execute_node] Executing query...
    ⚡ [execute_node] Query: SELECT COUNT(*) as customer_count FROM dbo.KHKKunde
    📡 MCP TOOL: query_bounded with TOP 1000, timeout 30s
    ✅ MCP RESULT: Query executed successfully
    ✅ [execute_node] ✅ Execution successful: 1 rows

⚡ [EXEC_RECOVERY] ✅ exec_recovery subgraph completed
⚡ [EXEC_RECOVERY] ✅ Execution complete: 1 rows, 234ms


════════════════════════════════════════════════════════════════
📝 [ANSWER] Starting AnswerAgent...
════════════════════════════════════════════════════════════════

📝 [ANSWER] Formatting answer...
📝 [ANSWER] Result: [{
    'customer_count': 12543
}]
📝 [ANSWER] ✅ Answer generated: "We have 12,543 customers in our database."


════════════════════════════════════════════════════════════════
✅ WORKFLOW COMPLETE
════════════════════════════════════════════════════════════════

Final Response:
{
  "status": "success",
  "answer": "We have 12,543 customers in our database.",
  "query": "How many customers do we have?",
  "tables_used": ["dbo.KHKKunde"],
  "execution_time_ms": 234,
  "rows_returned": 1
}
```

---

## Key Lines To Look For

### ✅ GOOD SIGN #1: Intent parsing works
```
🧠 [PARSE_INTENT] keywords_for_discovery=['customers']
```
*Should NOT be empty `[]`*

### ✅ GOOD SIGN #2: Discovery receives same keywords
```
🔍 [DISCOVERY] keywords_for_discovery: ['customers']  ← SAME AS ABOVE
```
*Should match parse_intent output*

### ✅ GOOD SIGN #3: Discovery finds reasonable number of candidates
```
🔍 [DISCOVERY] relevant_tables count: 3
```
*Should be 3-10, NOT 943*

### ✅ GOOD SIGN #4: Join SQL receives tables
```
🔗 [JOIN_SQL] Received from discovery: 3 tables
```
*Should NOT be zero*

### ✅ GOOD SIGN #5: SQL is generated
```
🔗 [JOIN_SQL] ✅ JoinSQL complete: 95 char SQL
```
*Should have content, not empty*

### ✅ GOOD SIGN #6: Execution succeeds
```
⚡ [EXEC_RECOVERY] ✅ Execution complete: 1 rows, 234ms
```
*Should show successful execution*

### ✅ GOOD SIGN #7: Natural answer
```
📝 [ANSWER] ✅ Answer generated: "We have 12,543 customers..."
```
*Should be proper English, not error*

---

## What BAD Logs Look Like

### ❌ BAD SIGN #1: Intent parsing failure
```
🧠 [PARSE_INTENT] keywords_for_discovery: []  ← EMPTY!
```
*This means intent parser failed*

### ❌ BAD SIGN #2: Discovery gets wrong keywords
```
🔍 [DISCOVERY] keywords_for_discovery: ['how', 'many', 'customers', 'do', 'we', 'have']
```
*Too many words, not semantic*

### ❌ BAD SIGN #3: Too many candidates
```
🔍 [DISCOVERY] relevant_tables count: 943
```
*Means discovery is returning all tables, not filtered*

### ❌ BAD SIGN #4: Join SQL has no tables
```
🔗 [JOIN_SQL] Received from discovery: 0 tables  ← ZERO!
🔗 [JOIN_SQL] ❌ CRITICAL: No relevant_tables from discovery!
```
*Downstream agent won't run*

### ❌ BAD SIGN #5: SQL generation fails
```
🔗 [JOIN_SQL] ❌ Error from join_sql subgraph: NO_TABLES
```
*Can't generate without tables*

### ❌ BAD SIGN #6: Execution fails
```
⚡ [EXEC_RECOVERY] ❌ Execution failed: SYNTAX_ERROR
```
*Query had an error*

### ❌ BAD SIGN #7: Error fallback
```
📝 [ANSWER] "I'm sorry, I couldn't answer your question. Please write SQL manually."
```
*Error fallback message, not good*

---

## Log Interpretation Guide

### If keywords_for_discovery is EMPTY
- Intent parser failed
- Solution: Check if line 170 has `await self.llm.ainvoke()`

### If keywords are WRONG (too many, function words)
- Intent parser ran but gave bad output
- Solution: Check LLM prompt in intent_parser

### If discovery finds 943 candidates
- Keywords are being re-extracted somewhere
- Solution: Check discovery `_extract_keywords()` method

### If join_sql has no tables
- Either discovery failed or didn't pass state
- Solution: Check discovery returns relevant_tables

### If SQL is empty
- Join planning failed
- Solution: Check join_sql requirements

### If execution fails
- SQL might have errors
- Solution: Check SQL in logs, try running manually

### If final answer is error message
- Some upstream step failed
- Solution: Look for first ❌ in logs above

---

## Quick Grep Commands

To find specific issues in logs:

```bash
# Find intent keywords
tail -100 /path/to/logs | grep "keywords_for_discovery"

# Find if discovery found candidates
tail -100 /path/to/logs | grep "relevant_tables count"

# Find if join_sql ran
tail -100 /path/to/logs | grep "\[JOIN_SQL\]"

# Find if execution succeeded
tail -100 /path/to/logs | grep "Execution complete"

# Find all errors
tail -100 /path/to/logs | grep "❌"

# Find all agents that ran
tail -100 /path/to/logs | grep "Starting\|✅ complete"
```

---

## Performance Expectations

### Timing
- INDEX_DATABASE: <500ms
- PARSE_INTENT: 1-2s (LLM call)
- DISCOVERY: 1-2s (MCP calls, scoring)
- JOIN_SQL: 1-2s (LLM planning)
- EXEC_RECOVERY: 100-500ms (Query execution)
- ANSWER: <500ms (Formatting)

**Total: 4-8 seconds typical**

If any step is much slower, something might be wrong.

---

## Next Steps

1. Run the query above
2. Save the log output
3. Check it matches the "GOOD SIGNS" section
4. If all ✅, you're done!
5. If any ❌, refer to the "What BAD Logs Look Like" section

Good luck! 🚀
