# Evaluation Artifacts

This directory contains the curated evidence base for the four thesis hypotheses. Every run here is the one cited in the thesis prose — older or pilot runs that did not make the final write-up live in the private evaluation vault and are not duplicated here.

The full source-of-truth audit is the April 17 evidence inventory at the master-thesis root (`H2a_H2b_Evidence_Inventory_2026-04-17.md`). What you find below is the publication-grade subset.

## Hypotheses

| Subdir | Hypothesis | Thesis section | Evidence type |
|---|---|---|---|
| [`H1/`](H1/) | Scout Mode autonomously builds a query-useful schema catalog | §5.1 | Catalog completeness on Northwind + Sage |
| [`H2a/`](H2a/) | Proactive schema grounding delivers semantic correctness (controlled) | §5.2 | SDG ablation on Northwind, N=64 |
| [`H2b/`](H2b/) | The system transfers to production conditions | §5.3 | `/process_query` grounding on Sage, N=9 |
| [`H3/`](H3/) | Users derive exploratory value from the system | §5.4 | Two-participant qualitative study |

## How to read each subdirectory

Each `H*/` directory ships:

- A `README.md` explaining the hypothesis, the runs included, the headline numbers, and the caveats.
- One or more timestamped run directories with `config.json`, `summary.json`, and `results_raw.jsonl` (the exact files produced by the evaluation framework in `eval/`).
- Where applicable, the input dataset and the reference SQL used as ground truth.

Run directory names follow `<YYYYMMDD>_<HHMMSS>_<hypothesis>_<condition>_<descriptor>` for unambiguous cross-referencing with the framework's run database under `eval/runs/`. The timestamps are the actual execution times, not the date they were copied here.

## Reproducing a result

Every run is reproducible from the framework code in [`../eval/`](../eval/) using the dataset and configuration recorded in the run directory:

```bash
python -m eval.run_h2a_full_pipeline \
  --dataset evaluation/H2a/northwind_extended_difficulty_v1.jsonl \
  --contracts evaluation/H2a/northwind_extended_difficulty_v1.contracts.json \
  --mode scout_enriched_ranked
```

See [`../eval/SDG_EVALUATION_RUNBOOK.md`](../eval/SDG_EVALUATION_RUNBOOK.md) for the canonical procedure, and the per-hypothesis READMEs for variations.

## What is *not* here

- Raw participant transcripts and recordings from H3 (held privately under the participant consent terms).
- Pre-SDG runs (March 2026 and earlier) — these used a different ablation design and are archived under `eval/runs/archived/` in the framework directory.
- Drafts and pilot iterations — kept under the master-thesis-level `evaluation/` vault for the supervisor's reference but excluded from this release.
