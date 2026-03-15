"""
Orchestrate H2b /process_query grounding setup and execution.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = Path(__file__).resolve().parent
RUNS_DIR = EVAL_DIR / "runs"

MODE_SPECS: Dict[str, Dict[str, Optional[str]]] = {
    "scout_on": {
        "SCOUT_DISABLE": "false",
        "SCOUT_OFF_CONTROL_MODE": None,
        "expected_backend": "ScoutRunner",
        "expected_off_control_mode": None,
    },
    "scout_off_aligned": {
        "SCOUT_DISABLE": "true",
        "SCOUT_OFF_CONTROL_MODE": "aligned_table_ranker",
        "expected_backend": "SchemaCatalog",
        "expected_off_control_mode": "aligned_table_ranker",
    },
    "scout_off_legacy": {
        "SCOUT_DISABLE": "true",
        "SCOUT_OFF_CONTROL_MODE": "legacy_lexical_schema_linking",
        "expected_backend": "SchemaCatalog",
        "expected_off_control_mode": "legacy_lexical_schema_linking",
    },
}


@dataclass
class ModeRun:
    mode: str
    replicate: int
    run_id: str
    run_dir: Path


def _utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _load_env_file(env_path: Path) -> Dict[str, str]:
    loaded: Dict[str, str] = {}
    if not env_path.exists():
        return loaded
    for line in env_path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        loaded[key.strip()] = value.strip().strip('"').strip("'")
    return loaded


def _run_cmd(
    cmd: List[str],
    cwd: Path,
    env: Dict[str, str],
    dry_run: bool,
    log_path: Optional[Path] = None,
) -> Tuple[int, str, str]:
    if dry_run:
        print(f"[dry-run] {' '.join(cmd)}")
        return 0, "", ""

    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
    )
    if log_path:
        log_path.write_text(
            f"$ {' '.join(cmd)}\n\n[stdout]\n{proc.stdout}\n\n[stderr]\n{proc.stderr}\n",
            encoding="utf-8",
        )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )
    return proc.returncode, proc.stdout, proc.stderr


def _run_shell_cmd(
    shell_cmd: str,
    cwd: Path,
    env: Dict[str, str],
    dry_run: bool,
    timeout_s: Optional[int] = None,
    log_path: Optional[Path] = None,
) -> Tuple[int, str, str]:
    if dry_run:
        print(f"[dry-run] {shell_cmd}")
        return 0, "", ""

    proc = subprocess.run(
        shell_cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        shell=True,
        timeout=timeout_s,
    )
    if log_path:
        log_path.write_text(
            f"$ {shell_cmd}\n\n[stdout]\n{proc.stdout}\n\n[stderr]\n{proc.stderr}\n",
            encoding="utf-8",
        )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {shell_cmd}\n"
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )
    return proc.returncode, proc.stdout, proc.stderr


def _kill_existing_services(env: Dict[str, str]) -> None:
    patterns = [
        "mcp_server.server.app",
        "simple_sql_agent.service:app",
        "uvicorn simple_sql_agent.service:app",
        "uvicorn mcp_server.server.app:app",
    ]
    for pattern in patterns:
        try:
            subprocess.run(
                ["pkill", "-f", pattern],
                cwd=str(PROJECT_ROOT),
                env=env,
                check=False,
            )
        except FileNotFoundError:
            # Windows environments typically do not provide pkill.
            # In that case we rely on tracked subprocess handles for cleanup.
            break


def _start_local_services(
    env: Dict[str, str],
    mode_log_dir: Path,
    python_bin: str,
    mcp_port: int,
    agent_port: int,
) -> List[Tuple[subprocess.Popen, Any]]:
    handles: List[Tuple[subprocess.Popen, Any]] = []
    mcp_log_handle = (mode_log_dir / "mcp_server.log").open("w", encoding="utf-8")
    agent_log_handle = (mode_log_dir / "agent_service.log").open("w", encoding="utf-8")

    mcp_env = env.copy()
    mcp_env["MCP_PORT"] = str(mcp_port)
    agent_env = env.copy()
    agent_env["PORT"] = str(agent_port)

    mcp_cmd = [python_bin, "-m", "mcp_server.server.app"]
    agent_cmd = [
        python_bin,
        "-m",
        "uvicorn",
        "simple_sql_agent.service:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(agent_port),
    ]

    mcp_proc = subprocess.Popen(
        mcp_cmd,
        cwd=str(PROJECT_ROOT),
        env=mcp_env,
        stdout=mcp_log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    handles.append((mcp_proc, mcp_log_handle))

    agent_proc = subprocess.Popen(
        agent_cmd,
        cwd=str(PROJECT_ROOT),
        env=agent_env,
        stdout=agent_log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    handles.append((agent_proc, agent_log_handle))
    return handles


def _stop_local_services(handles: Sequence[Tuple[subprocess.Popen, Any]]) -> None:
    for proc, _ in handles:
        if proc.poll() is None:
            proc.terminate()
    deadline = time.time() + 10.0
    for proc, _ in handles:
        while proc.poll() is None and time.time() < deadline:
            time.sleep(0.1)
    for proc, _ in handles:
        if proc.poll() is None:
            proc.kill()
    for _, handle in handles:
        try:
            handle.close()
        except Exception:
            pass


def _http_get_json(url: str, api_key: Optional[str], timeout_s: float = 8.0) -> Dict[str, Any]:
    headers: Dict[str, str] = {}
    if api_key:
        headers["X-API-Key"] = api_key
    req = Request(url=url, headers=headers, method="GET")
    with urlopen(req, timeout=timeout_s) as response:
        body = response.read().decode("utf-8", errors="replace")
        return json.loads(body)


def _wait_for_health(
    mcp_url: str,
    agent_url: str,
    mcp_api_key: Optional[str],
    timeout_s: int,
) -> Dict[str, Any]:
    deadline = time.time() + max(1, timeout_s)
    last_error = ""
    while time.time() < deadline:
        try:
            mcp_health = _http_get_json(f"{mcp_url.rstrip('/')}/health", api_key=mcp_api_key, timeout_s=6.0)
            agent_health = _http_get_json(f"{agent_url.rstrip('/')}/health", api_key=None, timeout_s=6.0)
            return {"mcp": mcp_health, "agent": agent_health}
        except (HTTPError, URLError, json.JSONDecodeError, TimeoutError) as exc:
            last_error = str(exc)
            time.sleep(1.0)
    raise RuntimeError(f"Health checks did not pass within {timeout_s}s. Last error: {last_error}")


def _verify_mode_health(mode: str, mcp_health: Dict[str, Any]) -> None:
    spec = MODE_SPECS[mode]
    components = mcp_health.get("components") if isinstance(mcp_health, dict) else {}
    scout = components.get("scout_catalog") if isinstance(components, dict) else {}
    backend = scout.get("backend") if isinstance(scout, dict) else None
    off_control_mode = scout.get("off_control_mode") if isinstance(scout, dict) else None

    expected_backend = spec.get("expected_backend")
    expected_off = spec.get("expected_off_control_mode")
    if expected_backend and backend != expected_backend:
        raise RuntimeError(
            f"Mode {mode}: unexpected backend. expected={expected_backend}, got={backend}"
        )
    if expected_off is not None and off_control_mode != expected_off:
        raise RuntimeError(
            f"Mode {mode}: unexpected off_control_mode. expected={expected_off}, got={off_control_mode}"
        )


def _render_mode_prepare_command(
    template: str,
    mode: str,
    replicate: int,
    target: str,
    mcp_url: str,
) -> str:
    spec = MODE_SPECS[mode]
    values = {
        "mode": mode,
        "replicate": str(replicate),
        "target": target,
        "mcp_url": mcp_url,
        "scout_disable": str(spec.get("SCOUT_DISABLE") or ""),
        "off_control_mode_raw": str(spec.get("SCOUT_OFF_CONTROL_MODE") or ""),
        "off_control_mode": str(spec.get("SCOUT_OFF_CONTROL_MODE") or "none"),
    }
    return template.format(**values)


def _find_run_dir_from_id(run_id: str) -> Path:
    candidates = sorted(RUNS_DIR.glob(f"{run_id}*"))
    if not candidates:
        raise FileNotFoundError(f"Could not find run directory for run_id={run_id}")
    return candidates[0]


def _parse_probe_output(stdout: str) -> Optional[Path]:
    match = re.search(r"Output:\s*(.*)", stdout or "")
    if not match:
        return None
    return Path(match.group(1).strip()).resolve()


def _parse_probe_verdict(probe_dir: Path) -> Dict[str, Any]:
    probe_json = probe_dir / "probe.json"
    if not probe_json.exists():
        raise FileNotFoundError(f"Missing probe.json at {probe_json}")
    payload = json.loads(probe_json.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid probe payload in {probe_json}")
    return payload


def _parse_run_id(stdout: str) -> Optional[str]:
    for line in (stdout or "").splitlines():
        if line.startswith("Run ID: "):
            return line.replace("Run ID: ", "", 1).strip()
    return None


def _comparison_pairs(modes: Sequence[str]) -> List[Tuple[str, str]]:
    pairs = [("scout_on", "scout_off_aligned"), ("scout_on", "scout_off_legacy"), ("scout_off_aligned", "scout_off_legacy")]
    return [pair for pair in pairs if pair[0] in modes and pair[1] in modes]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run setup-first H2b /process_query grounding pipeline.")
    parser.add_argument(
        "--dataset",
        default=str(EVAL_DIR / "datasets" / "cockpit_partner_queries_v1.jsonl"),
    )
    parser.add_argument(
        "--table-labels",
        default=str(EVAL_DIR / "datasets" / "cockpit_partner_table_labels_v1.json"),
    )
    parser.add_argument("--target", default="http://localhost:5001")
    parser.add_argument("--mcp-url", default=os.getenv("MCP_SERVER_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.getenv("API_KEY", "supersecretapikey"))
    parser.add_argument("--mcp-api-key", default=os.getenv("MCP_API_KEY", "supersecretapikey"))
    parser.add_argument("--modes", nargs="+", default=["scout_on", "scout_off_aligned", "scout_off_legacy"], choices=list(MODE_SPECS.keys()))
    parser.add_argument("--replicates", type=int, default=1)
    parser.add_argument("--request-timeout", type=float, default=240.0)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--required-stage-traces", default="discovery,ranked")
    parser.add_argument("--abort-on-missing-stage-trace", action="store_true", default=True)
    parser.add_argument("--no-abort-on-missing-stage-trace", action="store_true", default=False)
    parser.add_argument("--env-file", default=str(PROJECT_ROOT / ".env"))
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--catalog-snapshot", default=None)
    parser.add_argument("--start-services-per-mode", action="store_true", default=False)
    parser.add_argument("--no-start-services-per-mode", action="store_true", default=False)
    parser.add_argument("--mcp-port", type=int, default=8000)
    parser.add_argument("--agent-port", type=int, default=5001)
    parser.add_argument(
        "--mode-prepare-cmd",
        default=None,
        help=(
            "Optional shell command executed before each mode run. "
            "Placeholders: {mode}, {replicate}, {target}, {mcp_url}, "
            "{scout_disable}, {off_control_mode}, {off_control_mode_raw}."
        ),
    )
    parser.add_argument("--mode-prepare-timeout", type=int, default=300)
    parser.add_argument("--health-timeout", type=int, default=90)
    parser.add_argument("--verify-mode-health", action="store_true", default=True)
    parser.add_argument("--no-verify-mode-health", action="store_true", default=False)
    parser.add_argument(
        "--manual-overrides",
        default=str(EVAL_DIR / "datasets" / "cockpit_partner_table_label_overrides_v1.json"),
    )
    parser.add_argument("--setup-only", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--run-tag", default="h2b_process_query_grounding")
    args = parser.parse_args()

    dataset = Path(args.dataset).resolve()
    labels = Path(args.table_labels).resolve()
    if not dataset.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset}")
    if not labels.exists():
        raise FileNotFoundError(f"Table labels not found: {labels}")

    do_abort_on_missing_stage_trace = bool(
        args.abort_on_missing_stage_trace and not args.no_abort_on_missing_stage_trace
    )
    do_start_services_per_mode = bool(
        args.start_services_per_mode and not args.no_start_services_per_mode
    )
    do_verify_mode_health = bool(
        args.verify_mode_health and not args.no_verify_mode_health
    )
    if do_start_services_per_mode and args.mode_prepare_cmd:
        raise ValueError(
            "Use either --start-services-per-mode or --mode-prepare-cmd, not both."
        )

    root_dir = RUNS_DIR / f"{_timestamp()}_{args.run_tag}"
    root_dir.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, Any] = {
        "generated_at_utc": _utc_now(),
        "dataset": str(dataset),
        "table_labels": str(labels),
        "target": args.target,
        "mcp_url": args.mcp_url,
        "modes": args.modes,
        "replicates": args.replicates,
        "required_stage_traces": args.required_stage_traces,
        "abort_on_missing_stage_trace": do_abort_on_missing_stage_trace,
        "start_services_per_mode": do_start_services_per_mode,
        "mode_prepare_cmd": args.mode_prepare_cmd,
        "mode_prepare_timeout_s": args.mode_prepare_timeout,
        "verify_mode_health": do_verify_mode_health,
        "health_timeout_s": args.health_timeout,
        "setup_only": bool(args.setup_only),
        "dry_run": bool(args.dry_run),
        "steps": [],
    }

    env_base = os.environ.copy()
    env_base.update(_load_env_file(Path(args.env_file).resolve()))
    env_base["API_KEY"] = args.api_key
    env_base["MCP_API_KEY"] = args.mcp_api_key
    env_base["MCP_SERVER_URL"] = args.mcp_url

    command_plan: List[List[str]] = []
    command_plan.append(
        [
            args.python_bin,
            "-m",
            "eval.probe_process_query_feasibility",
            "--targets",
            args.target,
            "--api-key",
            args.api_key,
            "--required-stage-traces",
            args.required_stage_traces,
            "--out-name",
            f"{args.run_tag}_probe",
        ]
    )
    normalize_cmd = [
        args.python_bin,
        "-m",
        "eval.normalize_partner_table_labels",
        "--table-labels",
        str(labels),
        "--out-name",
        f"{args.run_tag}_label_normalization",
    ]
    if args.catalog_snapshot:
        normalize_cmd.extend(["--catalog-snapshot", str(Path(args.catalog_snapshot).resolve())])
    else:
        normalize_cmd.extend(["--mcp-url", args.mcp_url, "--mcp-api-key", args.mcp_api_key])
    if args.manual_overrides:
        normalize_cmd.extend(["--manual-overrides", str(Path(args.manual_overrides).resolve())])
    command_plan.append(normalize_cmd)
    for replicate in range(1, args.replicates + 1):
        for mode in args.modes:
            if args.mode_prepare_cmd:
                command_plan.append(
                    [
                        "<mode-prepare-cmd>",
                        _render_mode_prepare_command(
                            template=args.mode_prepare_cmd,
                            mode=mode,
                            replicate=replicate,
                            target=args.target,
                            mcp_url=args.mcp_url,
                        ),
                    ]
                )
            elif do_start_services_per_mode:
                command_plan.append(
                    [
                        "<start-services-per-mode>",
                        f"mode={mode}",
                        f"replicate={replicate}",
                        f"mcp_port={args.mcp_port}",
                        f"agent_port={args.agent_port}",
                    ]
                )
            command_plan.append(
                [
                    "<wait-for-health>",
                    args.mcp_url,
                    args.target,
                    f"timeout={args.health_timeout}",
                ]
            )
            if do_verify_mode_health:
                command_plan.append(
                    [
                        "<verify-mode-health>",
                        f"mode={mode}",
                        f"expected_backend={MODE_SPECS[mode].get('expected_backend')}",
                        f"expected_off_control_mode={MODE_SPECS[mode].get('expected_off_control_mode')}",
                    ]
                )

            run_name = f"h2b_cockpit_process_query_{mode}_r{replicate}"
            run_cmd = [
                args.python_bin,
                "-m",
                "eval.start_northwind_process_query",
                "--dataset",
                str(dataset),
                "--run-name",
                run_name,
                "--mode-label",
                mode,
                "--target",
                args.target,
                "--api-key",
                args.api_key,
                "--mcp-url",
                args.mcp_url,
                "--mcp-api-key",
                args.mcp_api_key,
                "--request-timeout",
                str(args.request_timeout),
                "--concurrency",
                str(args.concurrency),
                "--require-stage-traces",
                args.required_stage_traces,
            ]
            if do_abort_on_missing_stage_trace:
                run_cmd.append("--abort-on-missing-stage-trace")
            command_plan.append(run_cmd)
            command_plan.append(
                [
                    args.python_bin,
                    "-m",
                    "eval.evaluate_process_query_grounding",
                    "--run-dir",
                    "<RUN_DIR_FROM_PREVIOUS_STEP>",
                    "--table-labels",
                    "<NORMALIZED_LABELS_PATH>",
                    "--required-stage-traces",
                    args.required_stage_traces,
                ]
            )

    for left, right in _comparison_pairs(args.modes):
        command_plan.append(
            [
                args.python_bin,
                "-m",
                "eval.compare_process_query_grounding_runs",
                "--left-run-dir",
                f"<RUN_DIR_{left}>",
                "--right-run-dir",
                f"<RUN_DIR_{right}>",
                "--out-name",
                f"h2b_grounding_{left}_vs_{right}",
            ]
        )

    report_plan = [args.python_bin, "-m", "eval.report_h2b_process_query_grounding"]
    for mode in args.modes:
        report_plan.extend(["--mode-run", f"{mode}=<RUN_DIR_{mode}>"])
    report_plan.extend(
        [
            "--label-normalization",
            "<LABEL_NORMALIZATION_JSON>",
            "--out-name",
            f"{args.run_tag}_report",
        ]
    )
    command_plan.append(report_plan)
    manifest["command_plan"] = command_plan

    if args.setup_only or args.dry_run:
        setup_note = {
            "message": (
                "Setup-only/dry-run mode: commands were not executed. "
                "Use command_plan to run when systems are connected."
            ),
            "command_count": len(command_plan),
        }
        manifest["steps"].append({"name": "setup_only", "status": "ready", "details": setup_note})
        (root_dir / "setup_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Setup manifest: {root_dir / 'setup_manifest.json'}")
        for idx, cmd in enumerate(command_plan, start=1):
            print(f"[plan {idx}] {' '.join(cmd)}")
        return

    # Step A: feasibility probe
    probe_log = root_dir / "step_probe.log"
    _, probe_stdout, _ = _run_cmd(command_plan[0], PROJECT_ROOT, env_base, dry_run=False, log_path=probe_log)
    probe_dir = _parse_probe_output(probe_stdout)
    if probe_dir is None:
        raise RuntimeError("Could not parse probe output directory from probe command output.")
    probe_payload = _parse_probe_verdict(probe_dir)
    manifest["steps"].append(
        {
            "name": "probe_process_query_feasibility",
            "status": "completed",
            "probe_dir": str(probe_dir),
            "verdict": probe_payload.get("verdict"),
            "blocked_reasons": probe_payload.get("blocked_reasons"),
        }
    )
    if probe_payload.get("verdict") != "ready_for_h2b_process_query_grounding":
        (root_dir / "setup_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        raise RuntimeError(
            "Feasibility probe did not pass strict requirements. "
            f"See {probe_dir / 'probe.md'} and {probe_dir / 'fallback_technical_note_template.md'}"
        )

    # Step B: label normalization
    norm_log = root_dir / "step_normalize.log"
    _, norm_stdout, _ = _run_cmd(normalize_cmd, PROJECT_ROOT, env_base, dry_run=False, log_path=norm_log)
    norm_out_match = re.search(r"Output:\s*(.*)", norm_stdout)
    if not norm_out_match:
        raise RuntimeError("Could not parse normalization output directory from command output.")
    normalization_dir = Path(norm_out_match.group(1).strip()).resolve()
    normalized_labels_path = normalization_dir / "cockpit_partner_table_labels_v1.normalized.json"
    if not normalized_labels_path.exists():
        raise FileNotFoundError(f"Missing normalized labels artifact: {normalized_labels_path}")
    manifest["steps"].append(
        {
            "name": "normalize_partner_table_labels",
            "status": "completed",
            "normalization_dir": str(normalization_dir),
            "normalized_labels_path": str(normalized_labels_path),
        }
    )

    # Step C + D: run and evaluate each mode
    mode_runs: Dict[str, List[ModeRun]] = {mode: [] for mode in args.modes}
    for replicate in range(1, args.replicates + 1):
        for mode in args.modes:
            mode_env = env_base.copy()
            mode_env["SCOUT_DISABLE"] = str(MODE_SPECS[mode]["SCOUT_DISABLE"])
            if MODE_SPECS[mode]["SCOUT_OFF_CONTROL_MODE"] is None:
                mode_env.pop("SCOUT_OFF_CONTROL_MODE", None)
            else:
                mode_env["SCOUT_OFF_CONTROL_MODE"] = str(MODE_SPECS[mode]["SCOUT_OFF_CONTROL_MODE"])

            mode_local_log_dir = root_dir / f"mode_{mode}_r{replicate}"
            mode_local_log_dir.mkdir(parents=True, exist_ok=True)
            local_handles: List[Tuple[subprocess.Popen, Any]] = []

            try:
                if args.mode_prepare_cmd:
                    mode_prepare = _render_mode_prepare_command(
                        template=args.mode_prepare_cmd,
                        mode=mode,
                        replicate=replicate,
                        target=args.target,
                        mcp_url=args.mcp_url,
                    )
                    prep_log = root_dir / f"step_prepare_{mode}_r{replicate}.log"
                    _run_shell_cmd(
                        shell_cmd=mode_prepare,
                        cwd=PROJECT_ROOT,
                        env=mode_env,
                        dry_run=False,
                        timeout_s=args.mode_prepare_timeout,
                        log_path=prep_log,
                    )
                    manifest["steps"].append(
                        {
                            "name": "prepare_mode",
                            "status": "completed",
                            "mode": mode,
                            "replicate": replicate,
                            "command": mode_prepare,
                            "log": str(prep_log),
                        }
                    )
                elif do_start_services_per_mode:
                    _kill_existing_services(mode_env)
                    local_handles = _start_local_services(
                        env=mode_env,
                        mode_log_dir=mode_local_log_dir,
                        python_bin=args.python_bin,
                        mcp_port=args.mcp_port,
                        agent_port=args.agent_port,
                    )
                    manifest["steps"].append(
                        {
                            "name": "start_services_per_mode",
                            "status": "completed",
                            "mode": mode,
                            "replicate": replicate,
                            "mode_log_dir": str(mode_local_log_dir),
                        }
                    )

                health_snapshot = _wait_for_health(
                    mcp_url=args.mcp_url,
                    agent_url=args.target,
                    mcp_api_key=args.mcp_api_key,
                    timeout_s=args.health_timeout,
                )
                health_path = root_dir / f"health_{mode}_r{replicate}.json"
                health_path.write_text(
                    json.dumps(health_snapshot, indent=2),
                    encoding="utf-8",
                )
                if do_verify_mode_health:
                    _verify_mode_health(mode, health_snapshot.get("mcp") or {})

                manifest["steps"].append(
                    {
                        "name": "mode_health_ready",
                        "status": "completed",
                        "mode": mode,
                        "replicate": replicate,
                        "health_path": str(health_path),
                        "mode_verified": bool(do_verify_mode_health),
                    }
                )

                run_name = f"h2b_cockpit_process_query_{mode}_r{replicate}"
                run_cmd = [
                    args.python_bin,
                    "-m",
                    "eval.start_northwind_process_query",
                    "--dataset",
                    str(dataset),
                    "--run-name",
                    run_name,
                    "--mode-label",
                    mode,
                    "--target",
                    args.target,
                    "--api-key",
                    args.api_key,
                    "--mcp-url",
                    args.mcp_url,
                    "--mcp-api-key",
                    args.mcp_api_key,
                    "--request-timeout",
                    str(args.request_timeout),
                    "--concurrency",
                    str(args.concurrency),
                    "--require-stage-traces",
                    args.required_stage_traces,
                ]
                if do_abort_on_missing_stage_trace:
                    run_cmd.append("--abort-on-missing-stage-trace")

                mode_log = root_dir / f"step_run_{mode}_r{replicate}.log"
                _, run_stdout, _ = _run_cmd(
                    run_cmd,
                    PROJECT_ROOT,
                    mode_env,
                    dry_run=False,
                    log_path=mode_log,
                )
                run_id = _parse_run_id(run_stdout)
                if not run_id:
                    raise RuntimeError(f"Could not parse run_id for mode={mode} replicate={replicate}")
                run_dir = _find_run_dir_from_id(run_id)
                mode_runs[mode].append(
                    ModeRun(mode=mode, replicate=replicate, run_id=run_id, run_dir=run_dir)
                )

                eval_cmd = [
                    args.python_bin,
                    "-m",
                    "eval.evaluate_process_query_grounding",
                    "--run-dir",
                    str(run_dir),
                    "--table-labels",
                    str(normalized_labels_path),
                    "--required-stage-traces",
                    args.required_stage_traces,
                ]
                eval_log = root_dir / f"step_eval_{mode}_r{replicate}.log"
                _run_cmd(eval_cmd, PROJECT_ROOT, mode_env, dry_run=False, log_path=eval_log)

                manifest["steps"].append(
                    {
                        "name": "run_and_eval_mode",
                        "status": "completed",
                        "mode": mode,
                        "replicate": replicate,
                        "run_id": run_id,
                        "run_dir": str(run_dir),
                    }
                )
            finally:
                if do_start_services_per_mode:
                    _stop_local_services(local_handles)

    # Step E1: comparisons
    comparisons: List[Dict[str, Any]] = []
    for replicate in range(1, args.replicates + 1):
        for left, right in _comparison_pairs(args.modes):
            left_runs = [row for row in mode_runs[left] if row.replicate == replicate]
            right_runs = [row for row in mode_runs[right] if row.replicate == replicate]
            if not left_runs or not right_runs:
                continue
            left_run = left_runs[0]
            right_run = right_runs[0]
            out_name = f"h2b_grounding_{left}_vs_{right}_r{replicate}"
            comp_cmd = [
                args.python_bin,
                "-m",
                "eval.compare_process_query_grounding_runs",
                "--left-run-dir",
                str(left_run.run_dir),
                "--right-run-dir",
                str(right_run.run_dir),
                "--out-name",
                out_name,
            ]
            comp_log = root_dir / f"step_compare_{left}_vs_{right}_r{replicate}.log"
            _, comp_stdout, _ = _run_cmd(comp_cmd, PROJECT_ROOT, env_base, dry_run=False, log_path=comp_log)
            comp_match = re.search(r"Output:\s*(.*)", comp_stdout)
            comparisons.append(
                {
                    "left": left,
                    "right": right,
                    "replicate": replicate,
                    "comparison_dir": comp_match.group(1).strip() if comp_match else None,
                }
            )
    manifest["comparisons"] = comparisons

    # Step E2: report
    mode_run_args: List[str] = []
    for mode in args.modes:
        if not mode_runs.get(mode):
            continue
        # Report first replicate per mode by default.
        mode_run_args.extend(["--mode-run", f"{mode}={mode_runs[mode][0].run_dir}"])

    report_cmd = [
        args.python_bin,
        "-m",
        "eval.report_h2b_process_query_grounding",
        *mode_run_args,
        "--label-normalization",
        str(normalization_dir / "label_normalization.json"),
        "--out-name",
        f"{args.run_tag}_report",
    ]
    report_log = root_dir / "step_report.log"
    _, report_stdout, _ = _run_cmd(report_cmd, PROJECT_ROOT, env_base, dry_run=False, log_path=report_log)
    report_match = re.search(r"Output:\s*(.*)", report_stdout)
    manifest["report_dir"] = report_match.group(1).strip() if report_match else None

    (root_dir / "setup_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Setup manifest: {root_dir / 'setup_manifest.json'}")
    print(f"Report dir: {manifest.get('report_dir')}")


if __name__ == "__main__":
    main()
