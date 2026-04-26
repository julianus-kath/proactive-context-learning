# H1 Evidence — Catalog Completeness

H1 hypothesis: *Scout Mode autonomously builds a query-useful schema catalog.*

Primary evidence: structural catalog completeness on both evaluation environments. These figures populate Table~\ref{tab:h1-primary-key-results} in Thesis \S5.1.

## Staged runs

| Subdirectory | Environment | Tables | Columns | FK columns | Source |
|---|---|---:|---:|---:|---|
| [`northwind_catalog_coverage/`](northwind_catalog_coverage/) | Northwind (controlled) | 14 / 14 (100 %) | 92 / 92 (100 %) | 13 / 13 (100 %) | `code/eval/runs/archived/20260216_150213_northwind_offline_extract/` |
| [`sage_catalog_coverage/`](sage_catalog_coverage/) | Luisi & Diener Sage ERP (production) | 943 / 943 (100 %) | 13 759 / 13 759 (100 %) | 392 / 392 (100 %) | `code/eval/runs/archived/20260216_145042_ld_prod_offline_extract/` |

## Files per run

- `scout_catalog_coverage.json` — primary headline evidence (coverage percentages + missing counts)
- `scout_manifest.json` — run metadata (mode, source file paths)
- `scout_summary.json` — aggregated summary (coverage + quality metrics)
- `scout_catalog_quality.json` — catalog-quality metadata
- `scout_health.json` — diagnostic health report
- `scout_report.md` — human-readable report
- `northwind_descriptions.json` (Northwind run) / `sage_descriptions.json` (Sage run) — the SDG description cache produced as part of the catalog build. Same files used at runtime by the H2a/H2b SDG-on conditions; copies are kept under H2a/ and H2b/ for hypothesis self-containment.

Large artifacts (`scout_ground_truth.json`, `scout_catalog_discovered.json`, `scout_index_snapshot.json`) remain at the source paths under `code/eval/runs/archived/` and are not duplicated here.

## Provenance note

Both runs use `mode: offline_export_audit`: the catalogs are built from JSON exports of the live MCP runtime schemas rather than from a second online discovery pass. This makes H1 reproducible from the stored exports alone. The discovery pipeline itself is implemented in `mcp_server/scout/runner.py` and audited by `code/eval/archived_scripts/run_scout_audit.py`.

## Known caveats

- The Northwind `scout_health.json` flags `catalog_valid: false` with `age > TTL` (1 h). This is a freshness indicator only; the coverage numbers themselves are unaffected.
- The 100 % Northwind figure on a 14-table public schema is a correct read from `information_schema`, not a hard benchmark. The 943-table Sage figure is the more informative demonstration of the catalog builder at scale, and the thesis prose should weight it accordingly.
