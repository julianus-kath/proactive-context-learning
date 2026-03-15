"""
Run MCP search_tables evaluation against partner-provided cockpit table labels.

This script is useful when the MCP server is reachable but /process_query is not.
It evaluates table retrieval quality directly from search_tables results.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx


K_VALUES: Tuple[int, ...] = (1, 3, 5, 10, 25)
SEARCH_RESULT_TABLE_PATTERN = re.compile(
    r"^\s*(?:[•*\-]|\d+[.)])\s+((?:[A-Za-z_][A-Za-z0-9_]*)\.(?:[A-Za-z_][A-Za-z0-9_]*))\b",
    re.MULTILINE,
)


class RateLimitError(RuntimeError):
    pass


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


def _dedupe_keep_order(values: List[str]) -> List[str]:
    out: List[str] = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return out


def _load_dataset(path: Path) -> Dict[str, Dict[str, Any]]:
    rows: Dict[str, Dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            query_id = str(row.get("id") or "").strip()
            if not query_id:
                continue
            rows[query_id] = row
    return rows


def _load_labels(path: Path) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("labels"), list):
        labels = raw["labels"]
        meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    elif isinstance(raw, list):
        labels = raw
        meta = {}
    else:
        raise ValueError("Table labels file must be a list or an object with a 'labels' list.")

    by_id: Dict[str, Dict[str, Any]] = {}
    for label in labels:
        if not isinstance(label, dict):
            continue
        query_id = str(label.get("query_id") or label.get("id") or "").strip()
        if not query_id:
            continue
        by_id[query_id] = label
    return by_id, meta


def _extract_ranked_tables_from_text(text: str) -> List[str]:
    marker = "Full response (JSON):"
    if marker in (text or ""):
        json_blob = text.split(marker, 1)[1].strip()
        try:
            payload = json.loads(json_blob)
            results = (((payload or {}).get("data") or {}).get("results")) or []
            ranked_from_json: List[str] = []
            for item in results:
                if not isinstance(item, dict):
                    continue
                full_name = item.get("full_name")
                if isinstance(full_name, str) and full_name.strip():
                    name = full_name
                else:
                    schema = str(item.get("schema") or "").strip()
                    table = str(item.get("name") or "").strip()
                    name = f"{schema}.{table}" if schema and table else table
                normalized = _normalize_table_name(name)
                if normalized and normalized not in ranked_from_json:
                    ranked_from_json.append(normalized)
            if ranked_from_json:
                return ranked_from_json
        except Exception:
            pass

    ranked_from_lines: List[str] = []
    for full_name in SEARCH_RESULT_TABLE_PATTERN.findall(text or ""):
        normalized = _normalize_table_name(full_name)
        if normalized and normalized not in ranked_from_lines:
            ranked_from_lines.append(normalized)
    return ranked_from_lines


def _extract_source_metadata(text: str) -> Dict[str, Any]:
    marker = "Full response (JSON):"
    if marker not in (text or ""):
        return {}
    json_blob = text.split(marker, 1)[1].strip()
    try:
        payload = json.loads(json_blob)
        metadata: Dict[str, Any] = {}
        for key in ("source", "ranking_backend", "cached", "execution_time_ms", "source_details"):
            if key in payload:
                metadata[key] = payload[key]
        return metadata
    except Exception:
        return {}


def _call_health(client: httpx.Client, mcp_url: str, api_key: str) -> Dict[str, Any]:
    response = client.get(
        f"{mcp_url.rstrip('/')}/health",
        headers={"X-API-Key": api_key},
        timeout=30.0,
    )
    if response.status_code == 429:
        raise RateLimitError("429 while calling MCP /health")
    response.raise_for_status()
    return response.json()


def _call_search_tables(
    client: httpx.Client,
    mcp_url: str,
    api_key: str,
    query: str,
    limit: int,
) -> Dict[str, Any]:
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "search_tables",
            "arguments": {"query": query, "limit": limit},
        },
        "id": 1,
    }
    response = client.post(
        f"{mcp_url.rstrip('/')}/mcp",
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=120.0,
    )
    text_body = response.text or ""
    if response.status_code == 429 or "insufficient_quota" in text_body or '"code":429' in text_body:
        raise RateLimitError("429 / insufficient_quota while calling MCP search_tables")
    response.raise_for_status()
    body = response.json()
    result = body.get("result")
    text = ""
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text") or "")
                break
    return {
        "raw": body,
        "text": text,
        "ranked_tables": _extract_ranked_tables_from_text(text),
        "source_metadata": _extract_source_metadata(text),
    }


def _compute_metrics(required_tables: List[str], ranked_tables: List[str]) -> Dict[str, Any]:
    req = _dedupe_keep_order(required_tables)
    req_set = set(req)
    retrieved = _dedupe_keep_order(ranked_tables)

    metrics: Dict[str, Any] = {
        "required_tables": req,
        "retrieved_tables_ranked": retrieved,
    }
    for k in K_VALUES:
        topk = retrieved[:k]
        inter = req_set.intersection(set(topk))
        recall = (len(inter) / len(req_set)) if req_set else None
        metrics[f"recall_at_{k}"] = recall
        metrics[f"required_tables_ok_at_{k}"] = req_set.issubset(set(topk)) if req_set else None
        metrics[f"any_required_in_top_{k}"] = len(inter) > 0 if req_set else None

    first_required_rank: Optional[int] = None
    for idx, table in enumerate(retrieved, start=1):
        if table in req_set:
            first_required_rank = idx
            break
    metrics["first_required_rank"] = first_required_rank
    metrics["reciprocal_rank"] = (1.0 / first_required_rank) if first_required_rank else 0.0
    return metrics


def _aggregate(per_query: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(per_query)
    if total == 0:
        return {"total_queries": 0}

    agg: Dict[str, Any] = {"total_queries": total}
    mrr = sum(float(row.get("reciprocal_rank") or 0.0) for row in per_query) / total
    agg["mrr"] = round(mrr, 4)

    for k in K_VALUES:
        recalls = [
            float(row[f"recall_at_{k}"])
            for row in per_query
            if isinstance(row.get(f"recall_at_{k}"), (int, float))
        ]
        req_ok = [row for row in per_query if row.get(f"required_tables_ok_at_{k}") is True]
        any_ok = [row for row in per_query if row.get(f"any_required_in_top_{k}") is True]

        agg[f"mean_recall_at_{k}"] = round(sum(recalls) / len(recalls), 4) if recalls else None
        agg[f"required_tables_ok_count_at_{k}"] = len(req_ok)
        agg[f"required_tables_ok_rate_at_{k}"] = round(len(req_ok) / total, 4)
        agg[f"any_required_hit_rate_at_{k}"] = round(len(any_ok) / total, 4)

    return agg


def _render_summary_md(payload: Dict[str, Any]) -> str:
    aggregate = payload.get("aggregate") or {}
    lines = [
        "# Cockpit MCP Table-Retrieval Evaluation",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Run ID: `{payload.get('run_id')}`",
        f"- Mode label: `{payload.get('mode_label')}`",
        f"- MCP URL: `{payload.get('mcp_url')}`",
        "",
        "## Aggregate",
        "",
        f"- Total queries: `{aggregate.get('total_queries')}`",
        f"- Mean Recall@5: `{aggregate.get('mean_recall_at_5')}`",
        f"- Required-tables-ok@5: `{aggregate.get('required_tables_ok_count_at_5')}/{aggregate.get('total_queries')}`",
        f"- Mean Recall@10: `{aggregate.get('mean_recall_at_10')}`",
        f"- Required-tables-ok@10: `{aggregate.get('required_tables_ok_count_at_10')}/{aggregate.get('total_queries')}`",
        f"- MRR: `{aggregate.get('mrr')}`",
        "",
        "| Query | Recall@5 | Required ok@5 | Required tables | Top-10 retrieved | Missing required (top-10) |",
        "|---|---:|---:|---|---|---|",
    ]

    for row in payload.get("per_query", []):
        required = row.get("required_tables") or []
        top10 = (row.get("retrieved_tables_ranked") or [])[:10]
        missing = sorted(set(required).difference(set(top10)))
        lines.append(
            "| {qid} | {recall} | {ok} | {required} | {top10} | {missing} |".format(
                qid=row.get("query_id"),
                recall=(
                    f"{row.get('recall_at_5'):.3f}"
                    if isinstance(row.get("recall_at_5"), (int, float))
                    else "None"
                ),
                ok=row.get("required_tables_ok_at_5"),
                required=", ".join(required),
                top10=", ".join(top10),
                missing=", ".join(missing),
            )
        )
    lines.append("")
    return "\n".join(lines)


def run_eval(
    dataset_path: Path,
    labels_path: Path,
    run_name: str,
    mode_label: str,
    mcp_url: str,
    mcp_api_key: str,
    limit: int,
    expect_health_backend: Optional[str],
    expect_off_control_mode: Optional[str],
    expect_search_source: Optional[str],
    require_aligned_fields: bool,
) -> Path:
    queries_by_id = _load_dataset(dataset_path)
    labels_by_id, labels_meta = _load_labels(labels_path)

    run_id = f"{_timestamp()}_{run_name}"
    run_dir = Path(__file__).resolve().parent / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    with httpx.Client() as client:
        health = _call_health(client, mcp_url, mcp_api_key)
        scout_catalog = (health.get("components") or {}).get("scout_catalog") or {}
        health_backend = str(scout_catalog.get("backend") or "").strip()
        health_off_control_mode = str(scout_catalog.get("off_control_mode") or "").strip()

        if expect_health_backend and health_backend.lower() != expect_health_backend.lower():
            raise RuntimeError(
                f"Health backend mismatch. expected={expect_health_backend}, actual={health_backend}"
            )
        if expect_off_control_mode and health_off_control_mode.lower() != expect_off_control_mode.lower():
            raise RuntimeError(
                "Health off_control_mode mismatch. "
                f"expected={expect_off_control_mode}, actual={health_off_control_mode or '<none>'}"
            )

        per_query: List[Dict[str, Any]] = []
        first_source_seen: Optional[str] = None
        aligned_field_supported = False
        for query_id, label in sorted(labels_by_id.items()):
            query_row = queries_by_id.get(query_id) or {}
            question = str(query_row.get("question") or label.get("question") or "").strip()
            if not question:
                continue

            search = _call_search_tables(client, mcp_url, mcp_api_key, question, limit=limit)
            parsed_source = search.get("source_metadata", {}).get("source")
            if not parsed_source:
                # Fallback parse from raw JSON in response text if source_metadata not available.
                marker = "Full response (JSON):"
                text = search.get("text") or ""
                if marker in text:
                    try:
                        parsed_source = json.loads(text.split(marker, 1)[1].strip()).get("source")
                    except Exception:
                        parsed_source = None
            parsed_source = str(parsed_source or "").strip()
            if first_source_seen is None:
                first_source_seen = parsed_source
            if "ranking_backend" in (search.get("source_metadata") or {}) and "source_details" in (
                search.get("source_metadata") or {}
            ):
                aligned_field_supported = True

            required_tables_raw = [str(x).strip() for x in (label.get("required_tables") or []) if str(x).strip()]
            required_tables = _dedupe_keep_order([_normalize_table_name(x) for x in required_tables_raw])
            metrics = _compute_metrics(required_tables, search["ranked_tables"])

            row = {
                "query_id": query_id,
                "question": question,
                "required_tables_raw": required_tables_raw,
                "required_tables": required_tables,
                **metrics,
                "source_metadata": search.get("source_metadata") or {},
                "search_source": parsed_source,
            }
            per_query.append(row)

        if expect_search_source and (first_source_seen or "").lower() != expect_search_source.lower():
            raise RuntimeError(
                f"search_tables source mismatch. expected={expect_search_source}, actual={first_source_seen or '<none>'}"
            )
        if require_aligned_fields and not aligned_field_supported:
            raise RuntimeError(
                "search_tables response missing aligned fields "
                "(`ranking_backend` + `source_details`). Remote MCP likely not on aligned build."
            )

    aggregate = _aggregate(per_query)
    payload = {
        "generated_at_utc": _utc_now(),
        "run_id": run_id,
        "run_name": run_name,
        "mode_label": mode_label,
        "dataset_path": str(dataset_path),
        "labels_path": str(labels_path),
        "labels_meta": labels_meta,
        "mcp_url": mcp_url,
        "mcp_health_snapshot": health,
        "expected_mode_guard": {
            "expect_health_backend": expect_health_backend,
            "expect_off_control_mode": expect_off_control_mode,
            "expect_search_source": expect_search_source,
            "require_aligned_fields": require_aligned_fields,
        },
        "limit": limit,
        "aggregate": aggregate,
        "per_query": per_query,
    }
    (run_dir / "retrieval_table_eval.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (run_dir / "retrieval_table_eval.md").write_text(_render_summary_md(payload), encoding="utf-8")
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "run_name": run_name,
                "mode_label": mode_label,
                "dataset_path": str(dataset_path),
                "labels_path": str(labels_path),
                "mcp_url": mcp_url,
                "limit": limit,
                "generated_at_utc": payload["generated_at_utc"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Run ID: {run_id}")
    print(f"Output: {run_dir}")
    print(f"Mean Recall@5: {aggregate.get('mean_recall_at_5')}")
    print(
        f"Required tables ok@5: {aggregate.get('required_tables_ok_count_at_5')}/"
        f"{aggregate.get('total_queries')}"
    )
    print(f"MRR: {aggregate.get('mrr')}")
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate cockpit table retrieval via MCP search_tables.")
    parser.add_argument(
        "--dataset",
        default=str(Path(__file__).resolve().parent / "datasets" / "cockpit_partner_queries_v1.jsonl"),
        help="Path to cockpit queries JSONL.",
    )
    parser.add_argument(
        "--table-labels",
        default=str(Path(__file__).resolve().parent / "datasets" / "cockpit_partner_table_labels_v1.json"),
        help="Path to partner table labels JSON.",
    )
    parser.add_argument("--run-name", default="cockpit_partner_mcp_table_retrieval")
    parser.add_argument("--mode-label", default="unknown_mode")
    parser.add_argument("--mcp-url", default="http://localhost:8000")
    parser.add_argument("--mcp-api-key", default="supersecretapikey")
    parser.add_argument("--limit", type=int, default=25, help="search_tables result limit")
    parser.add_argument(
        "--expect-health-backend",
        default=None,
        help="Optional mode guard: expected /health.components.scout_catalog.backend",
    )
    parser.add_argument(
        "--expect-off-control-mode",
        default=None,
        help="Optional mode guard: expected /health.components.scout_catalog.off_control_mode",
    )
    parser.add_argument(
        "--expect-search-source",
        default=None,
        help="Optional mode guard: expected search response source value (e.g., scout_runner_catalog, schema_catalog).",
    )
    parser.add_argument(
        "--require-aligned-fields",
        action="store_true",
        help="Fail if search response does not contain ranking_backend/source_details fields.",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset).resolve()
    labels_path = Path(args.table_labels).resolve()
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")
    if not labels_path.exists():
        raise FileNotFoundError(f"Table labels not found: {labels_path}")

    try:
        run_eval(
            dataset_path=dataset_path,
            labels_path=labels_path,
            run_name=args.run_name,
            mode_label=args.mode_label,
            mcp_url=args.mcp_url,
            mcp_api_key=args.mcp_api_key,
            limit=max(1, min(args.limit, 100)),
            expect_health_backend=args.expect_health_backend,
            expect_off_control_mode=args.expect_off_control_mode,
            expect_search_source=args.expect_search_source,
            require_aligned_fields=bool(args.require_aligned_fields),
        )
    except RateLimitError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
