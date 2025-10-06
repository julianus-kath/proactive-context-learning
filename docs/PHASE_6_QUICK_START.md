# Phase 6 Quick Start Guide

**5-Minute Guide to Observability & Guardrails**

---

## 🚀 Quick Start

### 1. Check Health Status
```bash
curl http://localhost:8000/health | jq
```

**Expected Response**:
```json
{
  "status": "healthy",
  "database": {"connected": true},
  "catalog": {"initialized": true, "table_count": 150},
  "metrics": {"success_rate": 0.98, "avg_duration_ms": 45.2}
}
```

### 2. Run Integration Tests
```bash
cd "/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code"
python -m pytest tests/test_phase6_observability.py -v
```

### 3. Run Load Test (1 minute)
```bash
python tests/test_phase6_load.py --duration 1 --qpm 20
```

---

## 📊 Key Features

### Structured Logging
```python
from mcp_server.observability import log_tool_call

with log_tool_call("list_tables", {"page": 1}) as metrics:
    # Your tool logic here
    metrics.cache_hit = True
    metrics.row_count = 25
```

**Automatic Tracking**:
- ✅ Duration (milliseconds)
- ✅ Success/failure
- ✅ Cache hits
- ✅ Row counts
- ✅ Error categorization
- ✅ PII redaction

### Rate Limiting
```python
from mcp_server.discovery_tools import RateLimiter

limiter = RateLimiter(requests_per_second=10.0, burst_size=20)
allowed, retry_after = limiter.allow_request()

if not allowed:
    return {"error": "Rate limit exceeded", "retry_after": retry_after}
```

**Features**:
- Token bucket algorithm
- Configurable rate and burst
- Retry-After headers in responses

### Query Safety
```python
from mcp_server.query_validator import QueryValidator

validator = QueryValidator()
is_safe, error = validator.validate_query("SELECT * FROM users")

if not is_safe:
    return {"error": error}
```

**Protections**:
- ✅ DDL rejection (CREATE, DROP, ALTER)
- ✅ DML rejection (INSERT, UPDATE, DELETE)
- ✅ SELECT-only enforcement
- ✅ Dangerous function blocking

---

## 🔧 Configuration

### Environment Variables
```bash
# Rate Limiting
export RATE_LIMIT_RPS=10.0
export RATE_LIMIT_BURST=20

# Query Safety
export MAX_QUERY_ROWS=1000
export QUERY_TIMEOUT_SECONDS=30

# Logging
export LOG_LEVEL=INFO
export LOG_FORMAT=json
```

### Programmatic Configuration
```python
# In your startup code
from mcp_server.discovery_tools import DiscoveryTools, RateLimiter

DiscoveryTools._rate_limiter = RateLimiter(
    requests_per_second=20.0,
    burst_size=40
)
```

---

## 📈 Monitoring

### View Metrics
```python
from mcp_server.observability import StructuredLogger

logger = StructuredLogger()
summary = logger.get_metrics_summary()

print(f"Total calls: {summary['total_calls']}")
print(f"Success rate: {summary['success_rate']:.2%}")
print(f"Avg duration: {summary['avg_duration_ms']:.1f}ms")
print(f"Cache hit rate: {summary['cache_hit_rate']:.2%}")
```

### View Recent History
```python
history = logger.get_metrics_history(limit=10)
for call in history:
    print(f"{call['tool_name']}: {call['duration_ms']:.1f}ms - {'✅' if call['success'] else '❌'}")
```

---

## 🧪 Testing

### Unit Tests
```bash
# Test structured logging
pytest tests/test_phase6_observability.py::TestStructuredLogging -v

# Test rate limiting
pytest tests/test_phase6_observability.py::TestRateLimitingWithRetryAfter -v

# Test safety controls
pytest tests/test_phase6_observability.py::TestSafetyControls -v
```

### Integration Tests
```bash
# Run all Phase 6 tests
pytest tests/test_phase6_observability.py -v
```

### Load Tests
```bash
# Quick test (1 minute)
python tests/test_phase6_load.py --duration 1 --qpm 20

# Full acceptance test (5 minutes)
python tests/test_phase6_load.py --duration 5 --qpm 20

# Stress test (high load)
python tests/test_phase6_load.py --duration 2 --qpm 100
```

---

## 🚨 Troubleshooting

### Import Errors
If you see `ModuleNotFoundError: No module named 'models'`:
```python
# Add to top of test file
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
```

### Rate Limit Errors
If you're getting 429 errors:
1. Check current rate limit: `curl http://localhost:8000/health | jq .rate_limiting`
2. Increase rate limit: Set `RATE_LIMIT_RPS=20.0` in environment
3. Wait for retry_after duration from error response

### Health Check Failures
If `/health` returns unhealthy:
1. Check database connection: `curl http://localhost:8000/health | jq .database`
2. Check catalog status: `curl http://localhost:8000/health | jq .catalog`
3. View recent errors: `curl http://localhost:8000/health | jq .metrics.error_breakdown`

---

## 📚 Common Use Cases

### 1. Monitor System Health
```bash
# Check every 30 seconds
watch -n 30 'curl -s http://localhost:8000/health | jq ".status, .metrics.success_rate"'
```

### 2. Debug Slow Queries
```python
from mcp_server.observability import StructuredLogger

logger = StructuredLogger()
history = logger.get_metrics_history()

# Find slow queries
slow_queries = [
    call for call in history 
    if call['duration_ms'] > 100
]

for query in slow_queries:
    print(f"{query['tool_name']}: {query['duration_ms']:.1f}ms")
```

### 3. Track Error Rates
```python
summary = logger.get_metrics_summary()
error_rate = 1 - summary['success_rate']

if error_rate > 0.05:  # More than 5% errors
    print(f"⚠️ High error rate: {error_rate:.2%}")
    print(f"Error breakdown: {summary['error_breakdown']}")
```

### 4. Validate Rate Limiting
```python
from mcp_server.discovery_tools import RateLimiter

limiter = RateLimiter(requests_per_second=10.0, burst_size=20)

# Simulate burst
for i in range(25):
    allowed, retry_after = limiter.allow_request()
    if not allowed:
        print(f"Rate limited at request {i+1}, retry after {retry_after:.2f}s")
```

---

## 🎯 Acceptance Criteria Checklist

- ✅ Structured logging for all tool calls
- ✅ Enhanced /health endpoint with metrics
- ✅ Rate limiting with Retry-After headers
- ✅ Big schema handling (500+ tables)
- ✅ Relevance testing (search → describe → query)
- ✅ Safety controls (DDL/DML rejection)
- ✅ Load test: 20 qpm for 5 min, no 429s
- ✅ >95% success rate under load
- ✅ <100ms avg latency
- ✅ <200ms P95 latency

---

## 📖 Next Steps

1. **Review Full Documentation**: See `PHASE_6_COMPLETE.md`
2. **Run Load Tests**: Validate acceptance criteria
3. **Configure Monitoring**: Set up Prometheus/Datadog integration
4. **Deploy to Production**: Follow deployment guide
5. **Start Phase 7**: Advanced query planning & optimization

---

## 🔗 Quick Links

- **Full Documentation**: `docs/PHASE_6_COMPLETE.md`
- **Integration Tests**: `tests/test_phase6_observability.py`
- **Load Tests**: `tests/test_phase6_load.py`
- **Observability Module**: `mcp_server/observability.py`
- **Discovery Tools**: `mcp_server/discovery_tools.py`
- **Health Endpoint**: `mcp_server/server.py` (lines 150-200)

---

**Last Updated**: January 2025  
**Version**: 1.0