#!/usr/bin/env python3
"""
Startup script for the MCP server.
"""

import logging
import sys
import os
import signal
import subprocess
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def teardown_existing_server(port: int) -> None:
    logger = logging.getLogger(__name__)
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            check=False
        )
    except FileNotFoundError:
        logger.warning("lsof not available; skipping teardown")
        return
    pids = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    if not pids:
        return
    logger.info("Stopping MCP server processes on port %s", port)
    for pid in list(pids):
        try:
            os.kill(int(pid), signal.SIGTERM)
        except ProcessLookupError:
            pids.discard(pid)
    deadline = time.time() + 5
    remaining = set(pids)
    while remaining and time.time() < deadline:
        time.sleep(0.2)
        still_running = set()
        for pid in remaining:
            try:
                os.kill(int(pid), 0)
                still_running.add(pid)
            except ProcessLookupError:
                continue
        remaining = still_running
    for pid in remaining:
        try:
            os.kill(int(pid), signal.SIGKILL)
        except ProcessLookupError:
            continue
    if remaining:
        logger.warning("Some MCP server processes could not be terminated: %s", ", ".join(remaining))
    time.sleep(0.5)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        import uvicorn

        port = int(os.getenv("MCP_PORT", "8000"))
        teardown_existing_server(port)

        logger = logging.getLogger(__name__)
        logger.info("Starting MCP Database Server on port %s", port)

        uvicorn.run(
            "mcp_server.server:app",
            host="0.0.0.0",
            port=port,
            reload=False,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Server error: {e}")
        sys.exit(1)
