"""
Check partner-required table labels against live Scout catalog tables.
"""

from __future__ import annotations

import argparse
import difflib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx


def _utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _normalize_table_name(name: str) -> str:
    value = (name or "").strip().replace('"', "").replace("[", "").replace("]", "")
    value = value.rstrip(",")
    if not value:
        return value
    parts = [p for p in value.split(".") if p]
    return parts[-1].lower() if parts else value.lower()


def _load_labels(labels_path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    raw = json.loads(labels_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("labels"), list):
        return raw["labels"], (raw.get("meta") if isinstance(raw.get("meta"), dict) else {})
    if isinstance(raw, list):
        return raw, {}
    raise ValueError("labels file must be list or object with labels[]")


def _call_scout_catalog_get(client: httpx.Client, mcp_url: str, api_key: str) -> Dict[str, Any]:
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": "scout_catalog_get", "arguments": {}},
        "id": 1,
    }
    response = client.post(
        f"{mcp_url.rstrip('/')}/mcp",
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=120.0,
    )
    response.raise_for_status()
    body = response.json()
    result = body.get("result")
    text = ""
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text") or "")
                break
    if not text:
        raise RuntimeError("scout_catalog_get returned empty text")
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise RuntimeError("scout_catalog_get text is not a JSON object")
    return parsed


def _extract_catalog_table_names(catalog_payload: Dict[str, Any]) -> List[str]:
    catalog = catalog_payload.get("catalog") if isinstance(catalog_payload.get("catalog"), dict) else {}
    tables = catalog.get("tables") or []
    if isinstance(tables, dict):
        tables = list(tables.values())
    out: List[str] = []
    for row in tables:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        normalized = _normalize_table_name(name)
        if normalized and normalized not in out:
            out.append(normalized)
    return out


def _render_md(payload: Dict[str, Any]) -> str:
    lines = [
        "# Partner Label vs Catalog Check",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- MCP URL: `{payload.get('mcp_url')}`",
        f"- Labels path: `{payload.get('labels_path')}`",
        "",
        "## Summary",
        "",
        f"- Unique labeled tables: `{payload.get('summary', {}).get('unique_labeled_tables')}`",
        f"- Catalog tables: `{payload.get('summary', {}).get('catalog_tables')}`",
        f"- Missing labeled tables: `{payload.get('summary', {}).get('missing_tables_count')}`",
        "",
        "## Missing Labels",
        "",
        "| Missing labeled table | Closest catalog candidates |",
        "|---|---|",
    ]
    for row in payload.get("missing_tables", []):
        lines.append(
            f"| {row.get('missing_table')} | {', '.join(row.get('closest_catalog_candidates') or [])} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check partner table labels against live catalog names.")
    parser.add_argument(
        "--table-labels",
        default=str(Path(__file__).resolve().parent / "datasets" / "cockpit_partner_table_labels_v1.json"),
    )
    parser.add_argument("--mcp-url", default="http://localhost:8000")
    parser.add_argument("--mcp-api-key", default="supersecretapikey")
    parser.add_argument("--out-name", default="cockpit_partner_label_catalog_check")
    args = parser.parse_args()

    labels_path = Path(args.table_labels).resolve()
    if not labels_path.exists():
        raise FileNotFoundError(f"labels file not found: {labels_path}")

    labels, labels_meta = _load_labels(labels_path)
    with httpx.Client() as client:
        catalog_payload = _call_scout_catalog_get(client, args.mcp_url, args.mcp_api_key)
    catalog_table_names = _extract_catalog_table_names(catalog_payload)
    catalog_set = set(catalog_table_names)

    labeled_tables = sorted(
        {
            _normalize_table_name(str(table))
            for row in labels
            if isinstance(row, dict)
            for table in (row.get("required_tables") or [])
            if str(table).strip()
        }
    )
    missing = [table for table in labeled_tables if table not in catalog_set]

    missing_rows: List[Dict[str, Any]] = []
    for table in missing:
        missing_rows.append(
            {
                "missing_table": table,
                "closest_catalog_candidates": difflib.get_close_matches(
                    table, catalog_table_names, n=8, cutoff=0.6
                ),
            }
        )

    payload = {
        "generated_at_utc": _utc_now(),
        "mcp_url": args.mcp_url,
        "labels_path": str(labels_path),
        "labels_meta": labels_meta,
        "summary": {
            "unique_labeled_tables": len(labeled_tables),
            "catalog_tables": len(catalog_table_names),
            "missing_tables_count": len(missing),
        },
        "missing_tables": missing_rows,
    }

    out_dir = Path(__file__).resolve().parent / "runs" / f"{_timestamp()}_{args.out_name}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "label_catalog_check.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (out_dir / "label_catalog_check.md").write_text(_render_md(payload), encoding="utf-8")

    print(f"Output: {out_dir}")
    print(
        f"Missing labeled tables: {payload['summary']['missing_tables_count']}/"
        f"{payload['summary']['unique_labeled_tables']}"
    )


if __name__ == "__main__":
    main()
