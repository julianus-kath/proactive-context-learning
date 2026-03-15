# /process_query Northwind Run (scout_off_aligned)

- Run ID: `20260301_115508_nonlexical_v1_process_query_scout_off_aligned_r1`
- Run name: `nonlexical_v1_process_query_scout_off_aligned_r1`
- Scout start: `SchemaCatalog` | active=`False`
- Scout end: `SchemaCatalog` | active=`False`
- Meaning: Scout mode INACTIVE: MCP discovery backend is SchemaCatalog with aligned TableRanker baseline.
- Total queries: `20`
- Successes: `4`
- Failures: `16`
- Avg latency ms: `2922.7`
- P95 latency ms: `4438.0`

| Query | Status | Latency (ms) | SQL present | Tables used |
|---|---|---:|---|---|
| NL1 | success | 3443 | True | public.order_details |
| NL10 | failed | 1823 | False |  |
| NL11 | failed | 1737 | False |  |
| NL12 | failed | 1822 | False |  |
| NL13 | failed | 1778 | False |  |
| NL14 | failed | 1959 | False |  |
| NL15 | failed | 1785 | False |  |
| NL16 | failed | 1979 | False |  |
| NL17 | failed | 1918 | False |  |
| NL18 | failed | 1743 | False |  |
| NL19 | failed | 1885 | False |  |
| NL2 | success | 2880 | True | public.order_details, public.orders |
| NL20 | failed | 1744 | False |  |
| NL3 | success | 4438 | True | public.orders, public.shippers |
| NL4 | success | 4284 | True | public.order_details, public.products, public.categories |
| NL5 | failed | 14911 | False |  |
| NL6 | failed | 2338 | False |  |
| NL7 | failed | 1938 | False |  |
| NL8 | failed | 2139 | False |  |
| NL9 | failed | 1909 | False |  |
