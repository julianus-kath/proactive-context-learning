"""Verify that the 20 L1-L2 reference SQL statements execute on live Northwind.

For each qid in NW1..NW10, NL1..NL10:
- execute reference SQL
- print status (rows returned or error)
- capture a small row-count summary for the draft report
"""
import json
import psycopg2
from pathlib import Path

REF_SQL_PATH = Path(
    "/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/"
    "code/eval/runs/20260416_h2a_semantic_labels/reference_sql_l1_l4.json"
)
DSN = dict(host="localhost", port=55432, user="postgres", password="postgres", dbname="northwind")
STATEMENT_TIMEOUT_MS = 15000

TARGETS = [f"NW{i}" for i in range(1, 11)] + [f"NL{i}" for i in range(1, 11)]


def main() -> int:
    ref_sql = json.loads(REF_SQL_PATH.read_text())
    conn = psycopg2.connect(**DSN)
    conn.set_session(readonly=True, autocommit=False)
    with conn.cursor() as cur:
        cur.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")
    conn.commit()

    results = []
    fail = 0
    for qid in TARGETS:
        sql = ref_sql.get(qid)
        if not sql:
            print(f"[{qid}] MISSING from reference_sql_l1_l4.json")
            results.append({"qid": qid, "status": "MISSING"})
            fail += 1
            continue
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()
            conn.rollback()
            n = len(rows)
            head = rows[0] if rows else None
            print(f"[{qid}] OK: {n} rows, cols={cols[:6]}, first_row={head}")
            results.append({"qid": qid, "status": "OK", "rowcount": n, "cols": cols, "first_row": [str(v) for v in head] if head else None})
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            print(f"[{qid}] FAIL: {type(e).__name__}: {e}")
            results.append({"qid": qid, "status": "FAIL", "error": f"{type(e).__name__}: {e}"})
            fail += 1

    out = REF_SQL_PATH.parent.parent.parent / "evaluation/H2a/20260418_de_l1l2_drafts/reference_sql_verification.json"
    # Write next to the draft instead of inside code tree.
    out = Path(
        "/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/"
        "evaluation/H2a/20260418_de_l1l2_drafts/reference_sql_verification.json"
    )
    out.write_text(json.dumps(results, indent=2, default=str))
    conn.close()
    print(f"\nWrote {out}")
    print(f"Failures: {fail}/{len(TARGETS)}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
