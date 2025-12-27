from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


DATASET_PATH = Path("eval/datasets/cockpit_queries.jsonl")


def load_cockpit_queries(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Load a small subset of cockpit benchmark queries for shared tests.

    Returns a list of entries with at least:
    - id: str
    - question: str
    - expected_tables: List[str]
    """
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Benchmark dataset not found: {DATASET_PATH}")

    items: List[Dict[str, Any]] = []
    with DATASET_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            items.append(payload)
            if len(items) >= limit:
                break

    return items

