# ADR 0015: Semantic Table Ranking for Autonomous Query Execution

**Date:** 2024  
**Status:** ACCEPTED  
**Context:** Phase 7.1 Enhancement  

## Problem

The Phase 7 answer-first pipeline required selecting which database tables to query based on natural language user input. The original approach had limitations:

1. **Binary decisions** - "Is this table relevant?" (yes/no) with no confidence scoring
2. **Heuristic-dependent** - Relied on table name patterns and column hints
3. **Database coupling** - Required querying column metadata during ranking
4. **Scalability** - Linear O(n) database queries per ranking request
5. **No semantic awareness** - Couldn't distinguish between "customer" as name vs. foreign key

## Decision

Implement **Semantic Table Ranker** - A multi-dimensional scoring system that:

1. **Scores relevance** - 0.0 to 1.0 confidence for each table
2. **Uses cached metadata** - Consumes Scout Mode pre-computed types
3. **Applies intent-aware logic** - Different scoring for AGGREGATE vs. TREND
4. **Ranks deterministically** - Consistent ordering for same input
5. **Provides reasoning** - Explains why each table was selected

### Ranking Dimensions

#### 1. Entity Matching (Weight: 1.0)
```
Query: "Show me sales by customer"
Entities: ["sales", "customer"]

Scores:
- dbo.Sales:        1.0 (exact match on "sales")
- dbo.Customers:    1.0 (exact match on "customer")
- dbo.SalesDetail:  0.8 (entity match, full word)
- dbo.WebsalES:     0.6 (substring match)
- dbo.Orders:       0.0 (no match)
```

#### 2. Type Compatibility (Weight: 0.3-0.5)
Based on intent operations:

**For AGGREGATE (sum, count, avg):**
```
Query: "Total revenue by product"
Operations: ["sum"]
Intent: AGGREGATE

Scores:
- dbo.Sales (numeric_columns: ["revenue", "amount"]):     +0.3
- dbo.Orders (numeric_columns: ["total", "quantity"]):    +0.3
- dbo.Customers (numeric_columns: []):                   +0.0
```

**For TREND (monthly, yearly, trend):**
```
Query: "Sales trend by month"
Operations: ["trend"]
Intent: TREND

Scores:
- dbo.Sales (date_columns: ["sale_date", "created_at"]):  +0.3
- dbo.Orders (date_columns: ["order_date"]):             +0.3
- dbo.Inventory (date_columns: []):                      +0.0
```

#### 3. Fuzzy Matching (Weight: 0.4)
For partial matches:

```
Query Entity: "order"
Candidate: "dbo.Orders"

Similarity: 0.95 * 0.4 = 0.38
```

#### 4. Foreign Key Connectivity (Weight: 0.1)
Tables with more FKs are more likely to be central:

```
Scores:
- dbo.Sales (fk_count: 3):           +0.1 * min(3/5, 1.0) = +0.06
- dbo.Customers (fk_count: 0):       +0.0
- dbo.OrderItems (fk_count: 4):      +0.1 * min(4/5, 1.0) = +0.08
```

#### 5. Table Size (Weight: 0.05)
Larger tables more likely to be central:

```
Scores:
- dbo.Sales (rows: 500k):            +0.05 * min(500k/100k, 1.0) = +0.05
- dbo.Customers (rows: 10k):         +0.05 * min(10k/100k, 1.0) = +0.005
```

### Final Ranking Formula

```
Score = Entity Match (0-1.0)
      + Type Compatibility (0-0.5)
      + Fuzzy Match (0-0.4)
      + FK Bonus (0-0.1)
      + Size Factor (0-0.05)
      
Maximum: 3.05 (capped at 1.0 in final ranking)
```

## Example: Full Ranking Execution

Query: "Show me top 10 customers by total orders"

**Step 1: Intent Parsing**
```
Intent: REPORT
Entities: ["customers", "orders"]
Operations: ["top", "count"]
```

**Step 2: Load Scout Mode Cache (50ms)**
```
Tables in cache: 943
Semantic metadata loaded: numeric_columns, date_columns, fk_count
```

**Step 3: Score All Tables (50-100ms)**
```
dbo.Customers
  - Entity match (customers): +1.0
  - Fuzzy match: +0.0
  - Type compatibility: +0.0 (no numeric needed)
  - FK bonus: +0.05 (5 FKs)
  - Size: +0.05 (150k rows)
  SCORE: 1.10 → 1.0 (capped)

dbo.Orders
  - Entity match (orders): +1.0
  - Fuzzy match: +0.0
  - Type compatibility: +0.1 (numeric_columns present)
  - FK bonus: +0.06 (3 FKs)
  - Size: +0.05 (500k rows)
  SCORE: 1.21 → 1.0 (capped)

dbo.Products
  - Entity match: +0.0
  - Fuzzy match: +0.0
  - Type compatibility: +0.0
  - FK bonus: +0.04 (2 FKs)
  - Size: +0.03 (5k rows)
  SCORE: 0.07

[... 940 more tables scored ...]
```

**Step 4: Select Top Tables**
```
Ranked:
1. dbo.Customers (score: 1.0)
   Reasons: [Exact match for entity: customers, Well-connected (5 foreign keys)]

2. dbo.Orders (score: 1.0)
   Reasons: [Exact match for entity: orders, Well-connected (3 foreign keys)]

Selected for execution: [dbo.Customers, dbo.Orders]
```

**Step 5: Query Blueprint Generation**
```
SELECT TOP 10 
  c.customer_id, 
  c.name, 
  COUNT(o.order_id) as order_count
FROM dbo.Customers c
LEFT JOIN dbo.Orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name
ORDER BY order_count DESC
```

## Design Decisions

### 1. Cache-First Architecture
**Decision:** Consume Scout Mode metadata instead of querying database during ranking

**Rationale:** 
- 200-1000x faster (50ms vs 10-50s)
- Eliminates I/O during query execution
- Enables stateless scaling

### 2. Multi-Dimensional Scoring
**Decision:** Use 5 independent scoring dimensions rather than single heuristic

**Rationale:**
- More accurate for diverse query types
- Easier to debug (per-dimension reasoning)
- Extensible for new dimension types

### 3. Hard Caps on Scores
**Decision:** Maximum 1.0 despite formula allowing >1.0

**Rationale:**
- Simplifies interpretation
- Prevents outliers from dominating selection
- Consistent with confidence score semantics

### 4. Fuzzy Matching for Typos
**Decision:** Use Levenshtein distance for partial entity matches

**Rationale:**
- Handles common misspellings
- Fuzzy matching libraries well-tested
- Standard in full-text search

## Alternatives Considered

### 1. Machine Learning Ranking
**Pros:** Learns optimal weights from labeled data
**Cons:** Complex training pipeline, data requirements, non-deterministic
**Decision:** Rejected for Phase 7.1, consider for Phase 8+

### 2. Graph-Based Ranking
**Pros:** Considers table relationships holistically
**Cons:** Expensive computation, requires schema graph construction
**Decision:** Rejected; multi-dimensional scoring sufficient

### 3. User Feedback Loop
**Pros:** Adapts to user preferences over time
**Cons:** Complex state management, privacy concerns
**Decision:** Accepted as future enhancement (Phase 8)

## Integration Points

### With Scout Mode (ADR 0014)
- Receives pre-computed `numeric_columns`, `date_columns`, `fk_count`
- No database queries needed during ranking

### With Intent Parser
- Receives `intent` (AGGREGATE, TREND, REPORT, etc.)
- Receives `entities` and `operations` for scoring

### With Query Blueprints
- Receives selected tables from ranker
- Generates SQL based on rank ordering

### With Answer-first Orchestrator
- Called after table discovery, before blueprint generation
- Results cached in observability system

## Metrics & Observability

### Ranking Metrics Logged
```python
TableRankingMetrics:
  - tables_evaluated: 943
  - tables_scored_positive: 127
  - top_table_score: 0.95
  - top_tables_selected: 3
  - ranking_duration_ms: 45.2
  - average_score: 0.32
```

### Success Indicators
- ✅ Correct tables selected: >95% accuracy
- ✅ Ranking time: <100ms for 943 tables
- ✅ Consistency: Same query always produces same ranking
- ✅ Coverage: >90% of queries need ≤3 tables

## Failure Modes & Recovery

| Scenario | Detection | Recovery |
|----------|-----------|----------|
| Scout cache unavailable | Empty catalog | Fallback to discovery_tools |
| Entity doesn't match any table | Score 0.0 | Still execute with low confidence |
| All scores below threshold | No qualified tables | Return all tables, lowest confidence |
| Timeout during ranking | Takes >1s | Return partial ranking |

## Performance Characteristics

| Operation | Baseline | With Scout Cache |
|-----------|----------|------------------|
| Table discovery | 10-50s | <50ms |
| Type checking | Per-query DB hits | O(1) dict access |
| Full ranking | 5-10s | 50-100ms |
| End-to-end query | 15-70s | <500ms |

## Future Enhancements

1. **User-Specific Weights** - Different scoring per user role/team
2. **Query History** - Boost tables used in similar past queries
3. **Semantic Embeddings** - Use embeddings for deeper entity understanding
4. **Schema Change Detection** - Automatic cache invalidation on DDL
5. **Multi-Language Support** - German table name normalization
6. **ML-Based Learning** - Train weights from interaction data

## References

- ADR 0014: Scout Mode Semantic Caching
- ADR 0009: Context-Aware ERP Assistant Query Processing
- Phase 7 Answer-first Implementation
- Phase 7.1 Scout Mode Integration

---

## Decision Record

**Decision:** Implement semantic multi-dimensional table ranking as described above.

**Rationale:** Cache-first architecture with semantic metadata enables sub-second query execution without sacrificing accuracy.

**Approved By:** Architecture Team  
**Implementation Date:** Phase 7.1  
**Supersedes:** Interactive table clarification (Phase 6)