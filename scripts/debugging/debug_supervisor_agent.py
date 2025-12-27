#!/usr/bin/env python3
"""
🧠 ReAct Supervisor Debug Stream

Real-time monitor for the ReAct-style supervisor loop.

Shows, for each supervisor iteration:
  - step number
  - selected tool (interpret_query / discover_schema / plan_sql / validate_sql / execute_sql / evaluate_result / finalize_answer)
  - thought_summary (short decision)
  - observation_summary (what was observed)
  - progress_signal (positive / neutral / negative)
  - budgets snapshot (steps, llm calls, no-progress counter)

Usage:
    python scripts/debugging/debug_supervisor_agent.py
    # or:
    python scripts/debugging/debug_supervisor_agent.py --url http://localhost:5001 --api-key supersecretapikey
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
import json


class C:
    """Color constants for terminal output."""

    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    PURPLE = "\033[35m"
    WHITE = "\033[97m"
    GREY = "\033[90m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    END = "\033[0m"


def stamp(msg: str, emoji: str = "•", color: str = C.CYAN) -> str:
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    return f"{color}{emoji} [{ts}] {msg}{C.END}"


def format_supervisor_step(data: Dict[str, Any]) -> str:
    """Format a single supervisor_step log entry."""
    step = data.get("step")
    tool = data.get("tool")
    thought = data.get("thought_summary") or ""
    obs = data.get("observation_summary") or ""
    progress = data.get("progress_signal") or "neutral"
    budgets = data.get("budgets") or {}
    suggested = data.get("suggested_next_actions") or []

    header = (
        f"\n{C.BOLD}{C.CYAN}{'═' * 100}{C.END}\n"
        f"{C.BOLD}{C.CYAN}🧠 SUPERVISOR STEP {step} → {tool}{C.END}\n"
        f"{C.BOLD}{C.CYAN}{'═' * 100}{C.END}\n"
    )

    lines: List[str] = [header]

    lines.append(f"{C.GREEN}thought_summary{C.END}: {C.WHITE}{thought}{C.END}")
    lines.append(f"{C.GREEN}observation_summary{C.END}: {C.WHITE}{obs}{C.END}")
    lines.append(f"{C.GREEN}progress_signal{C.END}: {C.YELLOW}{progress}{C.END}")

    if suggested:
        lines.append(
            f"{C.GREEN}suggested_next_actions{C.END}: {C.WHITE}{', '.join(suggested)}{C.END}"
        )

    if budgets:
        bs = []
        for k in [
            "supervisor_step_count",
            "max_supervisor_steps",
            "total_llm_calls",
            "max_llm_calls",
            "no_progress_repeat_count",
        ]:
            if k in budgets:
                bs.append(f"{k}={budgets[k]}")
        if bs:
            lines.append(f"{C.GREEN}budgets{C.END}: {C.WHITE}{', '.join(str(b) for b in bs)}{C.END}")

    return "\n".join(lines)


async def stream_supervisor_steps(
    service_url: str = "http://localhost:5001",
    api_key: str = "supersecretapikey",
) -> None:
    """
    Poll /debug/logs/stream and render SUPERVISOR_STEP events in real time.
    """
    print(
        f"\n{C.BOLD}{C.GREEN}🧠 ReAct Supervisor Debug Stream{C.END}\n"
        f"{C.CYAN}Streaming from: {service_url}/debug/logs/stream{C.END}\n"
    )

    last_sequence_seen: int = 0

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(
                    f"{service_url}/debug/logs/stream",
                    headers={"X-API-Key": api_key},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        print(
                            stamp(
                                f"Server returned status {resp.status} while reading debug logs",
                                "❌",
                                C.RED,
                            )
                        )
                        await asyncio.sleep(2.0)
                        continue

                    payload = await resp.json()
                    logs: List[Dict[str, Any]] = payload.get("logs") or []

                    for entry in logs:
                        seq = int(entry.get("sequence", 0) or 0)
                        if seq <= last_sequence_seen:
                            continue
                        last_sequence_seen = seq

                        log_type = entry.get("type")
                        data = entry.get("data") or {}

                        if log_type == "SUPERVISOR_STEP" and isinstance(data, dict):
                            print(format_supervisor_step(data))

                    await asyncio.sleep(0.5)

            except asyncio.TimeoutError:
                print(stamp("Timeout while reading debug logs; retrying...", "⚠️", C.YELLOW))
                await asyncio.sleep(1.0)
            except aiohttp.ClientConnectorError:
                print(
                    stamp(
                        "Could not connect to LangGraph service. Is it running?",
                        "⚠️",
                        C.YELLOW,
                    )
                )
                await asyncio.sleep(3.0)
            except Exception as exc:  # pragma: no cover - defensive
                print(stamp(f"Unexpected error: {exc}", "❌", C.RED))
                await asyncio.sleep(2.0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Real-time supervisor debug stream for ReAct orchestration"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:5001",
        help="LangGraph service base URL (default: http://localhost:5001)",
    )
    parser.add_argument(
        "--api-key",
        default="supersecretapikey",
        help="API key for the LangGraph service (default: supersecretapikey)",
    )
    args = parser.parse_args()

    try:
        asyncio.run(stream_supervisor_steps(args.url, args.api_key))
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}👋 Stopped supervisor debug stream{C.END}")

