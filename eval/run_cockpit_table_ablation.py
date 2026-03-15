"""
Run cockpit table-correctness ablation across Scout modes.

This pipeline:
1) Starts MCP + agent per mode (optional).
2) Runs /process_query on cockpit partner queries.
3) Evaluates each run against partner-provided required-table labels.
4) Produces ON/OFF comparison artifacts.

It is designed for production-style H2b evidence without requiring reference SQL.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = PROJECT_ROOT / "eval" / "runs"


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
    mode_label: str


def _utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _load_env_file(env_path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _run_cmd(
    cmd: List[str],
    cwd: Path,
    env: Dict[str, str],
    log_path: Optional[Path] = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
    )
    if log_path is not None:
        log_path.write_text(
            f"$ {' '.join(cmd)}\n\n[stdout]\n{result.stdout}\n\n[stderr]\n{result.stderr}\n",
            encoding="utf-8",
        )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
        )
    return result


def _run_streaming(
    cmd: List[str],
    cwd: Path,
    env: Dict[str, str],
    log_path: Path,
    detect_429: bool = True,
) -> str:
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    lines: List[str] = []
    run_id = ""
    with log_path.open("w", encoding="utf-8") as handle:
        if proc.stdout is None:
            raise RuntimeError("Failed to capture command output.")
        for raw_line in proc.stdout:
            line = raw_line.rstrip("\n")
            print(line)
            handle.write(raw_line)
            lines.append(line)
            if line.startswith("Run ID: "):
                run_id = line.replace("Run ID: ", "", 1).strip()
            if detect_429 and ("429" in line or "insufficient_quota" in line):
                proc.terminate()
                raise RuntimeError(f"429 detected during command execution: {' '.join(cmd)}")
    code = proc.wait()
    if code != 0:
        merged = "\n".join(lines[-80:])
        raise RuntimeError(f"Command failed ({code}): {' '.join(cmd)}\nLast output:\n{merged}")
    return run_id


def _kill_existing_services(env: Dict[str, str]) -> None:
    patterns = [
        "mcp_server.server.app",
        "simple_sql_agent.service:app",
        "uvicorn simple_sql_agent.service:app",
        "uvicorn mcp_server.server.app:app",
    ]
    for pattern in patterns:
        subprocess.run(["pkill", "-f", pattern], cwd=str(PROJECT_ROOT), env=env, check=False)


def _start_services(
    env: Dict[str, str],
    log_dir: Path,
    mcp_port: int,
    agent_port: int,
) -> List[subprocess.Popen]:
    processes: List[subprocess.Popen] = []
    mcp_log = (log_dir / "mcp_server.log").open("w", encoding="utf-8")
    agent_log = (log_dir / "agent_service.log").open("w", encoding="utf-8")

    mcp_cmd = [env.get("PYTHON_BIN", "python"), "-m", "mcp_server.server.app"]
    agent_cmd = [
        env.get("PYTHON_BIN", "python"),
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
        env=env,
        stdout=mcp_log,
        stderr=subprocess.STDOUT,
        text=True,
    )
    processes.append(mcp_proc)

    agent_proc = subprocess.Popen(
        agent_cmd,
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=agent_log,
        stderr=subprocess.STDOUT,
        text=True,
    )
    processes.append(agent_proc)
    return processes


def _stop_processes(processes: List[subprocess.Popen]) -> None:
    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
    end = time.time() + 8
    for proc in processes:
        while proc.poll() is None and time.time() < end:
            time.sleep(0.1)
    for proc in processes:
        if proc.poll() is None:
            proc.kill()


def _http_get_json(url: str, api_key: Optional[str]) -> Dict[str, Any]:
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    req = Request(url=url, headers=headers, method="GET")
    with urlopen(req, timeout=6.0) as response:
        body = response.read().decode("utf-8", errors="replace")
        return json.loads(body)


def _wait_for_health(
    mcp_url: str,
    agent_url: str,
    mcp_api_key: Optional[str],
    timeout_s: int = 60,
) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    last_error = ""
    while time.time() < deadline:
        try:
            mcp_health = _http_get_json(f"{mcp_url.rstrip('/')}/health", mcp_api_key)
            agent_health = _http_get_json(f"{agent_url.rstrip('/')}/health", None)
            return {"mcp": mcp_health, "agent": agent_health}
        except (HTTPError, URLError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            time.sleep(1.0)
    raise RuntimeError(f"Health checks did not pass within timeout. Last error: {last_error}")


def _verify_mode_health(mode: str, mcp_health: Dict[str, Any]) -> None:
    spec = MODE_SPECS[mode]
    components = mcp_health.get("components") or {}
    scout = components.get("scout_catalog") or {}
    backend = scout.get("backend")
    off_control_mode = scout.get("off_control_mode")

    expected_backend = spec["expected_backend"]
    expected_off = spec["expected_off_control_mode"]
    if backend != expected_backend:
        raise RuntimeError(
            f"Mode {mode}: unexpected backend. expected={expected_backend}, got={backend}"
        )
    if expected_off is not None and off_control_mode != expected_off:
        raise RuntimeError(
            f"Mode {mode}: unexpected off_control_mode. expected={expected_off}, got={off_control_mode}"
        )


def _find_run_dir_from_id(run_id: str) -> Path:
    candidates = sorted(RUNS_DIR.glob(f"{run_id}*"))
    if not candidates:
        raise FileNotFoundError(f"Could not find run directory for run_id={run_id}")
    return candidates[0]


def _scan_file_for_429(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    lowered = text.lower()
    return (" 429 " in f" {lowered} ") or ("insufficient_quota" in lowered) or ("rate limit" in lowered)


def _scan_run_for_429(run_dir: Path) -> bool:
    for artifact in [
        run_dir / "process_query_results.json",
        run_dir / "run_summary.md",
    ]:
        if _scan_file_for_429(artifact):
            return True
    return False


def _mode_to_mode_label(mode: str) -> str:
    return mode


def main() -> None:
    parser = argparse.ArgumentParser(description="Run cockpit table-correctness ablation.")
    parser.add_argument(
        "--dataset",
        default=str(PROJECT_ROOT / "eval" / "datasets" / "cockpit_partner_queries_v1.jsonl"),
    )
    parser.add_argument(
        "--table-labels",
        default=str(PROJECT_ROOT / "eval" / "datasets" / "cockpit_partner_table_labels_v1.json"),
    )
    parser.add_argument("--target", default="http://localhost:5001")
    parser.add_argument("--mcp-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default="supersecretapikey")
    parser.add_argument("--mcp-api-key", default="supersecretapikey")
    parser.add_argument("--request-timeout", type=float, default=240.0)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--replicates", type=int, default=1)
    parser.add_argument(
        "--modes",
        nargs="+",
        default=["scout_on", "scout_off_aligned", "scout_off_legacy"],
        choices=list(MODE_SPECS.keys()),
    )
    parser.add_argument("--env-file", default=str(PROJECT_ROOT / ".env"))
    parser.add_argument("--python-bin", default="python")
    parser.add_argument("--db-dialect", default=None, help="Override DB_DIALECT if needed.")
    parser.add_argument("--start-services", action="store_true", default=True)
    parser.add_argument("--no-start-services", action="store_true", default=False)
    parser.add_argument("--mcp-port", type=int, default=8000)
    parser.add_argument("--agent-port", type=int, default=5001)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run-tag", default="cockpit_partner_table_ablation")
    args = parser.parse_args()

    dataset_path = Path(args.dataset).resolve()
    labels_path = Path(args.table_labels).resolve()
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")
    if not labels_path.exists():
        raise FileNotFoundError(f"Table labels not found: {labels_path}")

    do_start_services = bool(args.start_services and not args.no_start_services)

    env = os.environ.copy()
    env.update(_load_env_file(Path(args.env_file).resolve()))
    env["PYTHON_BIN"] = args.python_bin
    env["MCP_API_KEY"] = args.mcp_api_key
    env["MCP_SERVER_URL"] = args.mcp_url
    if args.db_dialect:
        env["DB_DIALECT"] = args.db_dialect

    root_dir = RUNS_DIR / f"{_timestamp()}_{args.run_tag}"
    root_dir.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, Any] = {
        "generated_at_utc": _utc_now(),
        "dataset": str(dataset_path),
        "table_labels": str(labels_path),
        "modes": args.modes,
        "replicates": args.replicates,
        "target": args.target,
        "mcp_url": args.mcp_url,
        "start_services": do_start_services,
        "dry_run": args.dry_run,
        "mode_runs": [],
        "comparisons": [],
    }

    if args.dry_run:
        print("Dry-run mode enabled. No services or API calls will be executed.")

    mode_runs: Dict[str, List[ModeRun]] = {mode: [] for mode in args.modes}

    for replicate in range(1, args.replicates + 1):
        for mode in args.modes:
            spec = MODE_SPECS[mode]
            mode_dir = root_dir / f"{mode}_r{replicate}"
            mode_dir.mkdir(parents=True, exist_ok=True)

            mode_env = env.copy()
            mode_env["SCOUT_DISABLE"] = str(spec["SCOUT_DISABLE"])
            if spec["SCOUT_OFF_CONTROL_MODE"] is None:
                mode_env.pop("SCOUT_OFF_CONTROL_MODE", None)
            else:
                mode_env["SCOUT_OFF_CONTROL_MODE"] = str(spec["SCOUT_OFF_CONTROL_MODE"])

            run_name = f"cockpit_partner_v1_process_query_{mode}_r{replicate}"
            mode_label = _mode_to_mode_label(mode)

            if args.dry_run:
                print(f"[dry-run] mode={mode} replicate={replicate} run_name={run_name}")
                continue

            if do_start_services:
                _kill_existing_services(mode_env)
            processes: List[subprocess.Popen] = []
            try:
                if do_start_services:
                    processes = _start_services(
                        env=mode_env,
                        log_dir=mode_dir,
                        mcp_port=args.mcp_port,
                        agent_port=args.agent_port,
                    )

                health = _wait_for_health(args.mcp_url, args.target, args.mcp_api_key, timeout_s=90)
                (mode_dir / "health_snapshot.json").write_text(
                    json.dumps(health, indent=2),
                    encoding="utf-8",
                )
                _verify_mode_health(mode, health.get("mcp") or {})

                run_log = mode_dir / "process_query_run.log"
                run_cmd = [
                    args.python_bin,
                    "-m",
                    "eval.start_northwind_process_query",
                    "--dataset",
                    str(dataset_path),
                    "--run-name",
                    run_name,
                    "--mode-label",
                    mode_label,
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
                ]
                run_id = _run_streaming(run_cmd, PROJECT_ROOT, mode_env, run_log, detect_429=True)
                if not run_id:
                    raise RuntimeError(f"Could not parse run_id for mode={mode} replicate={replicate}")

                run_dir = _find_run_dir_from_id(run_id)
                if _scan_file_for_429(run_log) or _scan_run_for_429(run_dir):
                    raise RuntimeError(f"429 detected in run artifacts for {run_id}")

                eval_log = mode_dir / "table_label_eval.log"
                eval_cmd = [
                    args.python_bin,
                    "-m",
                    "eval.evaluate_process_query_table_labels",
                    "--run-dir",
                    str(run_dir),
                    "--table-labels",
                    str(labels_path),
                ]
                _run_cmd(eval_cmd, PROJECT_ROOT, mode_env, log_path=eval_log, check=True)

                mode_run = ModeRun(
                    mode=mode,
                    replicate=replicate,
                    run_id=run_id,
                    run_dir=run_dir,
                    mode_label=mode_label,
                )
                mode_runs[mode].append(mode_run)
                manifest["mode_runs"].append(
                    {
                        "mode": mode,
                        "replicate": replicate,
                        "run_id": run_id,
                        "run_dir": str(run_dir),
                        "mode_label": mode_label,
                    }
                )
            finally:
                _stop_processes(processes)

    if not args.dry_run:
        compare_pairs = [
            ("scout_on", "scout_off_aligned"),
            ("scout_on", "scout_off_legacy"),
            ("scout_off_aligned", "scout_off_legacy"),
        ]
        for replicate in range(1, args.replicates + 1):
            for left, right in compare_pairs:
                left_runs = [r for r in mode_runs.get(left, []) if r.replicate == replicate]
                right_runs = [r for r in mode_runs.get(right, []) if r.replicate == replicate]
                if not left_runs or not right_runs:
                    continue
                left_run = left_runs[0]
                right_run = right_runs[0]
                comp_log = root_dir / f"compare_{left}_vs_{right}_r{replicate}.log"
                out_name = f"cockpit_partner_v1_table_eval_{left}_vs_{right}_r{replicate}"
                comp_cmd = [
                    args.python_bin,
                    "-m",
                    "eval.compare_process_query_table_label_runs",
                    "--on-run-dir",
                    str(left_run.run_dir),
                    "--off-run-dir",
                    str(right_run.run_dir),
                    "--out-name",
                    out_name,
                ]
                result = _run_cmd(comp_cmd, PROJECT_ROOT, env, log_path=comp_log, check=True)
                match = re.search(r"Comparison saved to:\s*(.*)", result.stdout)
                comparison_dir = match.group(1).strip() if match else None
                manifest["comparisons"].append(
                    {
                        "replicate": replicate,
                        "left_mode": left,
                        "right_mode": right,
                        "comparison_dir": comparison_dir,
                    }
                )

    manifest_path = root_dir / "ablation_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Ablation manifest: {manifest_path}")
    print(f"Root artifact dir: {root_dir}")


if __name__ == "__main__":
    main()
