# Northwind Consistency Analysis (Recovered, 5 runs)

## Runs analyzed
- `20260215_083337_northwind_hypothesis_consistency_recovered_r1`: success=10/10, strict=10.0%, acceptable=60.0%, ref_match=10.0%
- `20260215_083426_northwind_hypothesis_consistency_recovered_r2`: success=9/10, strict=0.0%, acceptable=22.22%, ref_match=0.0%
- `20260215_083511_northwind_hypothesis_consistency_recovered_r3`: success=10/10, strict=0.0%, acceptable=40.0%, ref_match=0.0%
- `20260215_083556_northwind_hypothesis_consistency_recovered_r4`: success=10/10, strict=10.0%, acceptable=50.0%, ref_match=10.0%
- `20260215_083640_northwind_hypothesis_consistency_recovered_r5`: success=10/10, strict=0.0%, acceptable=40.0%, ref_match=0.0%

## Aggregate (mean ± stddev)
- `success_rate_pct`: mean=98.0, stddev=4.0, min=90.0, max=100.0, n=5
- `semantic_strict_accuracy_pct`: mean=4.0, stddev=4.899, min=0.0, max=10.0, n=5
- `semantic_acceptable_accuracy_pct`: mean=42.444, stddev=12.54, min=22.22, max=60.0, n=5
- `reference_match_rate_pct`: mean=4.0, stddev=4.899, min=0.0, max=10.0, n=5
- `catalog_table_coverage_pct`: mean=100.0, stddev=0.0, min=100.0, max=100.0, n=5
- `catalog_column_coverage_pct`: mean=100.0, stddev=0.0, min=100.0, max=100.0, n=5
- `retrieval_avg_recall_at_5`: mean=0.8467, stddev=0.0067, min=0.8333, max=0.85, n=5
- `avg_total_llm_calls`: mean=3.58, stddev=0.16, min=3.4, max=3.8, n=5
- `avg_latency_ms_total`: mean=4404.08, stddev=266.3305, min=4022.5, max=4849.2, n=5
- `quota_errors_total`: 0

## Baseline comparison
- `success_rate_pct`: recovered_mean=98.0, baseline=100.0, delta=-2.0
- `semantic_strict_accuracy_pct`: recovered_mean=4.0, baseline=10.0, delta=-6.0
- `semantic_acceptable_accuracy_pct`: recovered_mean=42.444, baseline=40.0, delta=2.444
- `reference_match_rate_pct`: recovered_mean=4.0, baseline=10.0, delta=-6.0
- `retrieval_avg_recall_at_5`: recovered_mean=0.8467, baseline=0.85, delta=-0.0033
- `avg_total_llm_calls`: recovered_mean=3.58, baseline=3.7, delta=-0.12

## Per-query reliability (5 runs)
- `NW1`: success=4/5 (80.0%), dominant_label=PARTIAL, ref_match=0.0%, recall@5=0.8
- `NW10`: success=5/5 (100.0%), dominant_label=PARTIAL, ref_match=0.0%, recall@5=1.0
- `NW2`: success=5/5 (100.0%), dominant_label=INCORRECT, ref_match=40.0%, recall@5=0.6667
- `NW3`: success=5/5 (100.0%), dominant_label=INCORRECT, ref_match=0.0%, recall@5=1.0
- `NW4`: success=5/5 (100.0%), dominant_label=INCORRECT, ref_match=0.0%, recall@5=0.5
- `NW5`: success=5/5 (100.0%), dominant_label=INCORRECT, ref_match=0.0%, recall@5=0.6667
- `NW6`: success=5/5 (100.0%), dominant_label=PARTIAL, ref_match=0.0%, recall@5=1.0
- `NW7`: success=5/5 (100.0%), dominant_label=PARTIAL, ref_match=0.0%, recall@5=1.0
- `NW8`: success=5/5 (100.0%), dominant_label=INCORRECT, ref_match=0.0%, recall@5=0.6667
- `NW9`: success=5/5 (100.0%), dominant_label=INCORRECT, ref_match=0.0%, recall@5=1.0

## Interpretation
- Recovery is confirmed: consistency runs show no provider quota failures.
- H1 completeness remains maximal and stable (100% table/column coverage).
- H2a remains low in strict/reference accuracy despite stable execution, indicating semantic quality is the limiting factor.
- NW1 is the only query with intermittent execution instability in this batch.
