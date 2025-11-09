# Discovery Agent Deep Dive: Finding the Right Tables (Or Not)
**Status**: Architectural Analysis & Audit | Date: November 2025

> **Quick Answer**: It works for simple queries, falls apart on ambiguous intent or weak keywords.

---

## EXECUTIVE SUMMARY

The Discovery Agent is supposed to be the "gateway" to successful queries. It's also the **single most critical failure point** in the system.

| Aspect | Status | Problem |
|--------|--------|---------|
| **Search Strategy** | Views-first, fallback to tables ✓ | But views have stale/missing data |
| **Candidate Ranking** | Semantic scoring active ✓ | But dominated by text similarity (0.45 weight) |
| **Candidate Filtering** | Limited to ≤3 tables ✓ | But sometimes all 3 are wrong |
| **Column Fetching** | Implemented ✓ | But fetches happen AFTER schema building (too late) |
| **Error Handling** | Present ✓ | But ambiguity → empty result → silent failure |
| **Adaptive Discovery** | Strategic mode for complex queries ✓ | But heuristics are hardcoded (customer + sum = always KHKAdressen) |

**Root Issues**:
1. **Ignores Intent Confidence**: Discovery proceeds even when intent parser says 0.45 confidence
2. **Text-Similarity Dominated**: "Customer" matches "CustomerArchive" equally as "Customers"
3. **No Semantic Context**: Doesn't understand "I want active customers, not historical"
4. **Silent Fallback Chains**: If primary search fails, falls back to per-keyword searches (can return garbage)
5. **Candidate Ranking is Static**: Same weights for every query type (count vs. trend vs. growth)

---

## PART I: DISCOVERY AGENT ARCHITECTURE

### A. High-Level Flow

```
DiscoveryAgent (LangGraph subgraph)
├─ Node 1: search_candidates
│   ├─ Extract keywords from intent
│   ├─ Check if strategic query (growth_analysis, trend, etc.)
│   ├─ IF strategic: Call _strategic_query_discovery()
│   ├─ ELSE: Call search_tables() + search_views()
│   └─ Deduplicate + rank candidates
│
├─ Node 2: rank_candidates
│   ├─ Filter by semantic score > 0.05
│   └─ Keep unique candidates
│
├─ Node 3: filter_to_limit
│   ├─ Keep ≤3 candidates
│   └─ Store in state["candidate_views"]
│
├─ Node 4: describe_selected
│   ├─ For each candidate, call describe_table()
│   ├─ Extract columns, FKs, row counts
│   └─ Build table metadata cache
│
├─ Node 5 (Conditional): explore_date_columns
│   ├─ IF query needs date filtering
│   ├─ THEN search for date columns
│   └─ ELSE skip
│
├─ Node 6: build_schema_snippet
│   ├─ Combine descriptions into compact schema
│   └─ Format for downstream agents
│
└─ Node 7: fetch_column_index
    ├─ For each table, fetch exact column names
    ├─ Prevents hallucination in SQL generation
    └─ Store in state["column_index"]
```

**Input**: `{user_input, intent, session_described_tables}`  
**Output**: `{relevant_tables, schema_snippet, candidate_views, column_index, error_info}`

---

### B. Node-by-Node Analysis

#### Node 1: `search_candidates`

**Purpose**: Find initial set of table/view candidates matching intent

**Core Logic**:
```python
async def _search_candidates_node(self, state: BaseState) -> BaseState:
    user_input = state.get("user_input", "")
    intent = state.get("intent", {})
    
    # Extract search keywords
    keywords = self._extract_keywords(user_input, intent)
    
    if not keywords:
        error = {
            "type": "DISCOVERY_ERROR",
            "message": "Could not extract search keywords",
        }
        return {**state, "error_info": error}
    
    # Check for strategic queries
    required_action = intent.get("required_action", "")
    strategic_actions = ["growth_analysis", "department_productivity", "comparative_analysis"]
    
    candidates: List[Dict[str, Any]] = []
    
    if required_action in strategic_actions:
        logger.info(f"🔍 [STRATEGIC] Using strategic discovery for {required_action}")
        strategic_candidates = await self._strategic_query_discovery(user_input, intent)
        candidates.extend(strategic_candidates)
    else:
        # Standard search for simple queries
        query_str = " ".join(keywords)
        
        # Search tables
        try:
            result = await self.mcp.search_tables(query_str, page=1, page_size=10, intent_data=intent)
            parsed = self._parse_search_result(result)
            candidates.extend(parsed)
        except Exception as e:
            logger.warning(f"  Joined search (tables) failed: {e}")
        
        # Search views (views-first strategy)
        try:
            vres = await self.mcp.search_views(query_str, page=1, page_size=10, include_empty=False)
            vparsed = self._parse_search_result(vres)
            for v in vparsed:
                v["is_view"] = True
            candidates.extend(vparsed)
        except Exception as e:
            logger.warning(f"  Joined search (views) failed: {e}")
    
    # Deduplicate by table name
    seen = set()
    unique_candidates = []
    for c in candidates:
        table_name = c.get("table_name") or c.get("name") or c.get("full_name", "")
        if table_name not in seen and table_name:
            seen.add(table_name)
            unique_candidates.append(c)
    
    # Filter for semantic relevance (> 0.05)
    semantic_candidates = [c for c in unique_candidates if c.get("relevance_score", 0) > 0.05]
    
    if not unique_candidates or not semantic_candidates:
        logger.warning(f"⚠️  No semantically relevant tables found")
        state["candidate_views"] = []
        return state
    
    state["candidate_views"] = unique_candidates
    return state
```

**Search Strategy**:
1. **Joined Keywords**: Combine all keywords into single string, search once (fast)
2. **Views First**: Prefer pre-joined views over raw tables
3. **Deduplication**: Remove duplicates by table name
4. **Semantic Filtering**: Only keep results with relevance_score > 0.05

**Issues**:

1. **Ignores Intent Confidence**:
```python
# Current code:
intent = state.get("intent", {})
keywords = self._extract_keywords(user_input, intent)  # Uses keywords regardless of confidence

# Should be:
confidence = intent.get("confidence", 1.0)
if confidence < 0.5:
    # Return error or ask for clarification
    return {"error": "AMBIGUOUS_QUERY", ...}
```

2. **Keyword Extraction is Primitive**:
```python
def _extract_keywords(self, user_input: str, intent: dict) -> List[str]:
    """Extract keywords from intent + user_input."""
    # Combines intent keywords + user input text
    keywords = intent.get("keywords_for_discovery", [])
    # Then adds more from user_input (can double-extract!)
    additional = self._extract_basic_keywords(user_input)
    return list(set(keywords + additional))
```

This can result in duplicate keyword extraction and dilution of signal.

3. **Strategic Discovery is Hardcoded**:
```python
# Minimal targeted enrichment for customer-sum queries
if wants_sum and wants_customers:
    if all("khkadressen" not in (c.get("table_name","") or "").lower() for c in unique_candidates):
        logger.debug("  Enriching with explicit KHKAdressen lookup")
        enr = await self.mcp.search_tables("KHKAdressen", page=1, page_size=3, intent_data=intent)
        # ...
```

This works for **this specific scenario** but won't generalize. What if user wants "top 10 products by sales"? No hardcoded logic for that.

---

#### Node 2: `rank_candidates`

**Purpose**: Rank and filter candidates

**Current Implementation**:
```python
def _rank_candidates_node(self, state: BaseState) -> BaseState:
    candidates = state.get("candidate_views", [])
    
    if not candidates:
        return state
    
    # Candidates already ranked by MCP (semantic ranking)
    # Just ensure they're sorted
    candidates.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    
    state["candidate_views"] = candidates
    return state
```

**Problem**: This is a **pass-through node**. All heavy lifting is done by MCP's semantic ranker. If MCP ranking is wrong, no recovery.

**What it SHOULD do**:
- Re-rank based on intent context
- Penalize archive/historical tables if not explicitly requested
- Boost primary tables (fact tables > dimension tables)
- Consider entity cardinality (prefer 1:1 over 1:N for simple counts)

---

#### Node 3: `filter_to_limit`

**Purpose**: Keep only ≤3 candidates

**Implementation**:
```python
def _filter_to_limit_node(self, state: BaseState) -> BaseState:
    candidates = state.get("candidate_views", [])
    
    # Keep only top 3
    limited = candidates[:self.max_candidates_to_describe]
    
    state["candidate_views"] = limited
    return state
```

**Issue 1**: If top 3 are all equally wrong (score 0.4, 0.39, 0.38), system proceeds anyway.  
**Issue 2**: No clustering by "domain" (e.g., if all 3 are views but none are base tables, alert).  
**Issue 3**: No check for "confidence disparity" (if scores are 0.9, 0.1, 0.1, should treat first as primary).

---

#### Node 4: `describe_selected`

**Purpose**: Fetch detailed metadata for selected tables

**Implementation**:
```python
async def _describe_selected_node(self, state: BaseState) -> BaseState:
    candidates = state.get("candidate_views", [])
    session_described_tables = state.get("session_described_tables", {})
    
    schema_parts = []
    
    for candidate in candidates:
        table_fqn = candidate.get("full_name") or candidate.get("table_name")
        
        # Check cache first
        if table_fqn in session_described_tables:
            schema_parts.append(session_described_tables[table_fqn])
            continue
        
        # Fetch metadata from MCP
        try:
            desc_result = await self.mcp.describe_table(table_fqn)
            # Parse and cache
            parsed_desc = self._parse_describe_result(desc_result)
            session_described_tables[table_fqn] = parsed_desc
            schema_parts.append(parsed_desc)
        except Exception as e:
            logger.warning(f"Failed to describe {table_fqn}: {e}")
    
    state["session_described_tables"] = session_described_tables
    return state
```

**Issue**: This happens BEFORE `fetch_column_index`. So SQL generator will have `schema_snippet` but NO `column_index`, leading to hallucination.

---

#### Node 6: `build_schema_snippet`

**Purpose**: Combine descriptions into compact schema

**Output Format** (expected by JoinSQL):
```
Table 1: dbo.Customers
Columns: CustomerID (int, PK), Name (nvarchar), RevenueLTM (decimal)

Table 2: dbo.Orders
Columns: OrderID (int, PK), CustomerID (int, FK), Amount (decimal)
```

**Issue**: Column list is truncated (only top 5-10 columns). If SQL generator needs a column not in snippet, it hallucinates.

---

#### Node 7: `fetch_column_index` (Phase 7.2)

**Purpose**: Fetch exact column names from Scout Catalog

**Implementation**:
```python
async def _fetch_column_index_node(self, state: BaseState) -> BaseState:
    """PHASE 7.2: Fetch indexed columns from Scout Catalog to prevent hallucination."""
    relevant_tables = state.get("relevant_tables", [])
    
    column_index = {}
    for table_fqn in relevant_tables:
        try:
            columns = await self.mcp.get_column_index(table_fqn)
            column_index[table_fqn] = columns
        except Exception as e:
            logger.warning(f"Could not fetch column index for {table_fqn}: {e}")
    
    state["column_index"] = column_index
    return state
```

**Problem**: This is called LAST (Node 7), after schema building (Node 6). So SQL generation (which happens in a later agent) has access to `column_index`, but by then decisions have been made.

**Better**: Fetch column index in Node 4, pass to `build_schema_snippet`.

---

## PART II: CRITICAL BLIND SPOTS

### Blind Spot 1: No Confidence-Based Early Exit

**Current**:
```python
# Node 1 receives:
intent = {
    "confidence": 0.45,  # Low!
    "keywords_for_discovery": ["whatever"],
}

# Node 1 does:
keywords = intent.get("keywords_for_discovery", [])
result = await self.mcp.search_tables(" ".join(keywords), ...)

# Proceeds regardless of confidence
```

**Expected**: If `intent.confidence < 0.5`, don't search MCP. Ask user instead.

---

### Blind Spot 2: Views Might Be Stale

**Problem**: Scout Catalog is TTL'd at 7 days. If a view definition changed, Discovery still uses old definition.

**Example**:
```
Day 1: View "v_ActiveCustomers" shows [CustomerID, Name, Email]
Day 8: View definition changed to [CustomerID, Name, Email, Status]

Discovery (Day 8): Still thinks view has 3 columns
SQL Generator: Tries to SELECT Status → Column not found (or uses old definition)
```

**Current Mitigation**: None. Views are assumed fresh.

---

### Blind Spot 3: All 3 Candidates Can Be Wrong

**Scenario**:
```
Query: "Revenue by customer"

Candidates (after ranking):
1. v_CustomerSalesReport (score 0.65) ← Best semantic match, but outdated
2. Orders (score 0.60) ← Has OrderID, CustomerID, Amount
3. SalesInvoices (score 0.55) ← Duplicate data from Orders

Discovery picks all 3 and describes them.
JoinSQL tries to join all 3 → Complex, ambiguous join plan.
ExecRecovery executes → Maybe works, maybe returns wrong totals.
```

**Why**: Ranking algorithm doesn't distinguish "primary" from "supporting" tables.

---

### Blind Spot 4: No Semantic Re-Ranking Based on Intent

**Current**: Ranking is static (based on text similarity, role coverage, view bonus).

**Problem**: For "count customers", we want `Customers` table.  
For "top 10 revenue generators", we want `Orders` or `SalesInvoices` table.  
But ranking algorithm doesn't change based on metric type.

**Example**:
```python
# All queries use same ranking weights:
score = (
    0.45 * text_sim           # Text similarity (Levenshtein)
    + 0.25 * role_coverage    # Column role hints
    + 0.15 * entity_match     # Fuzzy keyword match
    + 0.10 * has_rows_bonus   # Non-empty tables preferred
    + 0.05 * is_view_bonus    # Views get boost
)

# But for "count customers", should be:
# Boost tables with:
#   - Primary key (CustomerID)
#   - Name/Description columns
#   - NOT historical data

# For "total revenue", should be:
# Boost tables with:
#   - Amount/Revenue columns
#   - Date columns (for filtering)
#   - Orders or Sales tables (domain knowledge)
```

Current ranking has no such context.

---

### Blind Spot 5: Fallback Chains Can Return Garbage

**Current Code** (lines 205-238):
```python
# Fallback per-keyword searches DISABLED to prevent search spam

# Instead, if primary search fails, try "business-pattern" fallback
# (now also disabled)

# So if no candidates found:
state["candidate_views"] = []
return state  # ← Silent empty return
```

**Previous Version** (disabled):
```python
for keyword in keywords:
    result = await self.mcp.search_tables(keyword, page=1, page_size=10)
    candidates.extend(parsed)
# Can result in 100+ candidates, most irrelevant
```

**Current approach**: Avoid search spam by NOT doing fallback.  
**Problem**: Now if keywords are bad, Discovery silently returns empty results.

---

## PART III: HOW RANKING ACTUALLY WORKS

### The MCP Ranking Algorithm

From `MCP_SERVER_ARCHITECTURE.md`:
```python
score = (
    0.45 * text_sim        # Levenshtein distance (normalized)
    + 0.25 * role_coverage # % of query roles covered by column roles
    + 0.15 * entity_match  # Fuzzy keyword match + component matching
    + 0.10 * has_rows_bonus # Table is non-empty
    + 0.05 * is_view_bonus # View gets preference
)
```

**Example Calculation**:
```
Query: "customers"

Table 1: dbo.Customers
  - text_sim: 1.0 (exact match)
  - role_coverage: 0.8 (has id, name, email → good coverage)
  - entity_match: 1.0 (exact keyword match)
  - has_rows: 1.0 (table has 10k rows)
  - is_view: 0 (base table)
  Score = 0.45*1.0 + 0.25*0.8 + 0.15*1.0 + 0.10*1.0 + 0.05*0 = 0.895

Table 2: dbo.CustomerArchive
  - text_sim: 0.85 (substring match)
  - role_coverage: 0.7 (has id, name → missing email)
  - entity_match: 0.85 (fuzzy match on "customers" → "archive")
  - has_rows: 1.0 (has data)
  - is_view: 0
  Score = 0.45*0.85 + 0.25*0.7 + 0.15*0.85 + 0.10*1.0 + 0.05*0 = 0.698

Table 3: v_CustomerReport
  - text_sim: 0.9 (substring match)
  - role_coverage: 0.9 (well-designed view)
  - entity_match: 0.9 (close match)
  - has_rows: 1.0
  - is_view: 1 (gets 0.05 bonus)
  Score = 0.45*0.9 + 0.25*0.9 + 0.15*0.9 + 0.10*1.0 + 0.05*1 = 0.89

Ranking: [Customers (0.895), v_CustomerReport (0.89), CustomerArchive (0.698)]
```

**Insight**: Text similarity dominates (0.45 weight). If query keyword matches multiple tables equally, tie goes to role_coverage.

**Problem**: Doesn't account for:
- Temporal context (archive tables shouldn't be default)
- Query intent (count vs. trend vs. join)
- Domain hierarchy (master tables vs. transactional tables)

---

## PART IV: WHAT'S ACTUALLY WORKING

### ✅ Strengths

1. **Views-First Strategy**:
   - Prefers pre-joined views (less ambiguity)
   - Falls back to base tables if views don't cover intent
   - Smart for complex queries

2. **Deduplication**:
   - Prevents duplicate descriptions
   - Saves latency

3. **Column Indexing (Phase 7.2)**:
   - Fetches exact column names from Scout
   - Prevents SQL generator from hallucinating columns
   - Good safeguard!

4. **Session Caching**:
   - Caches table descriptions across nodes
   - Avoids re-describing same table multiple times
   - ~50-100ms savings per describe

5. **Semantic Filtering**:
   - Only returns tables with relevance_score > 0.05
   - Avoids obvious garbage matches

---

## PART V: WHAT WOULD MAKE IT BETTER

### Quick Wins (Phase 10b)
1. **Confidence Check**: If intent confidence < 0.5, ask user instead of searching
2. **Candidate Clustering**: If top 3 candidates have similar scores, show ambiguity
3. **Archive Filtering**: Explicitly penalize historical/archive tables
4. **Intent-Aware Re-Ranking**: Boost tables based on metric type (count → primary tables, sum → fact tables)

### Medium-Term (Phase 11)
1. **Domain Knowledge**: Mark tables as fact/dimension/archive in catalog
2. **Cardinality Awareness**: Prefer 1:N tables for aggregations, 1:1 for lookups
3. **Temporal Filtering**: Track table freshness, penalize stale data
4. **Adaptive TTL**: Different cache TTL for views vs. base tables

### Long-Term (Phase 12+)
1. **Query Pattern Learning**: Track which tables work best for different query types
2. **User Feedback Loop**: If query fails, learn that this table wasn't right
3. **Schema Evolution Detection**: Alert if view definition changed since cache TTL

---

## PART VI: TESTING & VALIDATION

### Current Test Coverage
```
✅ test_mcp_health_check: MCP is reachable
✅ test_search_tables_basic: Can search tables
✅ test_describe_table_basic: Can describe table
❌ test_ambiguous_discovery: [NO TEST]
❌ test_low_confidence_discovery: [NO TEST]
❌ test_ranking_by_intent: [NO TEST]
❌ test_archive_table_filtering: [NO TEST]
❌ test_german_discovery: [NO TEST]
```

---

## SUMMARY: Critical Findings

| Issue | Severity | Impact | Fix Effort |
|-------|----------|--------|-----------|
| Ignores intent confidence | 🔴 Critical | Proceeds with bad intent | 30 mins |
| No semantic re-ranking | 🟠 High | Wrong tables picked for complex queries | 2 hours |
| Views might be stale | 🟠 High | Silent data freshness issues | 1 day |
| All 3 candidates can be wrong | 🟡 Medium | Ambiguity not detected until downstream | 2 hours |
| Fallback chains disabled | 🟡 Medium | Silent failures instead of graceful fallback | 1 hour |
| Column index fetched too late | 🟡 Medium | SQL generator still hallucinates | 1 hour |

---

## RECOMMENDATION FOR PHASE 10

**Phase 10a**: Implement Result Validator (catches 0-row garbage)

**Phase 10b**: Fix Discovery Agent:
1. Add confidence check (early exit if < 0.5)
2. Add archive table filtering
3. Re-order `fetch_column_index` to happen earlier
4. Implement intent-aware re-ranking

This makes Discovery more robust without major refactoring.

---

*End of Discovery Agent analysis. Pair with Intent Parser audit for complete picture.*