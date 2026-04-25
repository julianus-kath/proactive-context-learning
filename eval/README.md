# Evaluation & Tracking System

A standalone, non-intrusive evaluation harness for the autonomous multi-agent reasoning system. Designed to support thesis hypothesis validation (H1: Proof of Concept, H2a: Proof of Performance).

---

## Post-Consolidation State (as of 2026-04-14)

On 2026-04-14 the eval directory was consolidated. Pre-SDG scripts, datasets, runs, and docs were moved into archived directories; only the artifacts driving the current SDG-based evaluation design remain at the top level.

### Current top-level layout

```
eval/
├── README.md                            # this file
├── SDG_ABLATION_EXPERIMENTAL_SETUP.md   # canonical experimental design
├── SDG_EVALUATION_RUNBOOK.md            # how to run SDG-era evaluations
├── contracts.py                         # ground truth contract definitions
├── eval_client.py                       # instrumentation client
├── service.py                           # eval tracking service
├── run_h2a_full_pipeline.py             # H2a (Northwind) runner
├── run_h2b_process_query_grounding.py   # H2b (Cockpit/Sage) runner
├── generate_descriptions.py             # SDG description generation
├── datasets/
│   ├── northwind_extended_difficulty_v1.{jsonl,contracts.json}     # H2a, N=64
│   ├── northwind_queries_underspecified_v1.*                       # L5 source
│   ├── northwind_queries_lexical_breakpoint_v1.*                   # L6 source (see note)
│   ├── northwind_pilot_n10_v1.jsonl                                # SDG pilot, N=10
│   ├── cockpit_partner_queries_v1.jsonl                            # H2b, N=9
│   ├── cockpit_partner_table_labels_v1.{json,md}                   # H2b ground truth
│   ├── cockpit_partner_table_label_overrides_v1.json
│   └── archived/                        # 58 superseded datasets
├── runs/
│   ├── 20260327_071347_h2b_full_pipeline_scout_off_aligned_REAL    # first real H2b
│   ├── 20260328_131450_h2a_CLEAN_scout_on                          # structural baseline
│   ├── 20260328_131936_h2a_CLEAN_scout_off_aligned                 # ON≈OFF evidence
│   ├── 20260414_093339_pilot_n10_scout_structural                  # SDG pilot smoke
│   └── archived/                        # 302 pre-SDG runs
├── cache/                               # SDG description cache (generated)
├── archived_scripts/                    # retired scripts + old scoring/
└── archived_docs/                       # retired design docs
```

### Naming note: `lexical_breakpoint` vs "schema-opaque"

The thesis refers to the L6 query set as **schema-opaque**. The dataset files and the `category` field inside `northwind_extended_difficulty_v1.jsonl` are named **`lexical_breakpoint`** for historical reasons and are kept as-is to avoid breaking ground truth references. **Do not rename.** When writing thesis prose, use "schema-opaque"; when writing code, scripts, or queries, use `lexical_breakpoint`.

