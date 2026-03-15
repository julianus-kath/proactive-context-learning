# Complex Hard v1 (r1+r2) ON vs OFF-aligned

Generated: 2026-03-01T15:23:27.189154Z
- Dataset: `eval/datasets/northwind_queries_complex_hard_v1.jsonl`
- Reference SQL: `eval/datasets/northwind_queries_complex_hard_v1.reference_sql.json`

## Replicate Metrics

| Replicate | strict Δ | same-cols Δ | positional Δ | required-tables Δ | success Δ | avg-latency Δ ms | p95-latency Δ ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| r1 | 0 | 0 | 0 | -2 | 0.0 | -232.80000000000018 | 2280.0 |
| r2 | 0 | 0 | 0 | 0 | 0.0 | -1503.0999999999995 | -3420.0 |

Mean delta across r1+r2 (ON-OFF):
- strict: `0`
- same-cols: `0`
- positional: `0`
- required-tables: `-1`
- avg-latency-ms: `-867.9499999999998`

## Stable Scout Limits (both modes)

- Queries with no SQL in both modes across both replicates: `['HX15', 'HX3', 'HX8']`
- HX15: Bei welchen Versanddienstleistern haeufen sich verspaetete Lieferungen besonders bei hochrabattierten Auftraegen?
  ON excerpt: `Die Suche nach relevanten Tabellen für "Versanddienstleister", "verspätete Lieferungen", "hochrabattierte Aufträge" und verwandte Begriffe hat keine spezifischen Tabellen mit den benötigten Informationen ergeben. Die ein`
  OFF excerpt: `Die Datenbank enthält keine spezifischen Tabellen oder Spalten, die direkt Informationen zu Versanddienstleistern, verspäteten Lieferungen oder Rabatten enthalten. Die Tabelle `public.suppliers` wurde als potenziell rele`
- HX3: Bei welchen Versanddienstleistern ist der Anteil stark verspaeteter Sendungen (mehr als 3 Tage) am groessten?
  ON excerpt: `Es scheint, dass die Datenbank keine spezifischen Tabellen enthält, die direkt Informationen über Versanddienstleister und die Verspätung von Sendungen enthalten. Die Tabelle `public.suppliers` könnte Informationen über `
  OFF excerpt: `Ich konnte keine spezifischen Tabellen finden, die direkt Informationen über verspätete Sendungen in Verbindung mit Versanddienstleistern enthalten. Die Tabelle `public.suppliers` enthält Informationen über Lieferanten, `
- HX8: In welchen Monaten stieg die Frachtkostenquote gegenueber dem Vormonat am staerksten?
  ON excerpt: `Ich konnte keine spezifischen Tabellen oder Spalten zur "Frachtkostenquote" oder verwandten Begriffen in der Datenbank finden. Es könnte sein, dass die Daten unter einem anderen Namen gespeichert sind oder nicht direkt v`
  OFF excerpt: `Ich konnte keine spezifischen Tabellen oder Spalten zur "Frachtkostenquote" oder verwandten Begriffen in der Datenbank finden. Es könnte sein, dass die Daten unter einem anderen Namen gespeichert sind oder dass sie nicht`

## Progression vs Earlier Hard Tier
| Metric | Crosslingual hard mean Δ (ON-OFF) | Complex hard mean Δ (ON-OFF) |
|---|---:|---:|
| expert_strict_equal_count | 0.6666666666666666 | 0 |
| expert_same_cols_set_equal_count | 0.6666666666666666 | 0 |
| expert_positional_set_equal_count | 0.6666666666666666 | 0 |
| expert_required_tables_ok_count | 0.3333333333333333 | -1 |
| avg_latency_ms | 180.46666666666684 | -867.9499999999998 |

## Quota / 429 Check
- `20260301_151227_complex_hard_v1_process_query_scout_on_r1` -> {'http_429_count': 0, 'insufficient_quota_count': 0, 'rate_limit_exceeded_count': 0}
- `20260301_151456_complex_hard_v1_process_query_scout_off_aligned_r1` -> {'http_429_count': 0, 'insufficient_quota_count': 0, 'rate_limit_exceeded_count': 0}
- `20260301_151800_complex_hard_v1_process_query_scout_on_r2` -> {'http_429_count': 0, 'insufficient_quota_count': 0, 'rate_limit_exceeded_count': 0}
- `20260301_152002_complex_hard_v1_process_query_scout_off_aligned_r2` -> {'http_429_count': 0, 'insufficient_quota_count': 0, 'rate_limit_exceeded_count': 0}
