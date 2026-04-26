#!/usr/bin/env python3
"""
Retrieval-Only Ablation: Isolates Scout Mode's table ranking from LLM confounds.

EXPERIMENT DESIGN
=================
This script bypasses the LLM agent entirely and calls the MCP server's
search_tables endpoint directly. For each query, it:

  1. Extracts search keywords from the query text (simulating what the agent would send)
  2. Calls search_tables with SCOUT_DISABLE=false (Scout ON)
  3. Calls search_tables with SCOUT_DISABLE=true  (Scout OFF — two baselines)
  4. Compares the returned top-k tables against ground-truth required_tables

This removes ALL LLM-related confounds:
  - No stochastic tool-call sequences
  - No variation in search term formulation
  - No SQL generation noise
  - Identical inputs → deterministic comparison

METRICS
=======
  - Recall@k:    |retrieved ∩ required| / |required|
  - Precision@k: |retrieved ∩ required| / |retrieved|
  - MRR:         1/rank of first required table in results (0 if none found)
  - Hit@k:       1 if ANY required table in top-k, else 0

DATASETS
========
  H2a — Northwind (14 tables, N=84, EN + DE):
    eval/datasets/northwind_extended_difficulty_v1.jsonl + .contracts.json

  H2b — Cockpit/Sage (~943 tables, German):
    eval/datasets/cockpit_partner_queries_v1.jsonl
    + cockpit_partner_table_labels_v1.json

USAGE
=====
  # H2a: Northwind retrieval ablation
  python -m eval.run_retrieval_only_ablation \\
      --dataset northwind \\
      --mcp-url http://localhost:8000 \\
      --top-k 5

  # H2b: Production Sage retrieval ablation
  python -m eval.run_retrieval_only_ablation \\
      --dataset cockpit \\
      --mcp-url http://localhost:8000 \\
      --top-k 10

  # With automatic server restart between modes
  python -m eval.run_retrieval_only_ablation \\
      --dataset northwind \\
      --restart-server \\
      --top-k 5

  # Dry run (no MCP calls, just show queries and ground truth)
  python -m eval.run_retrieval_only_ablation --dataset northwind --dry-run

  # Single mode (server already running with correct env vars)
  python -m eval.run_retrieval_only_ablation \\
      --dataset northwind \\
      --modes scout_on \\
      --mcp-url http://localhost:8000

OUTPUT
======
  eval/runs/<timestamp>_retrieval_only_<dataset>/
    ├── config.json              # Full experiment configuration
    ├── results_raw.jsonl        # Per-query, per-mode, per-keyword results
    ├── summary.json             # Aggregated metrics per mode
    ├── comparison_table.md      # Human-readable side-by-side comparison
    └── statistical_tests.json   # Paired sign test for ON vs OFF
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from math import comb
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASETS_DIR = PROJECT_ROOT / "eval" / "datasets"
RUNS_DIR = PROJECT_ROOT / "eval" / "runs"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mode specs — the three experimental conditions
# ---------------------------------------------------------------------------
MODE_SPECS: Dict[str, Dict[str, Optional[str]]] = {
    # Scout whole-system ablation (legacy — kept for backwards compatibility).
    "scout_on": {
        "SCOUT_DISABLE": "false",
        "SCOUT_OFF_CONTROL_MODE": None,
    },
    "scout_off_aligned": {
        "SCOUT_DISABLE": "true",
        "SCOUT_OFF_CONTROL_MODE": "aligned_table_ranker",
    },
    "scout_off_legacy": {
        "SCOUT_DISABLE": "true",
        "SCOUT_OFF_CONTROL_MODE": "legacy_lexical_schema_linking",
    },
    # SDG ablation (matches thesis Table III). Both conditions keep Scout enabled
    # and use the same TableRanker; the only change is whether the LLM-generated
    # table descriptions are injected into the ranker signal and tool response.
    "sdg_off": {
        "SCOUT_DISABLE": "false",
        "SCOUT_OFF_CONTROL_MODE": None,
        "SCOUT_DESCRIPTIONS_ENABLED": "false",
        "SCOUT_DESCRIPTIONS_RANKING": "false",
        "SCOUT_DESCRIPTIONS_CACHE_PATH": None,
    },
    "sdg_on": {
        "SCOUT_DISABLE": "false",
        "SCOUT_OFF_CONTROL_MODE": None,
        # Thesis Table III defines SDG-on as descriptions active in BOTH the
        # ranker signal (SCOUT_DESCRIPTIONS_RANKING) and the tool response
        # (SCOUT_DESCRIPTIONS_ENABLED). The ranking flag defaults to off, so
        # it must be set explicitly here.
        "SCOUT_DESCRIPTIONS_ENABLED": "true",
        "SCOUT_DESCRIPTIONS_RANKING": "true",
        "SCOUT_DESCRIPTIONS_CACHE_PATH": "eval/cache/northwind_descriptions.json",
        "SCOUT_DESCRIPTIONS_DATABASE_TYPE": "northwind",
    },
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class QueryCase:
    """A single evaluation query with ground-truth tables."""
    query_id: str
    question: str
    required_tables: List[str]
    search_keywords: List[str]  # Multiple keyword variants to try
    notes: str = ""


@dataclass
class RetrievalResult:
    """Result of a single search_tables call."""
    query_id: str
    mode: str
    search_query: str
    top_k: int
    retrieved_tables: List[str]
    retrieved_scores: List[float]
    required_tables: List[str]
    recall_at_k: float
    precision_at_k: float
    hit_at_k: float
    mrr: float
    missing_tables: List[str]
    extra_tables: List[str]
    latency_ms: float
    source: str
    keyword_strategy: str = "primary"
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------
_STOP_EN = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must",
    "for", "and", "nor", "but", "or", "yet", "so", "in", "on", "at",
    "to", "from", "by", "with", "about", "between", "through", "during",
    "before", "after", "above", "below", "up", "down", "out", "off",
    "over", "under", "again", "further", "then", "once", "here", "there",
    "when", "where", "why", "how", "all", "both", "each", "few", "more",
    "most", "other", "some", "such", "no", "not", "only", "own", "same",
    "than", "too", "very", "just", "because", "as", "until", "while",
    "of", "if", "what", "which", "who", "whom", "this", "that", "these",
    "those", "am", "it", "its", "my", "your", "his", "her", "our",
    "their", "return", "select", "sum", "count", "avg", "group", "order",
    "sorted", "limit", "distinct", "join", "using", "calculate", "show",
    "list", "find", "get", "exactly", "per", "each", "total", "number",
    "many", "much", "based", "where", "after",
}

_STOP_DE = {
    "wie", "viele", "welche", "welcher", "welchem", "welchen",
    "der", "die", "das", "ein", "eine", "einer", "eines", "einem", "einen",
    "und", "oder", "nicht", "kein", "keine", "keinem",
    "mit", "von", "zu", "den", "dem", "des", "im", "ins", "am",
    "ist", "sind", "war", "waren", "wird", "werden", "wurde", "wurden",
    "hat", "haben", "hatte", "hatten",
    "für", "auf", "aus", "bei", "nach", "über", "unter", "vor",
    "zwischen", "durch", "ohne", "gegen", "um", "bis", "seit",
    "wann", "wo", "wer", "was", "bitte",
    "können", "sollen", "müssen", "darf", "dürfen",
    "muss", "kann", "soll", "gibt", "gab",
    "wir", "uns", "ich", "sie", "ihr", "ihm", "ihn",
    "alle", "jede", "jeden", "jeder", "mehr", "weniger",
    "dieses", "dieser", "diese", "man", "sich",
    "auch", "noch", "schon", "nur", "sehr",
    "heute", "morgen", "gestern",
}


def _extract_keywords_en(question: str, required_tables: List[str]) -> List[str]:
    """
    Extract search keywords from an English Northwind question.

    Returns multiple keyword strategies:
      1. Domain keywords from the question text (what an LLM agent would search)
      2. Table-name-derived terms (best-case search)
      3. Combined query
    """
    keywords = []

    # Strategy 1: Domain concepts from the question (primary — this is what the
    # agent actually does: formulates a search query from the user's question)
    words = re.findall(r'\b[a-zA-Z]+\b', question.lower())
    domain_words = [w for w in words if w not in _STOP_EN and len(w) >= 3]
    seen = set()
    unique = []
    for w in domain_words:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    if unique:
        keywords.append(" ".join(unique[:6]))

    # Strategy 2: Use required table names directly (oracle baseline)
    for table in required_tables:
        keywords.append(table.replace("_", " "))

    return keywords


def _extract_keywords_de(question: str) -> List[str]:
    """
    Extract search keywords from a German cockpit question.

    Returns multiple strategies:
      1. The raw German question (primary — Scout is designed to handle this)
      2. Extracted domain keywords (shorter, more targeted)
    """
    keywords = []

    # Strategy 1: Raw question (Scout's normalizer handles German input)
    keywords.append(question)

    # Strategy 2: Extracted domain terms
    words = re.findall(r'\b[a-zA-ZäöüÄÖÜß]+\b', question.lower())
    domain_words = [w for w in words if w not in _STOP_DE and len(w) >= 3]
    seen = set()
    unique = []
    for w in domain_words:
        if w not in seen:
            seen.add(w)
            unique.append(w)

    if unique:
        keywords.append(" ".join(unique[:5]))

    # Strategy 3: Individual important terms (first 3)
    for term in unique[:3]:
        keywords.append(term)

    return keywords


# ---------------------------------------------------------------------------
# Dataset loaders
# ---------------------------------------------------------------------------
def load_northwind_dataset() -> List[QueryCase]:
    """Load the N=84 Northwind extended-difficulty benchmark with ground-truth tables."""
    queries_path = DATASETS_DIR / "northwind_extended_difficulty_v1.jsonl"
    contracts_path = DATASETS_DIR / "northwind_extended_difficulty_v1.contracts.json"

    if not queries_path.exists():
        raise FileNotFoundError(f"Northwind queries not found: {queries_path}")
    if not contracts_path.exists():
        raise FileNotFoundError(f"Northwind contracts not found: {contracts_path}")

    queries = {}
    with open(queries_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            q = json.loads(line)
            queries[q["id"]] = q

    with open(contracts_path, encoding="utf-8") as f:
        contracts = json.loads(f.read())

    cases = []
    level_counts: Dict[str, int] = defaultdict(int)
    for contract in contracts:
        qid = contract["query_id"]
        q = queries.get(qid, {})
        question = q.get("question", "")
        lang = q.get("language", contract.get("language", "en"))
        category = q.get("category", contract.get("category", "unknown"))
        required = [t.lower() for t in contract["required_tables"]]

        if lang == "de":
            keywords = _extract_keywords_de(question)
        else:
            keywords = _extract_keywords_en(question, required)

        cases.append(QueryCase(
            query_id=qid,
            question=question,
            required_tables=required,
            search_keywords=keywords,
            notes=f"category={category}, language={lang}",
        ))
        level_counts[f"{category}_{lang}"] += 1

    logger.info(f"Loaded {len(cases)} Northwind queries from {queries_path.name}")
    for key in sorted(level_counts):
        logger.info(f"  {key}: {level_counts[key]}")
    return cases


def load_consolidated_dataset() -> List[QueryCase]:
    """Load the consolidated Northwind query set (40 queries, 4 categories)."""
    queries_path = DATASETS_DIR / "northwind_consolidated_v1.jsonl"
    contracts_path = DATASETS_DIR / "northwind_consolidated_v1.contracts.json"

    if not queries_path.exists():
        raise FileNotFoundError(f"Consolidated queries not found: {queries_path}")
    if not contracts_path.exists():
        raise FileNotFoundError(f"Consolidated contracts not found: {contracts_path}")

    queries = {}
    with open(queries_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            q = json.loads(line)
            queries[q["id"]] = q

    with open(contracts_path, encoding="utf-8") as f:
        contracts = json.loads(f.read())

    cases = []
    for contract in contracts:
        qid = contract["query_id"]
        q = queries.get(qid, {})
        question = q.get("question", "")
        lang = q.get("language", contract.get("language", "en"))
        category = q.get("category", contract.get("category", "unknown"))
        required = [t.lower() for t in contract["required_tables"]]

        if lang == "de":
            keywords = _extract_keywords_de(question)
        else:
            keywords = _extract_keywords_en(question, required)

        cases.append(QueryCase(
            query_id=qid,
            question=question,
            required_tables=required,
            search_keywords=keywords,
            notes=f"category={category}, language={lang}",
        ))

    logger.info(f"Loaded {len(cases)} consolidated queries with ground-truth tables")
    return cases


def _load_label_overrides() -> Dict[str, str]:
    """Load partner table label overrides (partner_label → live_catalog_name)."""
    overrides_path = DATASETS_DIR / "cockpit_partner_table_label_overrides_v1.json"
    if not overrides_path.exists():
        return {}
    with open(overrides_path, encoding="utf-8") as f:
        doc = json.loads(f.read())
    mapping = {}
    for entry in doc.get("overrides", []):
        mapping[entry["partner_label"]] = entry["live_catalog_name"]
    if mapping:
        logger.info(f"Loaded {len(mapping)} label overrides from {overrides_path.name}")
    return mapping


def load_cockpit_dataset() -> List[QueryCase]:
    """Load cockpit partner queries with ground-truth table labels."""
    queries_path = DATASETS_DIR / "cockpit_partner_queries_v1.jsonl"
    labels_path = DATASETS_DIR / "cockpit_partner_table_labels_v1.json"

    if not queries_path.exists():
        raise FileNotFoundError(f"Cockpit queries not found: {queries_path}")
    if not labels_path.exists():
        raise FileNotFoundError(f"Cockpit table labels not found: {labels_path}")

    queries = {}
    with open(queries_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            q = json.loads(line)
            queries[q["id"]] = q

    with open(labels_path, encoding="utf-8") as f:
        labels_doc = json.loads(f.read())

    # The labels file has format: { "meta": {...}, "labels": [ { "query_id": ..., "required_tables": [...] }, ...] }
    labels_list = labels_doc.get("labels", [])
    if not isinstance(labels_list, list):
        raise ValueError(f"Expected 'labels' to be a list, got {type(labels_list)}")

    # Apply label overrides (partner typos / naming mismatches → live catalog names)
    overrides = _load_label_overrides()

    cases = []
    for label in labels_list:
        qid = label["query_id"]
        if qid not in queries:
            logger.warning(f"Label {qid} has no matching query, skipping")
            continue

        question = queries[qid]["question"]
        required = label["required_tables"]

        # Apply overrides to required_tables
        if overrides:
            corrected = []
            for table in required:
                if table in overrides:
                    logger.info(f"  [{qid}] Override: {table} → {overrides[table]}")
                    corrected.append(overrides[table])
                else:
                    corrected.append(table)
            required = corrected

        keywords = _extract_keywords_de(question)

        cases.append(QueryCase(
            query_id=qid,
            question=question,
            required_tables=required,
            search_keywords=keywords,
            notes=label.get("notes", queries[qid].get("notes", "")),
        ))

    logger.info(f"Loaded {len(cases)} cockpit queries with ground-truth tables")
    return cases


# ---------------------------------------------------------------------------
# MCP client — calls search_tables directly via stdlib urllib
# ---------------------------------------------------------------------------
def _http_post_json(url: str, payload: dict, api_key: Optional[str] = None, timeout: float = 30.0) -> dict:
    """Send a JSON POST request and return parsed JSON response."""
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    req = Request(url=url, data=data, headers=headers, method="POST")
    with urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return json.loads(body)


def _http_get_json(url: str, api_key: Optional[str] = None, timeout: float = 10.0) -> dict:
    """Send a GET request and return parsed JSON response."""
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    req = Request(url=url, headers=headers, method="GET")
    with urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return json.loads(body)


def call_search_tables(
    mcp_url: str,
    query: str,
    api_key: Optional[str],
    top_k: int = 5,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """
    Call the MCP server's search_tables tool directly via JSON-RPC.

    Returns dict with: ok, tables, scores, source, latency_ms, raw_response.
    """
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "search_tables",
            "arguments": {
                "query": query,
                "page_size": top_k,
            },
        },
        "id": 1,
    }

    url = f"{mcp_url.rstrip('/')}/mcp"
    t0 = time.monotonic()

    try:
        result = _http_post_json(url, payload, api_key, timeout)
        latency_ms = (time.monotonic() - t0) * 1000

        tables, scores, source = _parse_mcp_search_response(result)

        return {
            "ok": True,
            "tables": tables,
            "scores": scores,
            "source": source,
            "latency_ms": latency_ms,
            "raw_response": result,
        }

    except Exception as e:
        latency_ms = (time.monotonic() - t0) * 1000
        return {
            "ok": False,
            "error": str(e),
            "latency_ms": latency_ms,
            "tables": [],
            "scores": [],
            "source": "error",
        }


def _parse_mcp_search_response(result: Dict[str, Any]) -> Tuple[List[str], List[float], str]:
    """
    Parse the MCP JSON-RPC response to extract table names and scores.

    The MCP server returns results in a content[].text field. The format
    depends on the search backend (Scout catalog vs TableRanker vs lexical).
    We try multiple parsing strategies to handle all formats.
    """
    tables: List[str] = []
    scores: List[float] = []
    source = "unknown"

    try:
        raw_result = result.get("result", {})
        # Handle both formats:
        #   {"result": {"content": [...]}}  (standard MCP JSON-RPC)
        #   {"result": [...]}               (direct content list)
        if isinstance(raw_result, list):
            content = raw_result
        else:
            content = raw_result.get("content", [])
        if not content:
            return tables, scores, source

        text = content[0].get("text", "")

        # Strategy 1: Find embedded JSON with structured results
        json_match = re.search(r'\{[\s\S]*"ok"\s*:\s*true[\s\S]*\}', text)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                source = parsed.get("source", "unknown")

                data = parsed.get("data", {})
                results_list = data.get("results", [])
                if not results_list and isinstance(data, list):
                    results_list = data

                for item in results_list:
                    if isinstance(item, dict):
                        name = item.get("full_name") or item.get("name", "")
                        score = item.get("relevance_score") or item.get("score", 0.0)
                        if name:
                            tables.append(name)
                            scores.append(float(score))
            except json.JSONDecodeError:
                pass

        # Strategy 2: Parse numbered list format ("1. table_name ...")
        if not tables:
            for line in text.split("\n"):
                line = line.strip()
                match = re.match(r'\d+\.\s+(\S+)', line)
                if match:
                    tables.append(match.group(1))
                    scores.append(0.0)

        # Strategy 3: Parse as plain JSON array
        if not tables:
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict):
                            name = item.get("table_name") or item.get("name", "")
                            score = float(item.get("score", 0.0))
                            if name:
                                tables.append(name)
                                scores.append(score)
                        elif isinstance(item, str):
                            tables.append(item)
                            scores.append(0.0)
            except (json.JSONDecodeError, ValueError):
                pass

    except Exception as e:
        logger.warning(f"Failed to parse MCP response: {e}")

    return tables, scores, source


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------
def _normalize_table_name(name: str) -> str:
    """Normalize table name: lowercase, strip schema prefix (dbo. etc.)."""
    parts = name.strip().split(".")
    base = parts[-1] if parts else name
    return base.lower().strip()


def compute_metrics(
    retrieved: List[str],
    required: List[str],
    top_k: int,
) -> Dict[str, Any]:
    """
    Compute retrieval metrics.

    Table name matching is case-insensitive and strips schema prefixes.
    """
    retrieved_norm = [_normalize_table_name(t) for t in retrieved[:top_k]]
    required_norm = set(_normalize_table_name(t) for t in required)

    retrieved_set = set(retrieved_norm)
    hits = retrieved_set & required_norm

    recall = len(hits) / len(required_norm) if required_norm else 1.0
    precision = len(hits) / len(retrieved_norm) if retrieved_norm else 0.0
    hit_at_k = 1.0 if hits else 0.0  # Any required table found

    # MRR: reciprocal rank of first required table found
    mrr = 0.0
    for i, t in enumerate(retrieved_norm):
        if t in required_norm:
            mrr = 1.0 / (i + 1)
            break

    missing = [t for t in required if _normalize_table_name(t) not in retrieved_set]
    extra = [t for t in retrieved[:top_k] if _normalize_table_name(t) not in required_norm]

    return {
        "recall_at_k": recall,
        "precision_at_k": precision,
        "hit_at_k": hit_at_k,
        "mrr": mrr,
        "missing_tables": missing,
        "extra_tables": extra,
    }


# ---------------------------------------------------------------------------
# Server management
# ---------------------------------------------------------------------------
def _wait_for_health(mcp_url: str, api_key: Optional[str], timeout_s: int = 60) -> bool:
    """Wait for MCP server health endpoint to respond."""
    deadline = time.time() + timeout_s
    health_url = f"{mcp_url.rstrip('/')}/health"
    while time.time() < deadline:
        try:
            body = _http_get_json(health_url, api_key, timeout=5.0)
            logger.info(f"  Server healthy: {json.dumps(body)[:200]}")
            return True
        except (HTTPError, URLError, OSError, json.JSONDecodeError):
            pass
        time.sleep(1.0)
    return False


def _load_env_file(path: Path) -> Dict[str, str]:
    """Load a .env file into a dict."""
    env = {}
    if not path.exists():
        return env
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip().strip('"').strip("'")
    return env


def restart_server_with_mode(
    mode: str,
    server_start_cmd: str,
    env_file: str,
    mcp_url: str,
    api_key: Optional[str],
    server_proc: Optional[subprocess.Popen],
    startup_wait_s: int = 90,
) -> subprocess.Popen:
    """Stop existing server, set env vars for mode, start new server."""
    if server_proc is not None:
        logger.info(f"  Stopping server (pid={server_proc.pid})...")
        server_proc.terminate()
        try:
            server_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server_proc.kill()
            server_proc.wait(timeout=5)
        time.sleep(2)

    # Build environment
    env = os.environ.copy()
    env.update(_load_env_file(Path(env_file).resolve()))

    spec = MODE_SPECS[mode]
    for k, v in spec.items():
        if v is not None:
            env[k] = v
        elif k in env:
            del env[k]

    logger.info(f"  Starting server for mode={mode}...")
    logger.info(f"    SCOUT_DISABLE={env.get('SCOUT_DISABLE', '(unset)')}")
    logger.info(f"    SCOUT_OFF_CONTROL_MODE={env.get('SCOUT_OFF_CONTROL_MODE', '(unset)')}")

    cmd_parts = server_start_cmd.split()
    # Redirect server stdio to a per-mode file. If we use subprocess.PIPE and
    # never read the pipe, the kernel buffer (~64 KB) fills mid-run and the
    # server blocks on write — queries start timing out after ~200 log lines.
    server_log_path = Path("/tmp") / f"mcp_server_{mode}.log"
    server_log_fh = open(server_log_path, "w")
    proc = subprocess.Popen(
        cmd_parts,
        env=env,
        cwd=str(PROJECT_ROOT),
        stdout=server_log_fh,
        stderr=subprocess.STDOUT,
    )
    logger.info(f"  Server stdio → {server_log_path}")

    logger.info(f"  Waiting up to {startup_wait_s}s for server startup...")
    if not _wait_for_health(mcp_url, api_key, timeout_s=startup_wait_s):
        proc.kill()
        raise RuntimeError(f"Server failed to start for mode={mode}")

    # For scout_on, wait for catalog build
    if mode == "scout_on":
        logger.info("  Waiting for Scout catalog build...")
        cat_deadline = time.time() + 120
        while time.time() < cat_deadline:
            try:
                resp = call_search_tables(mcp_url, "test", api_key, top_k=1)
                if resp["ok"]:
                    logger.info(f"  Scout catalog ready")
                    break
            except Exception:
                pass
            time.sleep(2)

    return proc


# ---------------------------------------------------------------------------
# Main experiment runner
# ---------------------------------------------------------------------------
def run_experiment(
    cases: List[QueryCase],
    mcp_url: str,
    api_key: Optional[str],
    top_k: int,
    modes: List[str],
    restart_server: bool = False,
    server_start_cmd: str = "python -m mcp_server",
    env_file: str = ".env",
    startup_wait_s: int = 90,
) -> List[RetrievalResult]:
    """
    Run the retrieval-only ablation across all modes and queries.

    For each query, tries all keyword strategies and records the result
    for each. The primary strategy (index 0) is used for the main
    comparison; additional strategies are logged for analysis.
    """
    all_results: List[RetrievalResult] = []
    server_proc: Optional[subprocess.Popen] = None

    try:
        for mode in modes:
            logger.info(f"\n{'='*60}")
            logger.info(f"MODE: {mode}")
            logger.info(f"{'='*60}")

            if restart_server:
                server_proc = restart_server_with_mode(
                    mode=mode,
                    server_start_cmd=server_start_cmd,
                    env_file=env_file,
                    mcp_url=mcp_url,
                    api_key=api_key,
                    server_proc=server_proc,
                    startup_wait_s=startup_wait_s,
                )
            else:
                if not _wait_for_health(mcp_url, api_key, timeout_s=10):
                    raise RuntimeError(
                        f"Server not responding. Either start it with mode={mode} "
                        f"env vars, or use --restart-server."
                    )

            for case in cases:
                logger.info(f"\n  [{case.query_id}] {case.question[:80]}")
                logger.info(f"    Required: {case.required_tables}")

                # Try each keyword strategy
                for kw_idx, kw in enumerate(case.search_keywords):
                    strategy = "primary" if kw_idx == 0 else f"alt_{kw_idx}"

                    resp = call_search_tables(
                        mcp_url=mcp_url,
                        query=kw,
                        api_key=api_key,
                        top_k=top_k,
                    )

                    if not resp["ok"]:
                        logger.warning(f"    [{strategy}] ERROR: {resp.get('error', '')[:100]}")
                        all_results.append(RetrievalResult(
                            query_id=case.query_id,
                            mode=mode,
                            search_query=kw,
                            top_k=top_k,
                            retrieved_tables=[],
                            retrieved_scores=[],
                            required_tables=case.required_tables,
                            recall_at_k=0.0,
                            precision_at_k=0.0,
                            hit_at_k=0.0,
                            mrr=0.0,
                            missing_tables=case.required_tables,
                            extra_tables=[],
                            latency_ms=resp["latency_ms"],
                            source="error",
                            keyword_strategy=strategy,
                            error=resp.get("error"),
                        ))
                        continue

                    metrics = compute_metrics(
                        retrieved=resp["tables"],
                        required=case.required_tables,
                        top_k=top_k,
                    )

                    result = RetrievalResult(
                        query_id=case.query_id,
                        mode=mode,
                        search_query=kw,
                        top_k=top_k,
                        retrieved_tables=resp["tables"][:top_k],
                        retrieved_scores=resp["scores"][:top_k],
                        required_tables=case.required_tables,
                        recall_at_k=metrics["recall_at_k"],
                        precision_at_k=metrics["precision_at_k"],
                        hit_at_k=metrics["hit_at_k"],
                        mrr=metrics["mrr"],
                        missing_tables=metrics["missing_tables"],
                        extra_tables=metrics["extra_tables"],
                        latency_ms=resp["latency_ms"],
                        source=resp["source"],
                        keyword_strategy=strategy,
                    )
                    all_results.append(result)

                    status = "PERFECT" if metrics["recall_at_k"] == 1.0 else (
                        "PARTIAL" if metrics["hit_at_k"] == 1.0 else "MISS"
                    )
                    logger.info(
                        f"    [{strategy}] {status}: recall={metrics['recall_at_k']:.2f} "
                        f"prec={metrics['precision_at_k']:.2f} "
                        f"mrr={metrics['mrr']:.2f} "
                        f"query=\"{kw[:50]}\" "
                        f"({resp['latency_ms']:.0f}ms)"
                    )
                    if metrics["missing_tables"]:
                        logger.info(f"      Missing: {metrics['missing_tables']}")

    finally:
        if server_proc is not None:
            logger.info("\nCleaning up server process...")
            server_proc.terminate()
            try:
                server_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server_proc.kill()

    return all_results


# ---------------------------------------------------------------------------
# Aggregation and statistical tests
# ---------------------------------------------------------------------------
def aggregate_results(
    results: List[RetrievalResult],
    strategy_filter: str = "primary",
) -> Dict[str, Dict[str, Any]]:
    """
    Aggregate per-query results into per-mode summaries.

    Only uses results from the specified keyword strategy for the main comparison.
    """
    filtered = [r for r in results if r.keyword_strategy == strategy_filter]
    by_mode: Dict[str, List[RetrievalResult]] = defaultdict(list)
    for r in filtered:
        by_mode[r.mode].append(r)

    summaries = {}
    for mode, mode_results in by_mode.items():
        n = len(mode_results)
        summaries[mode] = {
            "mode": mode,
            "n_queries": n,
            "mean_recall_at_k": sum(r.recall_at_k for r in mode_results) / n if n else 0,
            "mean_precision_at_k": sum(r.precision_at_k for r in mode_results) / n if n else 0,
            "mean_hit_at_k": sum(r.hit_at_k for r in mode_results) / n if n else 0,
            "mean_mrr": sum(r.mrr for r in mode_results) / n if n else 0,
            "perfect_recall_count": sum(1 for r in mode_results if r.recall_at_k == 1.0),
            "zero_recall_count": sum(1 for r in mode_results if r.recall_at_k == 0.0),
            "mean_latency_ms": sum(r.latency_ms for r in mode_results) / n if n else 0,
            "per_query": [{
                "query_id": r.query_id,
                "recall": r.recall_at_k,
                "precision": r.precision_at_k,
                "hit": r.hit_at_k,
                "mrr": r.mrr,
                "found": sorted(set(_normalize_table_name(t) for t in r.retrieved_tables[:r.top_k])
                                & set(_normalize_table_name(t) for t in r.required_tables)),
                "missing": r.missing_tables,
                "retrieved": r.retrieved_tables[:r.top_k],
                "search_query": r.search_query,
                "latency_ms": r.latency_ms,
            } for r in mode_results],
        }

    return summaries


# Level labels for the Northwind extended-difficulty benchmark.
# Maps (category, language) in the dataset to the thesis-side level code.
# `lexical_breakpoint` is the code-side name for "schema-opaque" (kept for
# historical reasons — do not rename dataset files or category values).
_LEVEL_LABELS: List[Tuple[str, str, str]] = [
    ("direct", "en", "L1_EN"),
    ("direct", "de", "L1_DE"),
    ("paraphrase", "en", "L2_EN"),
    ("paraphrase", "de", "L2_DE"),
    ("crosslingual", "de", "L3"),
    ("complex", "de", "L4"),
    ("underspecified", "de", "L5"),
    ("lexical_breakpoint", "de", "L6"),
]
_LEVEL_ORDER = [lbl for _, _, lbl in _LEVEL_LABELS]
_LEVEL_KEY_TO_LABEL = {(cat, lang): lbl for cat, lang, lbl in _LEVEL_LABELS}


def _parse_notes(notes: str) -> Tuple[str, str]:
    """Parse 'category=X, language=Y' notes field into (category, language)."""
    category = "unknown"
    language = "unknown"
    for part in (notes or "").split(","):
        part = part.strip()
        if part.startswith("category="):
            category = part.split("=", 1)[1].strip()
        elif part.startswith("language="):
            language = part.split("=", 1)[1].strip()
    return category, language


def aggregate_results_by_level(
    results: List[RetrievalResult],
    cases: List[QueryCase],
    strategy_filter: str = "primary",
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    Aggregate per-query results into (level, mode) summaries.

    Parses category/language from each case's notes field and maps the pair
    to the thesis-side level label (L1_EN … L6). Returns a nested dict keyed
    by level label, then by mode.
    """
    case_meta: Dict[str, Tuple[str, str]] = {}
    for c in cases:
        case_meta[c.query_id] = _parse_notes(c.notes)

    filtered = [r for r in results if r.keyword_strategy == strategy_filter]

    grouped: Dict[str, Dict[str, List[RetrievalResult]]] = defaultdict(lambda: defaultdict(list))
    for r in filtered:
        cat, lang = case_meta.get(r.query_id, ("unknown", "unknown"))
        label = _LEVEL_KEY_TO_LABEL.get((cat, lang), f"{cat}_{lang}")
        grouped[label][r.mode].append(r)

    def _mode_summary(mode_results: List[RetrievalResult]) -> Dict[str, Any]:
        n = len(mode_results)
        return {
            "n_queries": n,
            "mean_recall_at_k": sum(r.recall_at_k for r in mode_results) / n if n else 0.0,
            "mean_precision_at_k": sum(r.precision_at_k for r in mode_results) / n if n else 0.0,
            "mean_hit_at_k": sum(r.hit_at_k for r in mode_results) / n if n else 0.0,
            "mean_mrr": sum(r.mrr for r in mode_results) / n if n else 0.0,
            "perfect_recall_count": sum(1 for r in mode_results if r.recall_at_k == 1.0),
            "zero_recall_count": sum(1 for r in mode_results if r.recall_at_k == 0.0),
        }

    summaries: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for label, by_mode in grouped.items():
        summaries[label] = {mode: _mode_summary(mr) for mode, mr in by_mode.items()}
    return summaries


def _fmt_pct(value: float) -> str:
    """Swiss-English percentage: 94.17% not 94,17%."""
    return f"{value * 100:.2f}%"


def _fmt_delta_pp(value: float) -> str:
    """Signed percentage-point delta. Uses true minus sign and zero shows as '0.00'."""
    scaled = value * 100
    if abs(scaled) < 0.005:
        return "0.00"
    sign = "+" if scaled > 0 else "\u2212"  # typographic minus
    return f"{sign}{abs(scaled):.2f}"


def _make_cols(top_k: int) -> List[Tuple[str, int, str]]:
    """Column spec (header, width, alignment) parametric on top_k."""
    recall_off = f"Recall@{top_k} (off)"
    recall_on = f"Recall@{top_k} (on)"
    hit_off = f"Hit@{top_k} (off)"
    hit_on = f"Hit@{top_k} (on)"
    return [
        ("Level",       18,                  "left"),
        ("n",            3,                  "right"),
        (recall_off,    max(14, len(recall_off)), "right"),
        (recall_on,     max(13, len(recall_on)),  "right"),
        ("\u0394pp",     7,                  "right"),
        ("MRR (off)",    9,                  "right"),
        ("MRR (on)",     8,                  "right"),
        (hit_off,       max(11, len(hit_off)),    "right"),
        (hit_on,        max(10, len(hit_on)),     "right"),
    ]


def _pad(value: str, width: int, align: str) -> str:
    if align == "left":
        return value.ljust(width)
    return value.rjust(width)


def _row(cells: List[str], cols: List[Tuple[str, int, str]]) -> str:
    padded = [_pad(v, w, a) for v, (_, w, a) in zip(cells, cols)]
    return "| " + " | ".join(padded) + " |"


def _level_row(
    label: str,
    n: int,
    off: Dict[str, Any],
    on: Dict[str, Any],
    cols: List[Tuple[str, int, str]],
) -> str:
    """Render one Markdown row for the per-level comparison table."""
    off_recall = off.get("mean_recall_at_k", 0.0) if off else 0.0
    on_recall = on.get("mean_recall_at_k", 0.0) if on else 0.0
    off_mrr = off.get("mean_mrr", 0.0) if off else 0.0
    on_mrr = on.get("mean_mrr", 0.0) if on else 0.0
    off_hit = off.get("mean_hit_at_k", 0.0) if off else 0.0
    on_hit = on.get("mean_hit_at_k", 0.0) if on else 0.0
    delta = on_recall - off_recall
    return _row([
        label,
        str(n),
        _fmt_pct(off_recall),
        _fmt_pct(on_recall),
        _fmt_delta_pp(delta),
        f"{off_mrr:.3f}",
        f"{on_mrr:.3f}",
        _fmt_pct(off_hit),
        _fmt_pct(on_hit),
    ], cols)


def _aggregate_across_levels(
    level_summaries: Dict[str, Dict[str, Dict[str, Any]]],
    include_labels: List[str],
    mode: str,
) -> Tuple[int, Dict[str, float]]:
    """Sum n_queries and re-mean metrics across a group of levels for one mode."""
    total_n = 0
    acc = {
        "recall": 0.0,
        "mrr": 0.0,
        "hit": 0.0,
    }
    for lbl in include_labels:
        data = level_summaries.get(lbl, {}).get(mode)
        if not data:
            continue
        n = data["n_queries"]
        total_n += n
        acc["recall"] += data["mean_recall_at_k"] * n
        acc["mrr"] += data["mean_mrr"] * n
        acc["hit"] += data["mean_hit_at_k"] * n
    if total_n:
        for k in acc:
            acc[k] /= total_n
    return total_n, acc


def generate_comparison_by_level(
    level_summaries: Dict[str, Dict[str, Dict[str, Any]]],
    available_modes: List[str],
    top_k: int = 5,
) -> str:
    """
    Render a Markdown table matching Table III in 5_results.tex: one row per
    level (L1_EN … L6) plus English / German / Overall summary rows.
    Columns: Level, n, Recall@5 off, Recall@5 on, Δpp, MRR off, MRR on, Hit off, Hit on.
    Prefers the SDG ablation pair (sdg_off / sdg_on); falls back to the Scout
    whole-system pair (scout_off_aligned / scout_on) if SDG modes are not run.
    """
    if "sdg_off" in available_modes and "sdg_on" in available_modes:
        off_mode, on_mode = "sdg_off", "sdg_on"
    else:
        off_mode = "scout_off_aligned" if "scout_off_aligned" in available_modes else None
        on_mode = "scout_on" if "scout_on" in available_modes else None

    cols = _make_cols(top_k)

    # Header + separator with explicit alignment (left for Level, right for numerics).
    header = _row([name for name, _, _ in cols], cols)
    sep_cells = []
    for _, w, a in cols:
        if a == "right":
            sep_cells.append("-" * (w - 1) + ":")
        else:
            sep_cells.append("-" * w)
    sep = "| " + " | ".join(sep_cells) + " |"

    lines = [
        "# Retrieval-Only Ablation — Per-Level Comparison",
        "",
        f"Modes compared: off = `{off_mode or '(missing)'}`, on = `{on_mode or '(missing)'}` (top-k = {top_k})",
        "",
        header,
        sep,
    ]

    for label in _LEVEL_ORDER:
        level_data = level_summaries.get(label, {})
        off = level_data.get(off_mode, {}) if off_mode else {}
        on = level_data.get(on_mode, {}) if on_mode else {}
        n = off.get("n_queries") or on.get("n_queries") or 0
        lines.append(_level_row(label, n, off, on, cols))

    english_labels = ["L1_EN", "L2_EN"]
    german_labels = ["L1_DE", "L2_DE", "L3", "L4", "L5", "L6"]
    overall_labels = _LEVEL_ORDER

    for summary_label, labels in [
        ("English (L1–L2)", english_labels),
        ("German (L1–L6)", german_labels),
        ("**Overall**", overall_labels),
    ]:
        n_off, off_agg = _aggregate_across_levels(level_summaries, labels, off_mode) if off_mode else (0, {"recall": 0, "mrr": 0, "hit": 0})
        n_on, on_agg = _aggregate_across_levels(level_summaries, labels, on_mode) if on_mode else (0, {"recall": 0, "mrr": 0, "hit": 0})
        n = n_off or n_on
        delta = on_agg["recall"] - off_agg["recall"]
        lines.append(_row([
            summary_label,
            str(n),
            _fmt_pct(off_agg["recall"]),
            _fmt_pct(on_agg["recall"]),
            _fmt_delta_pp(delta),
            f"{off_agg['mrr']:.3f}",
            f"{on_agg['mrr']:.3f}",
            _fmt_pct(off_agg["hit"]),
            _fmt_pct(on_agg["hit"]),
        ], cols))

    return "\n".join(lines) + "\n"


def _sign_test(deltas: List[float]) -> Dict[str, Any]:
    """
    Exact binomial sign test for paired differences.

    Tests H0: median difference = 0 against H1: median difference != 0.
    """
    pos = sum(1 for d in deltas if d > 1e-9)
    neg = sum(1 for d in deltas if d < -1e-9)
    zero = sum(1 for d in deltas if abs(d) <= 1e-9)
    n_nonzero = pos + neg

    if n_nonzero == 0:
        p_value = 1.0
    else:
        min_count = min(pos, neg)
        p_value = 0.0
        for i in range(min_count + 1):
            p_value += comb(n_nonzero, i) * (0.5 ** n_nonzero)
        p_value *= 2  # two-sided
        p_value = min(p_value, 1.0)

    return {
        "n_positive": pos,
        "n_negative": neg,
        "n_zero": zero,
        "n_total": len(deltas),
        "mean_delta": sum(deltas) / len(deltas) if deltas else 0,
        "p_value_sign_test": round(p_value, 6),
    }


def compute_paired_tests(
    results: List[RetrievalResult],
    mode_a: str,
    mode_b: str,
    strategy: str = "primary",
) -> Dict[str, Any]:
    """Compute paired sign test comparing mode_a vs mode_b on matching queries."""
    filtered = [r for r in results if r.keyword_strategy == strategy]
    by_q_a: Dict[str, RetrievalResult] = {}
    by_q_b: Dict[str, RetrievalResult] = {}
    for r in filtered:
        if r.mode == mode_a:
            by_q_a[r.query_id] = r
        elif r.mode == mode_b:
            by_q_b[r.query_id] = r

    common = sorted(set(by_q_a) & set(by_q_b))
    if not common:
        return {"error": f"No common queries between {mode_a} and {mode_b}"}

    deltas_recall = [by_q_a[q].recall_at_k - by_q_b[q].recall_at_k for q in common]
    deltas_precision = [by_q_a[q].precision_at_k - by_q_b[q].precision_at_k for q in common]
    deltas_mrr = [by_q_a[q].mrr - by_q_b[q].mrr for q in common]

    per_query = []
    for q in common:
        per_query.append({
            "query_id": q,
            f"{mode_a}_recall": by_q_a[q].recall_at_k,
            f"{mode_b}_recall": by_q_b[q].recall_at_k,
            "delta_recall": by_q_a[q].recall_at_k - by_q_b[q].recall_at_k,
            f"{mode_a}_mrr": by_q_a[q].mrr,
            f"{mode_b}_mrr": by_q_b[q].mrr,
            "delta_mrr": by_q_a[q].mrr - by_q_b[q].mrr,
        })

    return {
        "comparison": f"{mode_a} vs {mode_b}",
        "n_paired_queries": len(common),
        "recall": _sign_test(deltas_recall),
        "precision": _sign_test(deltas_precision),
        "mrr": _sign_test(deltas_mrr),
        "per_query": per_query,
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def generate_comparison_table(
    summaries: Dict[str, Dict],
    top_k: int,
    cases: List[QueryCase],
    results: List[RetrievalResult],
    dataset_type: str,
    stat_tests: Dict[str, Any],
) -> str:
    """Generate a comprehensive markdown comparison report."""
    lines = [
        f"# Retrieval-Only Ablation Results — {dataset_type.upper()}",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
        f"**Top-k:** {top_k}  ",
        f"**Queries:** {len(cases)}  ",
        f"**Dataset:** {dataset_type}  ",
        "",
        "## 1. Aggregate Metrics (Primary Search Strategy)",
        "",
        "| Metric | " + " | ".join(summaries.keys()) + " |",
        "|--------|" + "|".join(["--------"] * len(summaries)) + "|",
    ]

    metrics_rows = [
        ("Mean Recall@k", "mean_recall_at_k", ".3f"),
        ("Mean Precision@k", "mean_precision_at_k", ".3f"),
        ("Mean Hit@k", "mean_hit_at_k", ".3f"),
        ("Mean MRR", "mean_mrr", ".3f"),
        ("Perfect Recall", "perfect_recall_count", None),
        ("Zero Recall", "zero_recall_count", None),
        ("Mean Latency (ms)", "mean_latency_ms", ".0f"),
    ]

    for label, key, fmt in metrics_rows:
        vals = []
        for mode in summaries:
            v = summaries[mode].get(key, 0)
            if fmt and isinstance(v, float):
                vals.append(f"{v:{fmt}}")
            elif key in ("perfect_recall_count", "zero_recall_count"):
                vals.append(f"{v}/{summaries[mode]['n_queries']}")
            else:
                vals.append(str(v))
        lines.append(f"| {label} | " + " | ".join(vals) + " |")

    # Per-query breakdown
    lines.extend([
        "",
        f"## 2. Per-Query Recall@{top_k}",
        "",
    ])

    mode_names = list(summaries.keys())
    lines.append("| Query | Required Tables | " + " | ".join(mode_names) + " |")
    lines.append("|-------|----------------|" + "|".join(["--------"] * len(mode_names)) + "|")

    # Build per-query lookup from primary strategy results
    primary_results = [r for r in results if r.keyword_strategy == "primary"]
    by_query: Dict[str, Dict[str, float]] = {}
    for r in primary_results:
        if r.query_id not in by_query:
            by_query[r.query_id] = {}
        by_query[r.query_id][r.mode] = r.recall_at_k

    for case in cases:
        req = ", ".join(case.required_tables[:3])
        if len(case.required_tables) > 3:
            req += f" (+{len(case.required_tables)-3})"
        vals = []
        for mode in mode_names:
            v = by_query.get(case.query_id, {}).get(mode, None)
            if v is not None:
                emoji = "PERFECT" if v == 1.0 else ("PARTIAL" if v > 0 else "MISS")
                vals.append(f"{v:.2f} ({emoji})")
            else:
                vals.append("--")
        lines.append(f"| {case.query_id} | {req} | " + " | ".join(vals) + " |")

    # Statistical tests
    if stat_tests:
        lines.extend([
            "",
            "## 3. Paired Statistical Tests (Sign Test)",
            "",
        ])
        for label, test in stat_tests.items():
            if "error" in test:
                lines.append(f"**{label}:** {test['error']}")
                continue
            lines.append(f"### {test['comparison']}")
            lines.append(f"N = {test['n_paired_queries']} paired queries")
            lines.append("")
            lines.append("| Metric | Mean Delta | +/-/= | p-value |")
            lines.append("|--------|-----------|-------|---------|")
            for metric in ["recall", "precision", "mrr"]:
                t = test[metric]
                lines.append(
                    f"| {metric} | {t['mean_delta']:+.3f} | "
                    f"+{t['n_positive']}/-{t['n_negative']}/={t['n_zero']} | "
                    f"{t['p_value_sign_test']:.4f} |"
                )
            lines.append("")

    # Keyword strategy analysis
    alt_results = [r for r in results if r.keyword_strategy != "primary"]
    if alt_results:
        lines.extend([
            "",
            "## 4. Keyword Strategy Analysis",
            "",
            "Shows whether alternative search strategies improve recall over the primary strategy.",
            "",
        ])
        by_mode_query: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
        for r in results:
            by_mode_query[r.mode][r.query_id][r.keyword_strategy] = r.recall_at_k

        for mode in mode_names:
            lines.append(f"### {mode}")
            lines.append("")
            lines.append("| Query | Primary | Best Alt | Delta |")
            lines.append("|-------|---------|----------|-------|")
            for case in cases:
                strategies = by_mode_query.get(mode, {}).get(case.query_id, {})
                primary_r = strategies.get("primary", 0)
                alt_recalls = [v for k, v in strategies.items() if k != "primary"]
                best_alt = max(alt_recalls) if alt_recalls else primary_r
                delta = best_alt - primary_r
                lines.append(f"| {case.query_id} | {primary_r:.2f} | {best_alt:.2f} | {delta:+.2f} |")
            lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Retrieval-Only Ablation: Scout ON vs OFF table search without LLM confounds.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dataset", choices=["northwind", "consolidated", "cockpit"], required=True,
        help="Dataset: 'northwind' (N=84 extended-difficulty), 'consolidated' (40 queries, 4 categories), or 'cockpit' (H2b)",
    )
    parser.add_argument("--mcp-url", default="http://localhost:8000", help="MCP server URL")
    parser.add_argument("--api-key", default=None, help="MCP API key (or set MCP_API_KEY)")
    parser.add_argument("--top-k", type=int, default=5, help="Number of tables to retrieve (default: 5)")
    parser.add_argument(
        "--modes", nargs="+",
        default=["scout_on", "scout_off_aligned", "scout_off_legacy"],
        choices=list(MODE_SPECS.keys()),
        help="Modes to test",
    )
    parser.add_argument("--restart-server", action="store_true", help="Auto-restart MCP between modes")
    parser.add_argument("--server-start-cmd", default="python -m mcp_server", help="Server start command")
    parser.add_argument("--env-file", default=".env", help="Path to .env file")
    parser.add_argument("--startup-wait", type=int, default=90, help="Max wait for server startup (s)")
    parser.add_argument("--dry-run", action="store_true", help="Show queries without calling MCP")
    parser.add_argument("--run-tag", default=None, help="Custom tag for output dir")
    parser.add_argument("--output-dir", default=None, help="Override output dir")

    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("MCP_API_KEY")

    # Load dataset
    if args.dataset == "northwind":
        cases = load_northwind_dataset()
    elif args.dataset == "consolidated":
        cases = load_consolidated_dataset()
    else:
        cases = load_cockpit_dataset()

    if not cases:
        logger.error("No query cases loaded. Check dataset files.")
        sys.exit(1)

    logger.info(f"\n{'='*60}")
    logger.info(f"RETRIEVAL-ONLY ABLATION")
    logger.info(f"Dataset: {args.dataset} ({len(cases)} queries)")
    logger.info(f"Top-k: {args.top_k}")
    logger.info(f"Modes: {args.modes}")
    logger.info(f"{'='*60}")

    for case in cases:
        logger.info(f"  {case.query_id}: {len(case.required_tables)} required → {case.required_tables}")
        logger.info(f"    Keywords: {case.search_keywords[:2]}")

    if args.dry_run:
        logger.info("\nDry run complete. No MCP calls made.")
        return

    # Create output directory
    tag = args.run_tag or f"retrieval_only_{args.dataset}"
    if args.output_dir:
        run_dir = Path(args.output_dir).resolve()
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = RUNS_DIR / f"{ts}_{tag}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Save config
    config = {
        "experiment": "retrieval_only_ablation",
        "dataset": args.dataset,
        "n_queries": len(cases),
        "query_ids": [c.query_id for c in cases],
        "top_k": args.top_k,
        "modes": args.modes,
        "restart_server": args.restart_server,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    (run_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    if not args.restart_server and len(args.modes) > 1:
        logger.warning(
            "\n  WARNING: Multiple modes requested but --restart-server not set.\n"
            "  The server must be restarted between modes with different env vars.\n"
            "  Running all queries against the CURRENT server state.\n"
            "  Results will only be valid if you run one mode at a time.\n"
        )

    # Run experiment
    results = run_experiment(
        cases=cases,
        mcp_url=args.mcp_url,
        api_key=api_key,
        top_k=args.top_k,
        modes=args.modes,
        restart_server=args.restart_server,
        server_start_cmd=args.server_start_cmd,
        env_file=args.env_file,
        startup_wait_s=args.startup_wait,
    )

    # Save raw results
    with open(run_dir / "results_raw.jsonl", "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(asdict(r), default=str, ensure_ascii=False) + "\n")

    # Aggregate (primary strategy only)
    summaries = aggregate_results(results, strategy_filter="primary")

    # Per-level aggregation (only meaningful for Northwind extended-difficulty).
    # The notes field is populated for northwind and consolidated loaders.
    level_summaries = aggregate_results_by_level(results, cases, strategy_filter="primary")
    if level_summaries:
        (run_dir / "summary_by_level.json").write_text(
            json.dumps(level_summaries, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )
        by_level_md = generate_comparison_by_level(level_summaries, args.modes, top_k=args.top_k)
        (run_dir / "comparison_by_level.md").write_text(by_level_md, encoding="utf-8")

    # Paired statistical tests. Run for any treatment-baseline pair:
    #   - scout_on vs each other mode (legacy Scout ablation)
    #   - sdg_on vs each other sdg_* mode (SDG ablation)
    stat_tests = {}
    for treatment in ("scout_on", "sdg_on"):
        if treatment not in args.modes:
            continue
        for baseline in args.modes:
            if baseline == treatment:
                continue
            key = f"{treatment}_vs_{baseline}"
            stat_tests[key] = compute_paired_tests(results, treatment, baseline)

    # Save summary
    (run_dir / "summary.json").write_text(
        json.dumps({
            **config,
            "summaries": summaries,
        }, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )

    # Save statistical tests
    (run_dir / "statistical_tests.json").write_text(
        json.dumps(stat_tests, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Generate comparison table
    md = generate_comparison_table(
        summaries=summaries,
        top_k=args.top_k,
        cases=cases,
        results=results,
        dataset_type=args.dataset,
        stat_tests=stat_tests,
    )
    (run_dir / "comparison_table.md").write_text(md, encoding="utf-8")

    # Print summary
    logger.info(f"\n{'='*60}")
    logger.info("RESULTS SUMMARY")
    logger.info(f"{'='*60}")
    for mode, s in summaries.items():
        logger.info(f"\n  {mode} (n={s['n_queries']}):")
        logger.info(f"    Mean Recall@{args.top_k}:    {s['mean_recall_at_k']:.3f}")
        logger.info(f"    Mean Precision@{args.top_k}: {s['mean_precision_at_k']:.3f}")
        logger.info(f"    Mean Hit@{args.top_k}:       {s['mean_hit_at_k']:.3f}")
        logger.info(f"    Mean MRR:              {s['mean_mrr']:.3f}")
        logger.info(f"    Perfect recall:        {s['perfect_recall_count']}/{s['n_queries']}")

    if stat_tests:
        logger.info(f"\n{'='*60}")
        logger.info("STATISTICAL COMPARISONS")
        logger.info(f"{'='*60}")
        for label, test in stat_tests.items():
            if "error" in test:
                logger.info(f"  {label}: {test['error']}")
                continue
            logger.info(f"\n  {test['comparison']} (n={test['n_paired_queries']}):")
            for metric in ["recall", "precision", "mrr"]:
                t = test[metric]
                logger.info(
                    f"    {metric}: delta={t['mean_delta']:+.3f} "
                    f"(+{t['n_positive']}/-{t['n_negative']}/={t['n_zero']}) "
                    f"p={t['p_value_sign_test']:.4f}"
                )

    # Print per-level comparison table to console so it can be pasted directly
    # into the thesis without rooting through the filesystem.
    if level_summaries:
        logger.info(f"\n{'='*60}")
        logger.info("PER-LEVEL COMPARISON (paste-ready for thesis)")
        logger.info(f"{'='*60}")
        print((run_dir / "comparison_by_level.md").read_text(encoding="utf-8"))

    logger.info(f"\nAll outputs saved to: {run_dir}")


if __name__ == "__main__":
    main()
