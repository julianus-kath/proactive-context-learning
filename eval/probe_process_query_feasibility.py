"""
Probe /process_query feasibility and trace recoverability for H2b setup.

This probe is setup-oriented and does not execute the full experiment.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import httpx


STAGE_PATHS: Dict[str, Tuple[Tuple[str, ...], ...]] = {
    "discovery": (
        ("discovery_log",),
        ("discovery",),
        ("discovered_tables",),
        ("discovery_tables",),
        ("state", "discovery"),
        ("state", "discovery_log"),
    ),
    "ranked": (
        ("sources",),
        ("relevant_tables",),
        ("ranked_tables",),
        ("selected_tables",),
        ("candidate_tables",),
        ("state", "ranked_tables"),
        ("state", "relevant_tables"),
    ),
    "final_sql": (
        ("sql_query",),
        ("state", "sql_query"),
        ("exec_result", "tables_used"),
        ("exec_result", "tables"),
    ),
}


def _utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _get_nested(data: Dict[str, Any], path: Sequence[str]) -> Tuple[bool, Any]:
    cur: Any = data
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return False, None
        cur = cur.get(key)
    return True, cur


def _auth_variants(api_key: str) -> List[Dict[str, Any]]:
    return [
        {"name": "none", "headers": {}, "include_payload_api_key": False},
        {"name": "payload_api_key", "headers": {}, "include_payload_api_key": True},
        {"name": "x_api_key", "headers": {"X-API-Key": api_key}, "include_payload_api_key": False},
        {
            "name": "bearer",
            "headers": {"Authorization": f"Bearer {api_key}"},
            "include_payload_api_key": False,
        },
    ]


def _attempt_get_health(
    client: httpx.Client,
    endpoint: str,
    auth: Dict[str, Any],
    timeout_s: float,
) -> Dict[str, Any]:
    started = time.perf_counter()
    try:
        resp = client.get(
            f"{endpoint.rstrip('/')}/health",
            headers=auth.get("headers") or {},
            timeout=timeout_s,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        body: Any = None
        try:
            body = resp.json()
        except Exception:
            body = resp.text[:1000]
        return {
            "success": resp.status_code == 200,
            "status_code": resp.status_code,
            "elapsed_ms": elapsed_ms,
            "body_preview": body,
            "error": None,
        }
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "success": False,
            "status_code": None,
            "elapsed_ms": elapsed_ms,
            "body_preview": None,
            "error": str(exc),
        }


def _attempt_process_query(
    client: httpx.Client,
    endpoint: str,
    auth: Dict[str, Any],
    timeout_s: float,
    user_input: str,
    api_key: str,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"user_input": user_input}
    if auth.get("include_payload_api_key"):
        payload["api_key"] = api_key

    started = time.perf_counter()
    try:
        resp = client.post(
            f"{endpoint.rstrip('/')}/process_query",
            json=payload,
            headers=auth.get("headers") or {},
            timeout=timeout_s,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        parsed: Any = None
        try:
            parsed = resp.json()
        except Exception:
            parsed = {"raw_text": resp.text[:1500]}
        return {
            "success": resp.status_code == 200,
            "status_code": resp.status_code,
            "elapsed_ms": elapsed_ms,
            "response": parsed,
            "error": None,
        }
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "success": False,
            "status_code": None,
            "elapsed_ms": elapsed_ms,
            "response": None,
            "error": str(exc),
        }


def _inspect_trace_capability(payload: Dict[str, Any]) -> Dict[str, Any]:
    observed_paths: Dict[str, List[str]] = {stage: [] for stage in STAGE_PATHS}
    stage_presence: Dict[str, bool] = {stage: False for stage in STAGE_PATHS}

    for stage, paths in STAGE_PATHS.items():
        for path in paths:
            exists, value = _get_nested(payload, path)
            if not exists:
                continue
            stage_presence[stage] = True
            observed_paths[stage].append(".".join(path))
            if stage == "final_sql" and path == ("sql_query",) and isinstance(value, str):
                # Keep final_sql true even if empty string key exists.
                stage_presence[stage] = True

    return {
        "raw_response_keys": sorted(payload.keys()),
        "trace_stage_presence": stage_presence,
        "observed_paths": observed_paths,
    }


def _is_successful_attempt(attempt: Dict[str, Any]) -> bool:
    return bool(attempt.get("success")) and isinstance(attempt.get("response"), dict)


def _render_probe_md(report: Dict[str, Any]) -> str:
    lines = [
        "# /process_query Feasibility Probe",
        "",
        f"- Generated: `{report.get('generated_at_utc')}`",
        f"- Verdict: `{report.get('verdict')}`",
        f"- Strict required stages: `{', '.join(report.get('required_stage_traces') or [])}`",
        "",
        "## Endpoints",
        "",
    ]
    for endpoint_row in report.get("endpoints", []):
        lines.append(f"### {endpoint_row.get('endpoint')}")
        lines.append("")
        health_ok = endpoint_row.get("health_success_count", 0)
        process_ok = endpoint_row.get("process_query_success_count", 0)
        lines.append(f"- `/health` successes: `{health_ok}`")
        lines.append(f"- `/process_query` successes: `{process_ok}`")
        if endpoint_row.get("trace_stage_presence") is not None:
            lines.append(
                "- Trace stage presence: `{}`".format(
                    endpoint_row.get("trace_stage_presence")
                )
            )
        lines.append("")

    lines.extend(
        [
            "## Verdict Reasons",
            "",
        ]
    )
    for reason in report.get("blocked_reasons", []):
        lines.append(f"- {reason}")
    if not report.get("blocked_reasons"):
        lines.append("- None")

    lines.append("")
    lines.append("## Recommendation")
    lines.append("")
    if report.get("verdict") == "ready_for_h2b_process_query_grounding":
        lines.append("- Proceed with strict H2b grounding evaluation.")
    else:
        lines.append("- Do not run H2b primary scoring yet; use generated fallback technical note template.")
    lines.append("")
    return "\n".join(lines)


def _render_fallback_note_template(report: Dict[str, Any]) -> str:
    lines = [
        "# H2b Fallback Technical Note (Template)",
        "",
        f"- Generated: `{report.get('generated_at_utc')}`",
        f"- Probe verdict: `{report.get('verdict')}`",
        "",
        "## Claim",
        "",
        "The intended H2b protocol requires full `/process_query` pipeline runs with recoverable",
        "discovery/ranked stage traces. This was not technically feasible at probe time.",
        "",
        "## Probe Evidence",
        "",
    ]
    for endpoint_row in report.get("endpoints", []):
        lines.append(f"### Endpoint `{endpoint_row.get('endpoint')}`")
        lines.append("")
        lines.append(f"- `/health` success count: `{endpoint_row.get('health_success_count')}`")
        lines.append(f"- `/process_query` success count: `{endpoint_row.get('process_query_success_count')}`")
        trace_presence = endpoint_row.get("trace_stage_presence")
        if trace_presence is not None:
            lines.append(f"- Trace stage presence: `{trace_presence}`")
        lines.append("")
    lines.extend(
        [
            "## Blocking Reasons",
            "",
        ]
    )
    for reason in report.get("blocked_reasons", []):
        lines.append(f"- {reason}")
    lines.extend(
        [
            "",
            "## Fallback Scope (if approved)",
            "",
            "Only use retrieval-only fallback as explicitly documented and mark it as non-equivalent to",
            "full `/process_query` grounding evaluation. Keep this note with thesis artifacts.",
            "",
        ]
    )
    return "\n".join(lines)


def run_probe(
    endpoints: Sequence[str],
    api_key: str,
    short_timeout_s: float,
    medium_timeout_s: float,
    required_stage_traces: Sequence[str],
    sample_query: str,
    out_name: str,
) -> Path:
    out_dir = Path(__file__).resolve().parent / "runs" / f"{_timestamp()}_{out_name}"
    out_dir.mkdir(parents=True, exist_ok=True)

    report: Dict[str, Any] = {
        "generated_at_utc": _utc_now(),
        "required_stage_traces": list(required_stage_traces),
        "short_timeout_s": short_timeout_s,
        "medium_timeout_s": medium_timeout_s,
        "sample_query": sample_query,
        "endpoints": [],
        "verdict": "blocked",
        "blocked_reasons": [],
    }

    auths = _auth_variants(api_key)

    with httpx.Client() as client:
        for endpoint in endpoints:
            endpoint_result: Dict[str, Any] = {
                "endpoint": endpoint,
                "health_attempts": [],
                "process_query_attempts": [],
                "health_success_count": 0,
                "process_query_success_count": 0,
                "trace_stage_presence": None,
                "trace_observed_paths": None,
                "raw_response_keys": None,
            }

            for auth in auths:
                h_attempt = _attempt_get_health(client, endpoint, auth, timeout_s=short_timeout_s)
                h_attempt["auth_variant"] = auth["name"]
                endpoint_result["health_attempts"].append(h_attempt)
                if h_attempt.get("success"):
                    endpoint_result["health_success_count"] += 1

            successful_payload: Optional[Dict[str, Any]] = None
            for auth in auths:
                for timeout_s in (short_timeout_s, medium_timeout_s):
                    p_attempt = _attempt_process_query(
                        client=client,
                        endpoint=endpoint,
                        auth=auth,
                        timeout_s=timeout_s,
                        user_input=sample_query,
                        api_key=api_key,
                    )
                    p_attempt["auth_variant"] = auth["name"]
                    p_attempt["timeout_s"] = timeout_s
                    endpoint_result["process_query_attempts"].append(p_attempt)
                    if _is_successful_attempt(p_attempt):
                        endpoint_result["process_query_success_count"] += 1
                        if successful_payload is None:
                            successful_payload = p_attempt["response"]
                    if p_attempt.get("success"):
                        break

            if successful_payload:
                trace = _inspect_trace_capability(successful_payload)
                endpoint_result["trace_stage_presence"] = trace["trace_stage_presence"]
                endpoint_result["trace_observed_paths"] = trace["observed_paths"]
                endpoint_result["raw_response_keys"] = trace["raw_response_keys"]

            report["endpoints"].append(endpoint_result)

    any_process_success = any(row.get("process_query_success_count", 0) > 0 for row in report["endpoints"])
    if not any_process_success:
        report["blocked_reasons"].append("No reachable `/process_query` endpoint with successful response.")

    best_trace_presence: Dict[str, bool] = {stage: False for stage in STAGE_PATHS}
    for row in report["endpoints"]:
        stage_presence = row.get("trace_stage_presence")
        if not isinstance(stage_presence, dict):
            continue
        for stage, present in stage_presence.items():
            if bool(present):
                best_trace_presence[stage] = True

    missing_required = [
        stage for stage in required_stage_traces if not bool(best_trace_presence.get(stage))
    ]
    if any_process_success and missing_required:
        report["blocked_reasons"].append(
            "Required trace stages missing from sampled `/process_query` responses: "
            + ", ".join(missing_required)
        )

    report["best_trace_stage_presence"] = best_trace_presence
    report["missing_required_stages"] = missing_required
    report["verdict"] = (
        "ready_for_h2b_process_query_grounding"
        if not report["blocked_reasons"]
        else "blocked"
    )

    (out_dir / "probe.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / "probe.md").write_text(_render_probe_md(report), encoding="utf-8")
    if report["verdict"] == "blocked":
        (out_dir / "fallback_technical_note_template.md").write_text(
            _render_fallback_note_template(report),
            encoding="utf-8",
        )

    print(f"Output: {out_dir}")
    print(f"Verdict: {report['verdict']}")
    if report["blocked_reasons"]:
        print("Blocking reasons:")
        for reason in report["blocked_reasons"]:
            print(f"- {reason}")
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe /process_query feasibility for H2b setup.")
    parser.add_argument(
        "--targets",
        default="http://localhost:5001",
        help="Comma-separated list of agent base URLs to probe.",
    )
    parser.add_argument("--api-key", default="supersecretapikey")
    parser.add_argument("--short-timeout", type=float, default=5.0)
    parser.add_argument("--medium-timeout", type=float, default=20.0)
    parser.add_argument("--required-stage-traces", default="discovery,ranked")
    parser.add_argument(
        "--sample-query",
        default="H2b feasibility ping: list one table relevant to this request.",
    )
    parser.add_argument("--out-name", default="process_query_feasibility_probe")
    args = parser.parse_args()

    targets = [target.strip() for target in args.targets.split(",") if target.strip()]
    required_stage_traces = [
        stage.strip().lower()
        for stage in args.required_stage_traces.split(",")
        if stage.strip()
    ]

    run_probe(
        endpoints=targets,
        api_key=args.api_key,
        short_timeout_s=args.short_timeout,
        medium_timeout_s=args.medium_timeout,
        required_stage_traces=required_stage_traces,
        sample_query=args.sample_query,
        out_name=args.out_name,
    )


if __name__ == "__main__":
    main()
