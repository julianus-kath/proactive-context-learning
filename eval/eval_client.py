"""
Evaluation Client
Non-blocking HTTP client for emitting structured evaluation events.
Failures must not break the main request path.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)

EVAL_TRACKING_URL = os.getenv("EVAL_TRACKING_URL", "").strip()
EVAL_ENABLED = os.getenv("EVAL_ENABLED", "1").lower() in ("1", "true", "yes")


class EvalClient:
    def __init__(self, tracking_url: Optional[str] = None):
        self.tracking_url = tracking_url or EVAL_TRACKING_URL
        self.enabled = EVAL_ENABLED and bool(self.tracking_url)

    async def emit_event(
        self,
        run_id: str,
        query_id: str,
        event_type: str,
        stage: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        """Emit a trace event asynchronously (non-blocking)."""
        if not self.enabled:
            return

        event = {
            "run_id": run_id,
            "query_id": query_id,
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "stage": stage,
            "data": data,
            "error": error,
        }

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.post(
                    f"{self.tracking_url}/events",
                    json=event,
                )
                if response.status_code != 200:
                    logger.warning(
                        f"Event emission failed: {response.status_code} - {response.text}"
                    )
        except asyncio.TimeoutError:
            logger.debug("Event emission timed out (non-critical)")
        except Exception as e:
            logger.debug(f"Event emission failed (non-critical): {e}")

    def emit_event_sync(
        self,
        run_id: str,
        query_id: str,
        event_type: str,
        stage: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        """Emit a trace event synchronously."""
        if not self.enabled:
            return

        event = {
            "run_id": run_id,
            "query_id": query_id,
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "stage": stage,
            "data": data,
            "error": error,
        }

        try:
            response = httpx.post(
                f"{self.tracking_url}/events",
                json=event,
                timeout=2.0,
            )
            if response.status_code != 200:
                logger.debug(f"Event emission returned: {response.status_code}")
        except Exception as e:
            logger.debug(f"Event emission failed (non-critical): {e}")

    async def save_query_artifact(
        self,
        run_id: str,
        query_id: str,
        artifact: Dict[str, Any],
    ):
        """Save per-query artifact asynchronously."""
        if not self.enabled:
            return

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{self.tracking_url}/runs/{run_id}/queries/{query_id}",
                    json=artifact,
                )
                if response.status_code != 200:
                    logger.warning(
                        f"Artifact save failed: {response.status_code} - {response.text}"
                    )
        except asyncio.TimeoutError:
            logger.debug("Artifact save timed out (non-critical)")
        except Exception as e:
            logger.debug(f"Artifact save failed (non-critical): {e}")

    def save_query_artifact_sync(
        self,
        run_id: str,
        query_id: str,
        artifact: Dict[str, Any],
    ):
        """Save per-query artifact synchronously."""
        if not self.enabled:
            return

        try:
            response = httpx.post(
                f"{self.tracking_url}/runs/{run_id}/queries/{query_id}",
                json=artifact,
                timeout=5.0,
            )
            if response.status_code != 200:
                logger.debug(f"Artifact save returned: {response.status_code}")
        except Exception as e:
            logger.debug(f"Artifact save failed (non-critical): {e}")


def get_eval_client() -> EvalClient:
    """Get the global evaluation client."""
    global _eval_client
    if _eval_client is None:
        _eval_client = EvalClient()
    return _eval_client


_eval_client: Optional[EvalClient] = None
