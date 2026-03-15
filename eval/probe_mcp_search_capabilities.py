"""
Probe MCP search_tables capabilities for ablation compatibility checks.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import httpx


def _utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _parse_response_text(text: str) -> Dict[str, Any]:
    marker = "Full response (JSON):"
    if marker in (text or ""):
        try:
            return json.loads(text.split(marker, 1)[1].strip())
        except Exception:
            return {}
    try:
        return json.loads(text or "")
    except Exception:
        return {}


def _extract_text(result_payload: Dict[str, Any]) -> str:
    result = result_payload.get("result")
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict) and item.get("type") == "text":
                return str(item.get("text") or "")
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe MCP search_tables capability surface.")
    parser.add_argument("--mcp-url", default="http://localhost:8000")
    parser.add_argument("--mcp-api-key", default="supersecretapikey")
    parser.add_argument("--query", default="show me revenue by customer country")
    parser.add_argument("--out-name", default="mcp_search_capability_probe")
    args = parser.parse_args()

    with httpx.Client() as client:
        health = client.get(
            f"{args.mcp_url.rstrip('/')}/health",
            headers={"X-API-Key": args.mcp_api_key},
            timeout=30.0,
        )
        health.raise_for_status()
        health_json = health.json()

        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "search_tables",
                "arguments": {"query": args.query, "limit": 10},
            },
            "id": 1,
        }
        resp = client.post(
            f"{args.mcp_url.rstrip('/')}/mcp",
            headers={"X-API-Key": args.mcp_api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=120.0,
        )
        resp.raise_for_status()
        raw = resp.json()
        text = _extract_text(raw)
        parsed = _parse_response_text(text)

    components = health_json.get("components") if isinstance(health_json.get("components"), dict) else {}
    scout_catalog = components.get("scout_catalog") if isinstance(components.get("scout_catalog"), dict) else {}
    source = parsed.get("source")
    has_ranking_backend = "ranking_backend" in parsed
    has_source_details = "source_details" in parsed
    supports_aligned_off_controls = has_ranking_backend and has_source_details
    backend = scout_catalog.get("backend")
    off_control_mode = scout_catalog.get("off_control_mode")

    report = {
        "generated_at_utc": _utc_now(),
        "mcp_url": args.mcp_url,
        "health_status": health_json.get("status"),
        "health_backend": backend,
        "health_off_control_mode": off_control_mode,
        "search_source": source,
        "search_has_ranking_backend_field": has_ranking_backend,
        "search_has_source_details_field": has_source_details,
        "supports_aligned_off_controls": supports_aligned_off_controls,
        "recommendation": (
            "ready_for_on_off_aligned_legacy_ablation"
            if supports_aligned_off_controls
            else "update_remote_mcp_to_aligned_search_tables_implementation"
        ),
        "parsed_search_keys": sorted(parsed.keys()) if isinstance(parsed, dict) else [],
        "search_preview": text[:1200],
    }

    out_dir = Path(__file__).resolve().parent / "runs" / f"{_timestamp()}_{args.out_name}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "probe.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / "probe.md").write_text(
        "\n".join(
            [
                "# MCP Search Capability Probe",
                "",
                f"- Generated: `{report['generated_at_utc']}`",
                f"- MCP URL: `{report['mcp_url']}`",
                f"- Health backend: `{report['health_backend']}`",
                f"- Health off_control_mode: `{report['health_off_control_mode']}`",
                f"- Search source: `{report['search_source']}`",
                f"- Has `ranking_backend`: `{report['search_has_ranking_backend_field']}`",
                f"- Has `source_details`: `{report['search_has_source_details_field']}`",
                f"- Supports aligned OFF controls: `{report['supports_aligned_off_controls']}`",
                f"- Recommendation: `{report['recommendation']}`",
                "",
                "## Parsed search keys",
                "",
                f"`{', '.join(report['parsed_search_keys'])}`",
            ]
        ),
        encoding="utf-8",
    )

    print(f"Output: {out_dir}")
    print(f"Recommendation: {report['recommendation']}")


if __name__ == "__main__":
    main()
