import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from eval.run_benchmark import (
    load_query_contracts_for_dataset,
    run_benchmark,
)


def _load_dataset_query_ids(dataset_path: Path) -> List[str]:
    ids: List[str] = []
    with open(dataset_path) as f:
        for line in f:
            if line.strip():
                obj = json.loads(line)
                ids.append(obj["id"])
    return ids


def test_contracts_cover_all_queries_in_top5_dataset():
    """Each cockpit_queries_top5.jsonl entry should have a matching contract."""
    dataset = Path("eval/datasets/cockpit_queries_top5.jsonl")
    assert dataset.exists(), f"Dataset not found: {dataset}"

    contracts = load_query_contracts_for_dataset(dataset)
    dataset_ids = set(_load_dataset_query_ids(dataset))

    assert dataset_ids, "Expected non-empty dataset"
    assert set(contracts.keys()) == dataset_ids


@pytest.mark.asyncio
async def test_run_benchmark_sends_query_contract(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """
    Verify that run_benchmark forwards a non-empty query_contract payload
    when running against a dataset with contracts.
    """

    sent_requests: List[Dict[str, Any]] = []

    class DummyResponse:
        status_code = 200

        def json(self) -> Dict[str, Any]:
            # Minimal successful payload; artifact shaping logic is tolerant.
            return {"final_response": "ok"}

    class DummyClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "DummyClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
            return None

        async def post(self, url: str, json: Dict[str, Any] | None = None, headers: Dict[str, Any] | None = None) -> DummyResponse:  # type: ignore[override]
            sent_requests.append({"url": url, "json": json or {}, "headers": headers or {}})
            return DummyResponse()

    # Patch the AsyncClient used inside eval.run_benchmark so no real HTTP is performed.
    monkeypatch.setattr("eval.run_benchmark.httpx.AsyncClient", DummyClient)

    await run_benchmark(
        dataset_path="eval/datasets/cockpit_queries_top5.jsonl",
        run_name="test_run",
        target_url="http://localhost:5001",
        eval_service_url=None,
    )

    # We expect one request per dataset query.
    assert sent_requests, "Expected at least one HTTP request to be issued"

    # All process_query calls should include a non-empty query_contract dict
    # and the appropriate eval headers.
    for req in sent_requests:
        body = req["json"]
        headers = req["headers"]

        # Only inspect process_query calls (ignore any other potential endpoints).
        if not req["url"].endswith("/process_query"):
            continue

        contract = body.get("query_contract")
        assert isinstance(contract, dict) and contract, "query_contract should be a non-empty dict"

        # Eval headers must be present so the orchestrator can correlate contracts.
        assert "X-Eval-Run-Id" in headers
        assert "X-Eval-Query-Id" in headers

