"""Combined N=84 analysis: April-14 N=64 + April-18 N=20 delta cohort.

Produces:
- Delta-only recall metrics and semantic-label distribution (n=20)
- Combined recall metrics, per-language and per-level breakdowns (n=84)
- Wilcoxon signed-rank test on combined paired recall
- Sensitivity check (both-produced-SQL subset)
- combined_summary.json with all of the above
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev
from typing import Any

try:
    from scipy.stats import wilcoxon  # type: ignore
    HAS_SCIPY = True
except Exception:
    HAS_SCIPY = False

THESIS_ROOT = Path("/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis")
EVAL_H2A = THESIS_ROOT / "evaluation/H2a"

# April-14 canonical runs (N=64).
APR14_OFF = EVAL_H2A / "20260414_h2a_full64_scout_structural/results_raw.jsonl"
APR14_ON = EVAL_H2A / "20260414_h2a_full64_scout_enriched_ranked/results_raw.jsonl"
APR14_LABELS = EVAL_H2A / "20260416_h2a_semantic_labels/semantic_labels.jsonl"

# April-18 delta runs (N=20).
APR18_OFF = EVAL_H2A / "20260418_h2a_de_l1l2_scout_structural/results_raw.jsonl"
APR18_ON = EVAL_H2A / "20260418_h2a_de_l1l2_scout_enriched_ranked/results_raw.jsonl"
APR18_LABELS = EVAL_H2A / "20260418_h2a_de_l1l2_semantic_labels/semantic_labels.jsonl"

OUT = EVAL_H2A / "20260418_de_l1l2_drafts/combined_summary.json"


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def keyed(rows: list[dict], key: str) -> dict[str, dict]:
    return {r[key]: r for r in rows}


def level_for(qid: str) -> str:
    """Map query_id → difficulty level label (L1/L2/L3/L4/L5/L6)."""
    if qid.startswith("NW_DE_"):
        return "L1_DE"
    if qid.startswith("NL_DE_"):
        return "L2_DE"
    if qid.startswith("NW"):
        return "L1_EN"
    if qid.startswith("NL"):
        return "L2_EN"
    if qid.startswith("CL"):
        return "L3"
    if qid.startswith("HX"):
        return "L4"
    if qid.startswith("US_"):
        return "L5"
    if qid.startswith("LB_"):
        return "L6"
    return "UNK"


def language_for(qid: str) -> str:
    if qid.startswith("NW_DE_") or qid.startswith("NL_DE_"):
        return "de"
    if qid.startswith("NW") or qid.startswith("NL"):
        return "en"
    return "de"


def stats(recalls: list[float]) -> dict[str, float]:
    if not recalls:
        return {"n": 0, "mean": None, "sd": None, "perfect": 0, "zero": 0}
    return {
        "n": len(recalls),
        "mean": round(mean(recalls), 4),
        "sd": round(stdev(recalls), 4) if len(recalls) >= 2 else 0.0,
        "perfect": sum(1 for r in recalls if r == 1.0),
        "zero": sum(1 for r in recalls if r == 0.0),
    }


def wilcoxon_paired(off_vals: list[float], on_vals: list[float]) -> dict[str, Any]:
    assert len(off_vals) == len(on_vals), "paired vectors must match length"
    diffs = [on - off for off, on in zip(off_vals, on_vals)]
    non_zero = [d for d in diffs if d != 0]
    result: dict[str, Any] = {
        "n_pairs": len(diffs),
        "n_non_zero": len(non_zero),
        "wins_on": sum(1 for d in diffs if d > 0),
        "wins_off": sum(1 for d in diffs if d < 0),
        "ties": sum(1 for d in diffs if d == 0),
        "mean_diff": round(mean(diffs), 4) if diffs else None,
    }
    if HAS_SCIPY and non_zero:
        stat, p_val = wilcoxon(non_zero, alternative="greater")
        result["wilcoxon_W"] = float(stat)
        result["wilcoxon_p_one_sided"] = float(p_val)
        # Rank-biserial correlation: r = (W+ - W-) / (W+ + W-)
        # Simpler proxy: use sign counts.
        pos = sum(1 for d in non_zero if d > 0)
        neg = sum(1 for d in non_zero if d < 0)
        if (pos + neg) > 0:
            result["rank_biserial_proxy"] = round((pos - neg) / (pos + neg), 4)
    return result


def label_counts(rows: list[dict]) -> dict[str, int]:
    out = {"CORRECT": 0, "PARTIAL": 0, "INCORRECT": 0, "ERROR": 0}
    for r in rows:
        out[r["label"]] = out.get(r["label"], 0) + 1
    return out


def main() -> int:
    # --- Load runs ---
    apr14_off = keyed(load_jsonl(APR14_OFF), "query_id")
    apr14_on = keyed(load_jsonl(APR14_ON), "query_id")
    apr18_off = keyed(load_jsonl(APR18_OFF), "query_id")
    apr18_on = keyed(load_jsonl(APR18_ON), "query_id")

    # --- Combined keyspace ---
    common_apr14 = set(apr14_off) & set(apr14_on)
    common_apr18 = set(apr18_off) & set(apr18_on)
    assert len(common_apr14) == 64, f"Apr14 joined size {len(common_apr14)}"
    assert len(common_apr18) == 20, f"Apr18 joined size {len(common_apr18)}"

    all_off = {**apr14_off, **apr18_off}
    all_on = {**apr14_on, **apr18_on}
    all_ids = sorted(set(all_off) & set(all_on))
    assert len(all_ids) == 84, f"Combined size {len(all_ids)}"

    # --- Delta-only metrics ---
    delta_off = [apr18_off[q]["recall"] for q in sorted(apr18_off)]
    delta_on = [apr18_on[q]["recall"] for q in sorted(apr18_on)]
    delta_off_sql = sum(1 for q in apr18_off if apr18_off[q]["sql_present"])
    delta_on_sql = sum(1 for q in apr18_on if apr18_on[q]["sql_present"])

    delta_by_level: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"off": [], "on": []})
    for q in sorted(apr18_off):
        lvl = level_for(q)
        delta_by_level[lvl]["off"].append(apr18_off[q]["recall"])
        delta_by_level[lvl]["on"].append(apr18_on[q]["recall"])

    delta_labels = load_jsonl(APR18_LABELS)
    delta_labels_off = [r for r in delta_labels if r["condition"] == "scout_structural"]
    delta_labels_on = [r for r in delta_labels if r["condition"] == "scout_enriched_ranked"]

    # --- Combined metrics ---
    combined_off = [all_off[q]["recall"] for q in all_ids]
    combined_on = [all_on[q]["recall"] for q in all_ids]

    combined_by_level: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"off": [], "on": []})
    for q in all_ids:
        lvl = level_for(q)
        combined_by_level[lvl]["off"].append(all_off[q]["recall"])
        combined_by_level[lvl]["on"].append(all_on[q]["recall"])

    combined_by_lang: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"off": [], "on": []})
    for q in all_ids:
        lng = language_for(q)
        combined_by_lang[lng]["off"].append(all_off[q]["recall"])
        combined_by_lang[lng]["on"].append(all_on[q]["recall"])

    # Sensitivity: both produced SQL.
    both_sql_ids = [q for q in all_ids if all_off[q]["sql_present"] and all_on[q]["sql_present"]]
    sens_off = [all_off[q]["recall"] for q in both_sql_ids]
    sens_on = [all_on[q]["recall"] for q in both_sql_ids]

    # --- Assemble summary ---
    summary: dict[str, Any] = {
        "description": "Combined N=84 H2a analysis (April-14 canonical + April-18 German L1-L2 extension).",
        "cross_snapshot_caveat": (
            "April-14 runs used the gpt-4o-mini snapshot current on 2026-04-14. "
            "April-18 runs used the gpt-4o-mini snapshot current on 2026-04-18. "
            "OpenAI does not pin model snapshots; any silent model drift between the "
            "two dates is a within-study methodological caveat."
        ),
        "delta_cohort_n20": {
            "sql_generation": {
                "scout_structural": round(delta_off_sql / 20, 4),
                "scout_enriched_ranked": round(delta_on_sql / 20, 4),
            },
            "recall": {
                "scout_structural": stats(delta_off),
                "scout_enriched_ranked": stats(delta_on),
                "delta_mean_on_minus_off": round(mean(delta_on) - mean(delta_off), 4),
            },
            "per_level": {
                lvl: {
                    "scout_structural": stats(by["off"]),
                    "scout_enriched_ranked": stats(by["on"]),
                    "delta": round(mean(by["on"]) - mean(by["off"]), 4),
                }
                for lvl, by in delta_by_level.items()
            },
            "semantic_labels": {
                "scout_structural": label_counts(delta_labels_off),
                "scout_enriched_ranked": label_counts(delta_labels_on),
            },
            "wilcoxon_paired": wilcoxon_paired(delta_off, delta_on),
        },
        "combined_n84": {
            "recall": {
                "scout_structural": stats(combined_off),
                "scout_enriched_ranked": stats(combined_on),
                "delta_mean_on_minus_off": round(mean(combined_on) - mean(combined_off), 4),
            },
            "per_language": {
                lng: {
                    "scout_structural": stats(by["off"]),
                    "scout_enriched_ranked": stats(by["on"]),
                    "delta": round(mean(by["on"]) - mean(by["off"]), 4),
                }
                for lng, by in combined_by_lang.items()
            },
            "per_level": {
                lvl: {
                    "scout_structural": stats(by["off"]),
                    "scout_enriched_ranked": stats(by["on"]),
                    "delta": round(mean(by["on"]) - mean(by["off"]), 4),
                }
                for lvl, by in sorted(combined_by_level.items())
            },
            "wilcoxon_paired_all84": wilcoxon_paired(combined_off, combined_on),
            "sensitivity_both_produced_sql": {
                "n": len(both_sql_ids),
                "off_mean": round(mean(sens_off), 4) if sens_off else None,
                "on_mean": round(mean(sens_on), 4) if sens_on else None,
                "delta": round(mean(sens_on) - mean(sens_off), 4) if sens_off else None,
                "wilcoxon": wilcoxon_paired(sens_off, sens_on) if sens_off else None,
            },
        },
    }

    OUT.write_text(json.dumps(summary, indent=2, default=str))

    # ---- Print table-ready summaries ----
    print("=" * 72)
    print("DELTA COHORT (n=20, German L1-L2)")
    print("=" * 72)
    print(f"  SDG-off  recall: mean={summary['delta_cohort_n20']['recall']['scout_structural']['mean']:.4f}  "
          f"sql_rate={summary['delta_cohort_n20']['sql_generation']['scout_structural']:.2%}")
    print(f"  SDG-on   recall: mean={summary['delta_cohort_n20']['recall']['scout_enriched_ranked']['mean']:.4f}  "
          f"sql_rate={summary['delta_cohort_n20']['sql_generation']['scout_enriched_ranked']:.2%}")
    print(f"  delta  : {summary['delta_cohort_n20']['recall']['delta_mean_on_minus_off']:+.4f}")
    print()
    for lvl in ("L1_DE", "L2_DE"):
        pl = summary["delta_cohort_n20"]["per_level"].get(lvl)
        if pl:
            print(f"  {lvl}: off={pl['scout_structural']['mean']:.4f}  on={pl['scout_enriched_ranked']['mean']:.4f}  "
                  f"delta={pl['delta']:+.4f}")
    print()
    print(f"  semantic labels (off): {summary['delta_cohort_n20']['semantic_labels']['scout_structural']}")
    print(f"  semantic labels (on):  {summary['delta_cohort_n20']['semantic_labels']['scout_enriched_ranked']}")
    w = summary["delta_cohort_n20"]["wilcoxon_paired"]
    print(f"  Wilcoxon (delta cohort): W={w.get('wilcoxon_W', 'NA')}  p={w.get('wilcoxon_p_one_sided', 'NA')}  "
          f"wins_on/off/ties={w['wins_on']}/{w['wins_off']}/{w['ties']}")

    print()
    print("=" * 72)
    print("COMBINED N=84")
    print("=" * 72)
    c = summary["combined_n84"]
    print(f"  SDG-off  recall: mean={c['recall']['scout_structural']['mean']:.4f}  sd={c['recall']['scout_structural']['sd']:.4f}")
    print(f"  SDG-on   recall: mean={c['recall']['scout_enriched_ranked']['mean']:.4f}  sd={c['recall']['scout_enriched_ranked']['sd']:.4f}")
    print(f"  delta  : {c['recall']['delta_mean_on_minus_off']:+.4f}")
    print()
    print("  per-language:")
    for lng, pl in c["per_language"].items():
        print(f"    {lng}: n={pl['scout_structural']['n']:>2}  "
              f"off={pl['scout_structural']['mean']:.4f}  on={pl['scout_enriched_ranked']['mean']:.4f}  "
              f"delta={pl['delta']:+.4f}")
    print()
    print("  per-level:")
    for lvl, pl in c["per_level"].items():
        print(f"    {lvl:<6} n={pl['scout_structural']['n']:>2}  "
              f"off={pl['scout_structural']['mean']:.4f}  on={pl['scout_enriched_ranked']['mean']:.4f}  "
              f"delta={pl['delta']:+.4f}")
    w = c["wilcoxon_paired_all84"]
    print()
    print(f"  Wilcoxon N=84: W={w.get('wilcoxon_W', 'NA')}  p={w.get('wilcoxon_p_one_sided', 'NA')}  "
          f"wins_on/off/ties={w['wins_on']}/{w['wins_off']}/{w['ties']}  "
          f"rbc={w.get('rank_biserial_proxy', 'NA')}")
    sens = c["sensitivity_both_produced_sql"]
    print(f"  Sensitivity (both SQL): n={sens['n']}  off={sens['off_mean']:.4f}  on={sens['on_mean']:.4f}  "
          f"delta={sens['delta']:+.4f}")
    if sens.get("wilcoxon"):
        sw = sens["wilcoxon"]
        print(f"    Wilcoxon (sens): W={sw.get('wilcoxon_W', 'NA')}  p={sw.get('wilcoxon_p_one_sided', 'NA')}")

    print()
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
