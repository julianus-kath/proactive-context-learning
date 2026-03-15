"""
Normalize partner-required table labels against a live or saved catalog.
"""

from __future__ import annotations

import argparse
import difflib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

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
    parts = [part for part in value.split(".") if part]
    return parts[-1].lower() if parts else value.lower()


def _load_labels(labels_path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    raw = json.loads(labels_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("labels"), list):
        labels = [row for row in raw["labels"] if isinstance(row, dict)]
        meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
        return labels, meta
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)], {}
    raise ValueError("labels file must be a list or object containing labels[]")


def _extract_jsonrpc_result(raw: Dict[str, Any]) -> Dict[str, Any]:
    result = raw.get("result")
    if isinstance(result, dict):
        return result
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict) and item.get("type") == "json" and isinstance(item.get("json"), dict):
                return item["json"]
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text") or "").strip()
                if text:
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, dict):
                            return parsed
                    except Exception:
                        continue
    return {}


def _load_catalog_from_mcp(mcp_url: str, mcp_api_key: str) -> Dict[str, Any]:
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": "scout_catalog_get", "arguments": {}},
        "id": 1,
    }
    with httpx.Client() as client:
        response = client.post(
            f"{mcp_url.rstrip('/')}/mcp",
            headers={"X-API-Key": mcp_api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=120.0,
        )
        response.raise_for_status()
        raw = response.json()
    parsed = _extract_jsonrpc_result(raw)
    return parsed


def _load_catalog_from_file(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise ValueError("catalog snapshot must be a JSON object")


def _extract_catalog_tables(catalog_payload: Dict[str, Any]) -> List[str]:
    catalog = catalog_payload.get("catalog") if isinstance(catalog_payload.get("catalog"), dict) else catalog_payload
    tables = catalog.get("tables") if isinstance(catalog, dict) else []
    if isinstance(tables, dict):
        rows = list(tables.values())
    elif isinstance(tables, list):
        rows = tables
    else:
        rows = []

    out: List[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        full_name = str(row.get("full_name") or row.get("name") or "").strip()
        if not full_name:
            schema = str(row.get("schema") or "").strip()
            name = str(row.get("table_name") or "").strip()
            full_name = f"{schema}.{name}" if schema and name else name
        if full_name and full_name not in out:
            out.append(full_name)
    return out


def _load_manual_overrides(path: Optional[Path]) -> Dict[str, Dict[str, str]]:
    if path is None or not path.exists():
        return {}

    raw = json.loads(path.read_text(encoding="utf-8"))
    entries: List[Dict[str, Any]] = []
    if isinstance(raw, dict) and isinstance(raw.get("overrides"), list):
        entries = [row for row in raw["overrides"] if isinstance(row, dict)]
    elif isinstance(raw, list):
        entries = [row for row in raw if isinstance(row, dict)]
    elif isinstance(raw, dict):
        for key, value in raw.items():
            if isinstance(value, str):
                entries.append(
                    {
                        "original_partner_label": key,
                        "matched_live_table": value,
                    }
                )
    out: Dict[str, Dict[str, str]] = {}
    for row in entries:
        original = str(
            row.get("original_partner_label")
            or row.get("partner_label")
            or row.get("label")
            or ""
        ).strip()
        matched = str(row.get("matched_live_table") or row.get("live_table") or "").strip()
        if not original or not matched:
            continue
        out[_normalize_table_name(original)] = {
            "original_partner_label": original,
            "matched_live_table": matched,
            "note": str(row.get("note") or row.get("notes") or "").strip(),
        }
    return out


def _prefix_candidates(label_norm: str, catalog_norms: Sequence[str], limit: int = 12) -> List[str]:
    hits: List[str] = []
    for name in catalog_norms:
        if name.startswith(label_norm) or label_norm.startswith(name):
            if name not in hits:
                hits.append(name)
        if len(hits) >= limit:
            break
    return hits


def _choose_alias_match(label_norm: str, catalog_norms: Sequence[str]) -> Tuple[Optional[str], List[str]]:
    close = difflib.get_close_matches(label_norm, list(catalog_norms), n=8, cutoff=0.7)
    pref = _prefix_candidates(label_norm, catalog_norms, limit=8)
    candidates: List[str] = []
    for item in pref + close:
        if item not in candidates:
            candidates.append(item)
    if not candidates:
        return None, []
    if len(pref) == 1:
        return pref[0], candidates
    if close:
        return close[0], candidates
    return candidates[0], candidates


def _match_label(
    original_label: str,
    catalog_norm_to_full: Dict[str, List[str]],
    manual_overrides: Dict[str, Dict[str, str]],
) -> Dict[str, Any]:
    normalized = _normalize_table_name(original_label)
    catalog_norms = sorted(catalog_norm_to_full.keys())

    if normalized in manual_overrides:
        override = manual_overrides[normalized]
        matched = override["matched_live_table"]
        return {
            "original_partner_label": original_label,
            "normalized_partner_label": normalized,
            "matched_live_table": matched,
            "match_type": "manual_confirmed",
            "candidate_matches": [matched],
            "note": override.get("note") or "",
        }

    exact_full = catalog_norm_to_full.get(normalized) or []
    if exact_full:
        return {
            "original_partner_label": original_label,
            "normalized_partner_label": normalized,
            "matched_live_table": sorted(exact_full)[0],
            "match_type": "exact",
            "candidate_matches": sorted(exact_full)[:8],
            "note": "",
        }

    alias_norm, alias_candidates_norm = _choose_alias_match(normalized, catalog_norms)
    if alias_norm:
        alias_candidates_full: List[str] = []
        for norm_name in alias_candidates_norm:
            alias_candidates_full.extend(sorted(catalog_norm_to_full.get(norm_name) or []))
        alias_candidates_full = alias_candidates_full[:8]
        matched = sorted(catalog_norm_to_full.get(alias_norm) or [alias_norm])[0]
        return {
            "original_partner_label": original_label,
            "normalized_partner_label": normalized,
            "matched_live_table": matched,
            "match_type": "alias_prefix_normalized",
            "candidate_matches": alias_candidates_full,
            "note": "",
        }

    return {
        "original_partner_label": original_label,
        "normalized_partner_label": normalized,
        "matched_live_table": None,
        "match_type": "unresolved",
        "candidate_matches": [],
        "note": "",
    }


def _render_review_md(payload: Dict[str, Any]) -> str:
    lines = [
        "# Partner Label Normalization Review",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Labels source: `{payload.get('labels_path')}`",
        f"- Catalog source: `{payload.get('catalog_source')}`",
        "",
        "## Summary",
        "",
        f"- Unique partner labels: `{payload.get('summary', {}).get('unique_partner_labels')}`",
        f"- Exact matches: `{payload.get('summary', {}).get('exact')}`",
        f"- Alias/prefix matches: `{payload.get('summary', {}).get('alias_prefix_normalized')}`",
        f"- Manual confirmed: `{payload.get('summary', {}).get('manual_confirmed')}`",
        f"- Unresolved: `{payload.get('summary', {}).get('unresolved')}`",
        "",
        "| Partner label | Match type | Matched live table | Candidate matches |",
        "|---|---|---|---|",
    ]
    for row in payload.get("mapping", []):
        candidates = ", ".join(row.get("candidate_matches") or [])
        lines.append(
            "| {label} | {match_type} | {matched} | {candidates} |".format(
                label=row.get("original_partner_label"),
                match_type=row.get("match_type"),
                matched=row.get("matched_live_table"),
                candidates=candidates,
            )
        )
    lines.append("")
    return "\n".join(lines)


def run_normalization(
    labels_path: Path,
    out_name: str,
    mcp_url: Optional[str],
    mcp_api_key: Optional[str],
    catalog_snapshot: Optional[Path],
    overrides_path: Optional[Path],
) -> Path:
    labels, labels_meta = _load_labels(labels_path)
    overrides = _load_manual_overrides(overrides_path)

    if catalog_snapshot is not None:
        catalog_payload = _load_catalog_from_file(catalog_snapshot)
        catalog_source = str(catalog_snapshot)
    else:
        if not mcp_url or not mcp_api_key:
            raise ValueError("Either --catalog-snapshot or (--mcp-url and --mcp-api-key) is required.")
        catalog_payload = _load_catalog_from_mcp(mcp_url=mcp_url, mcp_api_key=mcp_api_key)
        catalog_source = mcp_url

    catalog_full_names = _extract_catalog_tables(catalog_payload)
    catalog_norm_to_full: Dict[str, List[str]] = {}
    for full_name in catalog_full_names:
        norm = _normalize_table_name(full_name)
        catalog_norm_to_full.setdefault(norm, [])
        if full_name not in catalog_norm_to_full[norm]:
            catalog_norm_to_full[norm].append(full_name)

    partner_unique: List[str] = []
    for row in labels:
        for table in row.get("required_tables") or []:
            label = str(table).strip()
            if label and label not in partner_unique:
                partner_unique.append(label)

    mapping: List[Dict[str, Any]] = []
    for partner_label in partner_unique:
        mapping.append(
            _match_label(
                original_label=partner_label,
                catalog_norm_to_full=catalog_norm_to_full,
                manual_overrides=overrides,
            )
        )
    mapping.sort(key=lambda x: (x.get("match_type") or "", x.get("original_partner_label") or ""))

    by_normalized_label: Dict[str, Dict[str, Any]] = {
        row.get("normalized_partner_label"): row for row in mapping
    }

    normalized_labels: List[Dict[str, Any]] = []
    unresolved_total = 0
    for row in labels:
        query_id = str(row.get("query_id") or row.get("id") or "").strip()
        required_original = [str(x).strip() for x in (row.get("required_tables") or []) if str(x).strip()]

        required_entries: List[Dict[str, Any]] = []
        required_resolved: List[str] = []
        unresolved_for_query: List[str] = []
        for original_label in required_original:
            normalized = _normalize_table_name(original_label)
            entry = by_normalized_label.get(normalized) or _match_label(
                original_label=original_label,
                catalog_norm_to_full=catalog_norm_to_full,
                manual_overrides=overrides,
            )
            required_entries.append(entry)
            matched = entry.get("matched_live_table")
            if isinstance(matched, str) and matched.strip():
                if matched not in required_resolved:
                    required_resolved.append(matched)
            else:
                unresolved_for_query.append(original_label)

        unresolved_total += len(unresolved_for_query)
        normalized_labels.append(
            {
                "query_id": query_id,
                "question": row.get("question"),
                "required_tables_original": required_original,
                "required_table_entries": required_entries,
                # Primary scoring uses resolved-only denominator.
                "required_tables": required_resolved,
                "required_tables_resolved": required_resolved,
                "unresolved_required_labels": unresolved_for_query,
                "required_columns": row.get("required_columns") or [],
                "external_required_sources": row.get("external_required_sources") or [],
                "notes": row.get("notes"),
            }
        )

    summary = {
        "unique_partner_labels": len(partner_unique),
        "exact": sum(1 for row in mapping if row.get("match_type") == "exact"),
        "alias_prefix_normalized": sum(1 for row in mapping if row.get("match_type") == "alias_prefix_normalized"),
        "manual_confirmed": sum(1 for row in mapping if row.get("match_type") == "manual_confirmed"),
        "unresolved": sum(1 for row in mapping if row.get("match_type") == "unresolved"),
        "queries": len(normalized_labels),
        "unresolved_labels_across_queries": unresolved_total,
    }

    payload = {
        "generated_at_utc": _utc_now(),
        "labels_path": str(labels_path),
        "labels_meta": labels_meta,
        "catalog_source": catalog_source,
        "catalog_table_count": len(catalog_full_names),
        "overrides_path": str(overrides_path) if overrides_path else None,
        "summary": summary,
        "mapping": mapping,
        "labels": normalized_labels,
    }

    out_dir = Path(__file__).resolve().parent / "runs" / f"{_timestamp()}_{out_name}"
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "label_normalization.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "label_normalization_review.md").write_text(
        _render_review_md(payload),
        encoding="utf-8",
    )
    normalized_eval_labels = {
        "meta": {
            **labels_meta,
            "generated_at_utc": _utc_now(),
            "normalization_source": str(out_dir / "label_normalization.json"),
            "scoring_policy": "resolved_only_primary_recall",
            "unresolved_labels_explicit": True,
        },
        "labels": normalized_labels,
    }
    (out_dir / "cockpit_partner_table_labels_v1.normalized.json").write_text(
        json.dumps(normalized_eval_labels, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Output: {out_dir}")
    print(
        "Match summary: "
        f"exact={summary['exact']}, alias={summary['alias_prefix_normalized']}, "
        f"manual={summary['manual_confirmed']}, unresolved={summary['unresolved']}"
    )
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize partner table labels against live catalog names.")
    parser.add_argument(
        "--table-labels",
        default=str(Path(__file__).resolve().parent / "datasets" / "cockpit_partner_table_labels_v1.json"),
    )
    parser.add_argument("--mcp-url", default=None)
    parser.add_argument("--mcp-api-key", default=None)
    parser.add_argument("--catalog-snapshot", default=None, help="Optional local catalog JSON snapshot.")
    parser.add_argument(
        "--manual-overrides",
        default=str(Path(__file__).resolve().parent / "datasets" / "cockpit_partner_table_label_overrides_v1.json"),
    )
    parser.add_argument("--out-name", default="cockpit_partner_label_normalization")
    args = parser.parse_args()

    labels_path = Path(args.table_labels).resolve()
    if not labels_path.exists():
        raise FileNotFoundError(f"labels file not found: {labels_path}")

    catalog_snapshot = Path(args.catalog_snapshot).resolve() if args.catalog_snapshot else None
    if catalog_snapshot is not None and not catalog_snapshot.exists():
        raise FileNotFoundError(f"catalog snapshot not found: {catalog_snapshot}")

    overrides_path = Path(args.manual_overrides).resolve() if args.manual_overrides else None
    if overrides_path is not None and not overrides_path.exists():
        overrides_path = None

    run_normalization(
        labels_path=labels_path,
        out_name=args.out_name,
        mcp_url=args.mcp_url,
        mcp_api_key=args.mcp_api_key,
        catalog_snapshot=catalog_snapshot,
        overrides_path=overrides_path,
    )


if __name__ == "__main__":
    main()
