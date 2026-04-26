"""Write a filtered dataset + contracts file containing only the 20 new German L1-L2 queries.

Used as the runner input so we do not re-run the existing 64 canonical queries.
The canonical 84-query file remains unchanged.
"""
import json
from pathlib import Path

ROOT = Path("/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis")
DATASET = ROOT / "code/eval/datasets/northwind_extended_difficulty_v1.jsonl"
CONTRACTS = ROOT / "code/eval/datasets/northwind_extended_difficulty_v1.contracts.json"

OUT_DIR = ROOT / "evaluation/H2a/20260418_de_l1l2_drafts"
OUT_JSONL = OUT_DIR / "de_l1l2_only.jsonl"
OUT_CONTRACTS = OUT_DIR / "de_l1l2_only.contracts.json"

TARGETS = {f"NW_DE_{i:02d}" for i in range(1, 11)} | {f"NL_DE_{i:02d}" for i in range(1, 11)}


def main() -> int:
    dataset_rows = []
    with DATASET.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row["id"] in TARGETS:
                dataset_rows.append(row)

    contracts = [c for c in json.loads(CONTRACTS.read_text()) if c["query_id"] in TARGETS]

    assert len(dataset_rows) == 20, f"Expected 20 dataset rows, got {len(dataset_rows)}"
    assert len(contracts) == 20, f"Expected 20 contract rows, got {len(contracts)}"
    assert {r["id"] for r in dataset_rows} == TARGETS
    assert {c["query_id"] for c in contracts} == TARGETS

    with OUT_JSONL.open("w") as f:
        for row in dataset_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    OUT_CONTRACTS.write_text(json.dumps(contracts, indent=2, ensure_ascii=False))

    print(f"Filtered dataset: {OUT_JSONL} ({len(dataset_rows)} queries)")
    print(f"Filtered contracts: {OUT_CONTRACTS} ({len(contracts)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
