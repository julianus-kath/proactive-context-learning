"""H2a semantic labeling — delta cohort only (20 German L1-L2 queries, 40 trials).

Mirrors `code/eval/runs/20260416_h2a_semantic_labels/label_pipeline.py` exactly for
row-matching rules, canonicalisation, and statement timeout. Scoped to the 20 new
query IDs (NW_DE_*, NL_DE_*) and the two new April-18 run directories.

Outputs land next to the two April-18 run dirs under evaluation/H2a/.
"""
from __future__ import annotations

import json
import math
import sys
import time
from decimal import Decimal
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import psycopg2
import psycopg2.extensions
import psycopg2.extras

# ---------- Paths ----------

THESIS_ROOT = Path("/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis")
EVAL_H2A = THESIS_ROOT / "evaluation/H2a"

DATASET = THESIS_ROOT / "code/eval/datasets/northwind_extended_difficulty_v1.jsonl"
CONTRACTS = THESIS_ROOT / "code/eval/datasets/northwind_extended_difficulty_v1.contracts.json"
REF_L1_L4 = THESIS_ROOT / "code/eval/runs/20260416_h2a_semantic_labels/reference_sql_l1_l4.json"

RUN_OFF = EVAL_H2A / "20260418_h2a_de_l1l2_scout_structural/results_raw.jsonl"
RUN_ON = EVAL_H2A / "20260418_h2a_de_l1l2_scout_enriched_ranked/results_raw.jsonl"
OUT_DIR = EVAL_H2A / "20260418_h2a_de_l1l2_semantic_labels"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DB_DSN = dict(host="localhost", port=55432, user="postgres", password="postgres", dbname="northwind")
STATEMENT_TIMEOUT_MS = 15000

TARGETS = {f"NW_DE_{i:02d}" for i in range(1, 11)} | {f"NL_DE_{i:02d}" for i in range(1, 11)}


# ---------- Helpers (verbatim from label_pipeline.py) ----------


def canonical_value(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, bool):
        return bool(v)
    if isinstance(v, (int,)):
        return float(v)
    if isinstance(v, Decimal):
        return round(float(v), 6)
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return round(v, 6)
    if isinstance(v, datetime):
        if v.hour == 0 and v.minute == 0 and v.second == 0 and v.microsecond == 0:
            return v.date().isoformat()
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    s = str(v).strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        if "T" in s:
            date_part, time_part = s.split("T", 1)
            if time_part.startswith("00:00:00") and all(
                date_part[i].isdigit() or date_part[i] == "-" for i in range(len(date_part))
            ):
                return date_part
    return s


def is_numeric(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def canonical_row(row: tuple) -> tuple:
    return tuple(canonical_value(c) for c in row)


def rows_sequence(rows: list[tuple]) -> list[tuple]:
    return [canonical_row(r) for r in rows]


def connect():
    conn = psycopg2.connect(**DB_DSN)
    conn.set_session(readonly=True, autocommit=False)
    with conn.cursor() as cur:
        cur.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")
    conn.commit()
    return conn


def run_sql(conn, sql: str) -> tuple[Optional[list[str]], Optional[list[tuple]], Optional[str]]:
    if not sql or not sql.strip():
        return None, None, "empty_sql"
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            if cur.description is None:
                conn.rollback()
                return None, None, "no_resultset"
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        conn.rollback()
        return cols, rows, None
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return None, None, f"{type(e).__name__}: {str(e).strip()[:400]}"


def has_order_by(sql: str) -> bool:
    if not sql:
        return False
    sql_up = sql.upper()
    depth = 0
    out = []
    for ch in sql_up:
        if ch == "(":
            depth += 1
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            continue
        if depth == 0:
            out.append(ch)
    return " ORDER BY " in "".join(out)


def row_texts_ms(row: tuple) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in row:
        if isinstance(v, str) and v:
            key = v.lower()
            out[key] = out.get(key, 0) + 1
    return out


def row_nums_ms(row: tuple) -> dict[float, int]:
    out: dict[float, int] = {}
    for v in row:
        if is_numeric(v):
            key = round(float(v), 2)
            out[key] = out.get(key, 0) + 1
    return out


def ms_subset_eq(sub: dict, sup: dict) -> bool:
    for k, v in sub.items():
        if sup.get(k, 0) < v:
            return False
    return True


def rows_match_semantically(gen_row: tuple, ref_row: tuple) -> tuple[bool, str]:
    gen_texts = row_texts_ms(gen_row)
    ref_texts = row_texts_ms(ref_row)
    gen_nums = row_nums_ms(gen_row)
    ref_nums = row_nums_ms(ref_row)

    texts_ok = ms_subset_eq(gen_texts, ref_texts) or ms_subset_eq(ref_texts, gen_texts)
    nums_ok = ms_subset_eq(gen_nums, ref_nums) or ms_subset_eq(ref_nums, gen_nums)

    if not texts_ok or not nums_ok:
        return False, ""
    if not gen_texts and not gen_nums:
        return False, ""
    if not ref_texts and not ref_nums:
        return False, ""

    if gen_texts == ref_texts and gen_nums == ref_nums:
        return True, "exact"
    if gen_texts and ref_texts and (gen_nums or ref_nums):
        return True, "text+nums_subset"
    if gen_nums and ref_nums and not gen_texts and not ref_texts:
        return True, "nums_only"
    if gen_nums and ref_nums and (gen_texts != ref_texts):
        return True, "text+nums_subset"
    return True, "partial"


def match_rows(gen_rows: list[tuple], ref_rows: list[tuple]):
    pairs: list[tuple[int, int]] = []
    used_ref: set[int] = set()
    unmatched_gen: list[int] = []
    for gi, g in enumerate(gen_rows):
        best_ri = -1
        best_kind = ""
        for ri, r in enumerate(ref_rows):
            if ri in used_ref:
                continue
            ok, kind = rows_match_semantically(g, r)
            if ok:
                if kind == "exact":
                    best_ri, best_kind = ri, kind
                    break
                if best_ri == -1:
                    best_ri, best_kind = ri, kind
        if best_ri >= 0:
            pairs.append((gi, best_ri))
            used_ref.add(best_ri)
        else:
            unmatched_gen.append(gi)
    unmatched_ref = [i for i in range(len(ref_rows)) if i not in used_ref]
    return pairs, unmatched_gen, unmatched_ref


def score_label(ref_rows, gen_rows, ref_has_order, gen_has_order, ref_rowcount, gen_rowcount):
    ref_n = len(ref_rows)
    gen_n = len(gen_rows)
    if ref_n == 0 and gen_n == 0:
        return "CORRECT", "Both result sets empty."
    if ref_n == 0 and gen_n > 0:
        return "INCORRECT", "Reference empty but agent returned rows."
    if gen_n == 0 and ref_n > 0:
        return "INCORRECT", "Agent empty but reference returned rows."
    if ref_n == 1 and gen_n == 1:
        ok, kind = rows_match_semantically(gen_rows[0], ref_rows[0])
        if ok:
            if kind == "exact":
                return "CORRECT", "Single-row aggregate matches reference exactly."
            return "PARTIAL", "Single-row aggregate: values align with reference, column projection differs."
        r_nums = set(row_nums_ms(ref_rows[0]))
        g_nums = set(row_nums_ms(gen_rows[0]))
        if r_nums & g_nums:
            return "PARTIAL", f"Single-row aggregate: {len(r_nums & g_nums)}/{len(r_nums)} numeric values match."
        return "INCORRECT", f"Single-row aggregate differs (ref={sorted(r_nums)}, gen={sorted(g_nums)})."
    pairs, unmatched_gen, unmatched_ref = match_rows(gen_rows, ref_rows)
    if not unmatched_gen and not unmatched_ref and gen_n == ref_n:
        exact = all(
            rows_match_semantically(gen_rows[gi], ref_rows[ri])[1] == "exact"
            for gi, ri in pairs
        )
        if exact:
            if ref_has_order:
                ordered = all(pairs[i][1] == i for i in range(len(pairs)))
                if ordered:
                    return "CORRECT", "Identical ordered rowset (exact match, rows in same order)."
                return "PARTIAL", "Same rowset but ordering differs (tie-breaking)."
            return "CORRECT", "Identical rowset (exact match, unordered)."
        if ref_has_order:
            ordered = all(pairs[i][1] == i for i in range(len(pairs)))
            if ordered:
                return "CORRECT", "Rowset matches reference in order; column projection differs slightly."
            return "PARTIAL", "Rowset matches reference but ordering differs."
        return "CORRECT", "Rowset matches reference (column projection differs)."
    if not unmatched_gen and unmatched_ref:
        if ref_has_order:
            prefix_ok = all(pairs[i][1] == i for i in range(len(pairs)))
            if prefix_ok:
                return "PARTIAL", f"Agent returned top {gen_n}/{ref_n} rows; ordered prefix matches reference."
        return "PARTIAL", f"Agent returned {gen_n}/{ref_n} rows; all match a subset of the reference."
    if unmatched_gen and not unmatched_ref:
        return "PARTIAL", f"Agent returned {gen_n} rows covering all {ref_n} reference rows plus {len(unmatched_gen)} extras."
    matched = len(pairs)
    if matched > 0:
        ref_cov = matched / ref_n
        gen_cov = matched / gen_n
        if ref_cov >= 0.8 and gen_cov >= 0.8:
            return "PARTIAL", f"Rowsets largely overlap ({matched} matched, {len(unmatched_ref)} ref-only, {len(unmatched_gen)} gen-only)."
        if ref_cov >= 0.5 and gen_cov >= 0.5:
            return "PARTIAL", f"Partial overlap: {matched} matched, {len(unmatched_ref)} ref-only, {len(unmatched_gen)} gen-only."
    return "INCORRECT", f"Rowsets diverge: {matched}/{ref_n} reference rows matched, {matched}/{gen_n} agent rows matched."


# ---------- IO ----------


def load_dataset() -> dict[str, dict]:
    queries = {}
    with DATASET.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj["id"] in TARGETS:
                queries[obj["id"]] = obj
    return queries


def load_contracts() -> dict[str, list[str]]:
    with CONTRACTS.open() as f:
        data = json.load(f)
    return {row["query_id"]: row["required_tables"] for row in data if row["query_id"] in TARGETS}


def load_reference_sql() -> dict[str, str]:
    ref = json.loads(REF_L1_L4.read_text())
    return {k: v for k, v in ref.items() if k in TARGETS}


def load_run(path: Path) -> dict[str, dict]:
    rows = {}
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            rows[obj["query_id"]] = obj
    return rows


def rows_sequence_to_tuples(rowset_listoflists: list[list]) -> list[tuple]:
    return [tuple(r) for r in rowset_listoflists]


def main() -> int:
    queries = load_dataset()
    contracts = load_contracts()
    ref_sql_map = load_reference_sql()

    assert len(queries) == 20, f"Expected 20 queries, got {len(queries)}"
    assert len(contracts) == 20
    assert len(ref_sql_map) == 20
    assert set(queries) == TARGETS == set(contracts) == set(ref_sql_map)

    off_rows = load_run(RUN_OFF)
    on_rows = load_run(RUN_ON)
    assert set(off_rows) == TARGETS
    assert set(on_rows) == TARGETS

    # Execute 20 reference SQLs.
    print(f"[ref] connecting to {DB_DSN['host']}:{DB_DSN['port']}/{DB_DSN['dbname']}")
    conn = connect()
    reference_results: dict[str, dict] = {}
    with (OUT_DIR / "reference_results.jsonl").open("w") as f_ref:
        for qid in sorted(queries):
            sql = ref_sql_map[qid]
            t0 = time.time()
            cols, rows, err = run_sql(conn, sql)
            dt_ms = (time.time() - t0) * 1000.0
            if err:
                print(f"[ref] {qid}: ERROR {err}", file=sys.stderr)
                print(f"     SQL:\n{sql}", file=sys.stderr)
                return 2
            reference_results[qid] = {
                "query_id": qid,
                "reference_sql": sql,
                "reference_columns": cols,
                "reference_rowset": [list(r) for r in rows_sequence(rows)],
                "reference_rowcount": len(rows),
                "reference_has_order_by": has_order_by(sql),
                "elapsed_ms": round(dt_ms, 1),
            }
            f_ref.write(json.dumps(reference_results[qid], default=str) + "\n")
            print(f"[ref] {qid}: {len(rows)} rows in {dt_ms:.0f} ms")
    conn.close()

    # Execute 40 generated SQLs and label.
    conn = connect()
    labels_out = []
    for condition_name, run_rows in (("scout_structural", off_rows), ("scout_enriched_ranked", on_rows)):
        for qid in sorted(queries):
            row = run_rows[qid]
            q = queries[qid]
            ref_info = reference_results[qid]
            gen_sql = row.get("generated_sql") or ""
            sql_present = bool(row.get("sql_present"))
            run_error = row.get("error")
            gen_rowset: list = []
            gen_rowcount: Optional[int] = None
            if run_error:
                label = "ERROR"
                label_reason = f"Pipeline/system error recorded in source run artifact: {run_error}"
            elif not sql_present:
                label = "INCORRECT"
                label_reason = "Agent produced no SQL (sql_present=false)."
            else:
                cols, rows, exec_err = run_sql(conn, gen_sql)
                if exec_err:
                    label = "INCORRECT"
                    label_reason = f"Generated SQL failed to execute: {exec_err}"
                else:
                    gen_rowset = [list(r) for r in rows_sequence(rows)]
                    gen_rowcount = len(rows)
                    label, label_reason = score_label(
                        ref_rows=rows_sequence_to_tuples(ref_info["reference_rowset"]),
                        gen_rows=[tuple(r) for r in gen_rowset],
                        ref_has_order=ref_info["reference_has_order_by"],
                        gen_has_order=has_order_by(gen_sql),
                        ref_rowcount=ref_info["reference_rowcount"],
                        gen_rowcount=gen_rowcount,
                    )
            labels_out.append({
                "query_id": qid,
                "condition": condition_name,
                "category": q.get("category"),
                "language": q.get("language"),
                "label": label,
                "label_reason": label_reason,
                "sql_present": sql_present,
                "generated_rowcount": gen_rowcount,
                "reference_rowcount": ref_info["reference_rowcount"],
                "generated_rowset": gen_rowset if gen_rowcount is not None and gen_rowcount <= 50 else None,
                "generated_rowset_truncated": bool(gen_rowcount is not None and gen_rowcount > 50),
                "run_error": run_error,
            })
    conn.close()

    assert len(labels_out) == 40
    per_cond_counts: dict[str, list[dict]] = {}
    for r in labels_out:
        per_cond_counts.setdefault(r["condition"], []).append(r)
    for c, rs in per_cond_counts.items():
        assert len(rs) == 20, f"{c} has {len(rs)} rows"
    for r in labels_out:
        assert r["label_reason"], r

    with (OUT_DIR / "semantic_labels.jsonl").open("w") as f:
        for r in labels_out:
            f.write(json.dumps(r, default=str) + "\n")

    def count_by(rows, key):
        out = {}
        for r in rows:
            k = r[key]
            out.setdefault(k, {"CORRECT": 0, "PARTIAL": 0, "INCORRECT": 0, "ERROR": 0})
            out[k][r["label"]] += 1
        return out

    summary = {"per_condition": {}, "comparison": {}}
    for cond, rows in per_cond_counts.items():
        dist = {"CORRECT": 0, "PARTIAL": 0, "INCORRECT": 0, "ERROR": 0}
        for r in rows:
            dist[r["label"]] += 1
        acceptable = dist["CORRECT"] + dist["PARTIAL"]
        summary["per_condition"][cond] = {
            "label_distribution": dist,
            "acceptable_answer_rate": round(acceptable / 20, 4),
            "per_category": count_by(rows, "category"),
            "per_language": count_by(rows, "language"),
        }
    off_rate = summary["per_condition"]["scout_structural"]["acceptable_answer_rate"]
    on_rate = summary["per_condition"]["scout_enriched_ranked"]["acceptable_answer_rate"]
    summary["comparison"]["delta_acceptable_rate_on_minus_off"] = round(on_rate - off_rate, 4)

    with (OUT_DIR / "semantic_summary.json").open("w") as f:
        json.dump(summary, f, indent=2, default=str)

    print("\n=== Semantic label distribution (delta cohort, n=20) ===")
    for cond, block in summary["per_condition"].items():
        print(f"\n{cond}: {block['label_distribution']}")
        print(f"  acceptable rate = {block['acceptable_answer_rate']:.2%}")
    print(
        f"\nDelta (acceptable_rate ON - OFF) = "
        f"{summary['comparison']['delta_acceptable_rate_on_minus_off']:+.2%}"
    )
    print(f"\nOutputs: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
