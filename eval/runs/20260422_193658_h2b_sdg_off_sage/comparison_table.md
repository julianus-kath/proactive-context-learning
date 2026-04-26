# Retrieval-Only Ablation Results — COCKPIT

**Date:** 2026-04-22 19:37  
**Top-k:** 10  
**Queries:** 9  
**Dataset:** cockpit  

## 1. Aggregate Metrics (Primary Search Strategy)

| Metric | sdg_off |
|--------|--------|
| Mean Recall@k | 0.148 |
| Mean Precision@k | 0.022 |
| Mean Hit@k | 0.222 |
| Mean MRR | 0.051 |
| Perfect Recall | 1/9 |
| Zero Recall | 7/9 |
| Mean Latency (ms) | 179 |

## 2. Per-Query Recall@10

| Query | Required Tables | sdg_off |
|-------|----------------|--------|
| CP1 | dbo.KHKArtikel, dbo.KHKArtikelLieferant, dbo.KHKArtikelVarianten | 0.00 (MISS) |
| CP2 | dbo.KHKVKBelege, dbo.KHKVKBelegePositionen | 0.00 (MISS) |
| CP3 | dbo.KHKPpsFaBelege, dbo.KHKPpsFaBelegeAGPositionen, dbo.KHKPpsBdeStempel | 0.00 (MISS) |
| CP4 | dbo.OsemzizZEBuchungen | 0.00 (MISS) |
| CP5 | dbo.OsemzizZEBuchungen, dbo.KHKPpsBdeStempel | 0.00 (MISS) |
| CP6 | dbo.KHKEKBelege, dbo.KHKEKBelegePositionen, dbo.KHKEKBelegePositionenLager | 0.33 (PARTIAL) |
| CP7 | KHKBuchungserfassung | 1.00 (PERFECT) |
| CP8 | dbo.KHKPpsFaBelege, dbo.KHKPpsFaBelegeAGPositionen, dbo.KHKPpsBdeStempel | 0.00 (MISS) |
| CP9 | dbo.OsemzizZEBuchungen, dbo.KHKPpsBdeStempel, dbo.KHKPpsFaBelege (+1) | 0.00 (MISS) |

## 4. Keyword Strategy Analysis

Shows whether alternative search strategies improve recall over the primary strategy.

### sdg_off

| Query | Primary | Best Alt | Delta |
|-------|---------|----------|-------|
| CP1 | 0.00 | 0.33 | +0.33 |
| CP2 | 0.00 | 0.00 | +0.00 |
| CP3 | 0.00 | 0.00 | +0.00 |
| CP4 | 0.00 | 0.00 | +0.00 |
| CP5 | 0.00 | 0.50 | +0.50 |
| CP6 | 0.33 | 0.33 | +0.00 |
| CP7 | 1.00 | 1.00 | +0.00 |
| CP8 | 0.00 | 0.00 | +0.00 |
| CP9 | 0.00 | 0.50 | +0.50 |

