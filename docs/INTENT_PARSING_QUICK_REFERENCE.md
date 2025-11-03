# Intent Parsing: Quick Reference Guide

## 🎯 The Rule

**Intent parsing happens ONLY in LangGraph.**

```
LangGraph (macOS) = Semantic Reasoning ← Parse intent here ✅
MCP Server (Windows) = Pure Tool Layer ← NO parsing ❌
```

---

## 📍 Where to Use Each Component

### ✅ DO: Use `IntentParserAgent` in LangGraph

**Location:** `langgraph_integration/agents/intent_parser/agent.py`

**When:**
- You're in the LangGraph orchestrator
- You need to understand user intent
- You're building discovery keywords
- You need structured parsing (entities, metrics, filters)

**Example:**
```python
from langgraph_integration.agents.intent_parser.agent import IntentParserAgent

parser = IntentParserAgent()
intent = await parser.parse("How many customers do we have?")

# Returns: ParsedIntent {
#   keywords_for_discovery: ["customer"],
#   primary_entities: ["customers"],
#   metrics: ["count"],
#   confidence: 0.95
# }

# Use the parsed intent:
keywords = intent["keywords_for_discovery"]  # ["customer"]
entities = intent["primary_entities"]  # ["customers"]
```

### ❌ DON'T: Use `mcp_server.intent_parser` directly

**Location:** `mcp_server/intent_parser.py` (deprecated for main flow)

**Why not:**
- MCP should never parse natural language
- Creates duplicate parsing
- Causes plural entity bugs
- Violates architecture (repo.md)

**Only used in:**
- Diagnostic tests (for verification that component exists)
- Archive/deprecated code
- Historical reference

---

## 🔄 Information Flow

### Correct: Single Parse in LangGraph

```
┌─────────────────────────────────────────┐
│ LangGraph Orchestrator (macOS)          │
├─────────────────────────────────────────┤
│                                         │
│  1. parse_intent_node()                 │
│     ├─ IntentParserAgent.parse()        │
│     │  └─ Query: "Show me customers"    │
│     │  ← Returns: ParsedIntent ✅       │
│     └─ state["intent"] = ParsedIntent   │
│                                         │
│  2. discovery_node()                    │
│     ├─ Extract: intent.keywords_for_discovery  │
│     │ ["customer"]                      │
│     ├─ Call MCP: search_tables("customer")     │
│     │ (NO re-parsing at MCP)            │
│     └─ Get ~30 customer tables ✅       │
│                                         │
│  3. join_sql_node()                     │
│     └─ Build query from clean schema    │
│                                         │
│  4. exec_recovery_node()                │
│     └─ Execute safely                   │
│                                         │
│  5. answer_node()                       │
│     └─ Format natural language          │
│                                         │
└─────────────────────────────────────────┘
         ↓
    [MCP Server] (Pure execution tool)
    - search_tables(keyword)
    - describe_table(fqtn)
    - query_bounded(sql)
    (NO parsing, NO reasoning)
```

### Incorrect: Double Parse ❌

```
Query
 ├─→ LangGraph IntentParser ← Parse #1
 └─→ MCP IntentParser ← Parse #2 ❌ WRONG!
     └─→ Plural bug occurs
```

---

## 🧪 Testing Intent Parsing

### Test the LangGraph Parser

```python
import asyncio
from langgraph_integration.agents.intent_parser.agent import IntentParserAgent

async def test_parser():
    parser = IntentParserAgent()
    
    # Test plural forms
    result = await parser.parse("How many customers do we have?")
    assert "customer" in result["keywords_for_discovery"]
    assert result["metrics"] == ["count"]
    
    # Test JOIN intent
    result = await parser.parse("Show me orders with customer details")
    assert "order" in result["keywords_for_discovery"]
    assert "customer" in result["keywords_for_discovery"]
    
    print("✅ All tests passed")

asyncio.run(test_parser())
```

### Verify MCP Doesn't Parse

```bash
# Should return NO results (MCP doesn't import IntentParser anymore)
grep -r "from mcp_server.intent_parser" mcp_server/ --include="*.py"

# Should return NOTHING
```

---

## 📋 Common Scenarios

### Scenario 1: Adding a New Agent

**Question:** "Where should I parse intent?"
**Answer:** In LangGraph. Never in MCP.

```python
# ✅ DO THIS (in LangGraph agent)
from langgraph_integration.agents.intent_parser.agent import IntentParserAgent

intent = await parser.parse(user_input)

# ❌ DON'T DO THIS (in MCP or anywhere else)
from mcp_server.intent_parser import IntentParser
parser = IntentParser()
parsed = parser.parse(query)
```

### Scenario 2: Adding a New Discovery Tool

**Question:** "Should the MCP tool parse the query?"
**Answer:** No. Receive already-parsed entities from LangGraph.

```python
# ✅ DO THIS
async def search_tables(query: str, entities: List[str] = None):
    """Search by already-parsed entities (from LangGraph)."""
    # entities already cleaned by LangGraph IntentParserAgent
    ranked = ranker.rank_tables(entities, intent_operations=[])

# ❌ DON'T DO THIS
async def search_tables(query: str):
    """Don't parse here!"""
    parser = IntentParser()  # ❌ WRONG!
    parsed = parser.parse(query)
```

### Scenario 3: Testing Discovery Results

**Question:** "Why am I getting all 943 tables?"
**Answer:** Check if MCP is doing double parsing.

```python
# Debug checklist:
1. Check MCP logs: "Intent parsed:" should NOT appear in MCP
2. Check LangGraph logs: "Intent parsed:" should appear ONCE
3. Check discovery_tools.py: Should NOT import IntentParser
4. Check intent.keywords_for_discovery: Should be clean (no "how", "many")
5. Restart services: Kill both mcp_server and orchestrator
```

---

## 🏗️ Architecture Rules

| Component | Role | Parse Intent? | Reasoning? |
|-----------|------|---|---|
| **LangGraph** | Agent orchestration | ✅ YES | ✅ YES |
| **IntentParserAgent** | Semantic analysis | ✅ YES | N/A |
| **DiscoveryAgent** | Find tables | ❌ NO | ✅ Uses parsed intent |
| **MCP Server** | Tool execution | ❌ NO | ❌ NO |
| **discovery_tools.py** | MCP discovery | ❌ NO | ❌ NO |
| **table_ranker.py** | Ranking algorithm | ❌ NO | ❌ NO |

---

## 📚 Related Files

### Core Intent Parsing
- `langgraph_integration/agents/intent_parser/agent.py` — LLM-based parser ✅
- `langgraph_integration/agents/intent_parser/__init__.py` — Exports

### Discovery (Uses Parsed Intent)
- `langgraph_integration/agents/discovery/agent.py` — Uses `intent.keywords_for_discovery`
- `langgraph_integration/mcp_client.py` — MCP client (no parsing)

### Deprecated (Archive Only)
- `mcp_server/intent_parser.py` — Old regex-based parser ❌
- `archive/monolithic_workflow/` — Old system used this

---

## ✨ Key Takeaway

**One Parse Rule:**
- Intent parsing happens ONCE, in LangGraph, before all other operations
- MCP receives pre-parsed results and just executes
- If you're calling intent parsing in MCP, you're doing it wrong

**Quick Check:**
```bash
# Run this to verify architecture is correct:
bash DEPLOY_INTENT_ARCHITECTURE_FIX.sh
```

---

**Last Updated:** Phase 9
**Status:** ✅ Active