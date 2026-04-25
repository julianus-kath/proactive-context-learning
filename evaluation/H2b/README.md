# H2b Evidence — Production Transfer to Sage/Luisi & Diener

H2b hypothesis: *The system remains operationally usable in production, generating SQL and maintaining stable answerability.*

Primary evidence: a single end-to-end run of the `/process_query` pipeline against the Sage MSSQL ERP at Luisi & Diener, against nine partner-supplied questions (CP1–CP9), under both `scout_structural` (SDG off) and `scout_enriched_ranked` (SDG on). The Sage catalog was generated once on 2026-04-15 and reused in both arms.

These figures populate Table 5.6 and the discussion in Thesis §5.3.

## Headline numbers

| Mode | N | Required-table recall | All-required surfaced | SQL present | SQL exec success | Median latency |
|---|---:|---:|---:|---:|---:|---:|
| `scout_structural` | 9 | 0.000 | 0 / 9 | 6 / 9 | 6 / 9 | 7,330 ms |
| `scout_enriched_ranked` | 9 | 0.000 | 0 / 9 | 7 / 9 | 6 / 9 | 6,876 ms |

Recall against partner-supplied required-table labels is **zero in both conditions**. The H2b positive signal lives entirely in (a) SQL-generation rate (+1, structural → enriched_ranked) and (b) the discovery-layer trace — what Scout *considered* as candidates, recoverable from the per-query result records — not in required-table grounding under the full pipeline.

The thesis must (and does) frame H2b as *operational stability under production conditions*, not as *production-grade table accuracy*.

## Run structure

The single outer run directory `20260415_101033_h2b_sage_sdg_label_normalization/` contains six chronologically nested phases:

| Inner subdirectory | Phase |
|---|---|
| `20260415_100955_h2b_sage_sdg/` | Service boot, mode toggling, health probes |
| `20260415_101009_h2b_sage_sdg_probe/` | `/process_query` feasibility probe (verdict `ready_for_h2b_process_query_grounding`) |
| `20260415_101033_h2b_sage_sdg_label_normalization/` | Partner-label → live-catalog normalization (produces `cockpit_partner_table_labels_v1.normalized.json`) |
| `20260415_101039_h2b_cockpit_process_query_scout_structural_r1/` | SDG-off run: 9 queries through the full pipeline |
| `20260415_101220_h2b_cockpit_process_query_scout_enriched_ranked_r1/` | SDG-on run: same 9 queries, identical pipeline |
| `20260415_101337_h2b_sage_sdg_report/` | Combined report (`report.md`, `report.json`) |

Per-run outputs in each of the two evaluation phases:
- `run_manifest.json` — environment, model, flags, timestamps
- `run_summary.md` — human-readable per-query rollup
- `process_query_results.json` — full agent trace per query
- `grounding_eval.json` / `grounding_eval.md` — required-table recall accounting
- `summary.json` — aggregate

## Inputs and ground truth

The `cockpit_partner_*` ground truth files live with the framework code under `eval/datasets/`. They are not duplicated here because they include partner-author identification that needs anonymization before any wider distribution. The `sage_descriptions.json` cache used by both arms is included here (943 tables, ~1 MB).

## Caveats (load-bearing for the defense)

1. **Required-table recall is 0/9 under both conditions.** The full agent pipeline never surfaces a partner-required table. The "transfer succeeded" claim in the thesis must be — and is — confined to operational stability (boot, query, return, no crashes), not retrieval accuracy.

2. **The partner labels are provisional.** The ground-truth file at `eval/datasets/cockpit_partner_table_labels_v1.json` carries `verification_status: "partner_mapped_pending_expert_review"` and identifies the partner annotator by first name. Five of the thirteen partner-supplied table names had to be normalized post hoc to live catalog names (alias / prefix collapse). One of those normalizations (CP2: "Bestellung" → VK rather than EK) is a module-knowledge edit that the question itself does not justify, and was preserved purely to keep the recall metric measurable. The thesis does not claim independently validated ground truth.

3. **The Sage description cache provider is not persisted in the cache.** The thesis text states the Sage descriptions were generated with a Claude Sonnet 4 configuration, but the cache file does not record the model field, so this claim is not auditable from the artifact alone. The provenance is recorded only in the operator log.

4. **Latency numbers are diagnostic, not benchmarks.** The 6.8–7.3 second medians include VPN round-trip and a Windows-side MCP-server cold-start cost. They are reported for operational realism, not for performance comparison.
