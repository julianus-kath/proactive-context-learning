"""
End-to-end toggle tests for ScoutRunner.

Verifies:
- Default (env unset) → NullDescriptionGenerator, every table gets description=""
- env SCOUT_DESCRIPTIONS_ENABLED=true + injected client → LLM generator is used,
  and descriptions flow through get_catalog()
- Enrichment is cached: the injected generator is called once per table
  across repeated get_catalog() calls
- invalidate_enrichment_cache() forces re-enrichment
- An injected description_generator parameter bypasses env reading entirely
  (makes it easy to run experimental conditions without monkeypatching env)

We avoid a real DB adapter / CatalogStore by stubbing `runner.store.load_catalog`.
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from mcp_server.scout.runner import ScoutRunner


def _make_fake_catalog() -> Dict[str, Any]:
    # Fresh dict every time — CatalogStore.load_catalog returns a new copy in
    # reality; tests mimic that so enrichment doesn't leak across calls.
    return {
        "metadata": {"tables_count": 2},
        "tables": [
            {"full_name": "dbo.Customers", "name": "Customers", "schema": "dbo"},
            {"full_name": "dbo.Orders", "name": "Orders", "schema": "dbo"},
        ],
    }


class _CountingGenerator:
    """Test double that records every call and returns a predictable string."""

    enabled = True

    def __init__(self):
        self.calls: List[str] = []

    def generate(self, table_info: Dict[str, Any]) -> str:
        name = str(table_info.get("full_name"))
        self.calls.append(name)
        return f"description-of-{name}"


@pytest.fixture
def runner_factory(tmp_path, monkeypatch):
    """Build a ScoutRunner without touching a real database or the env."""
    # Ensure env is clean for each test.
    for key in [
        "SCOUT_DESCRIPTIONS_ENABLED",
        "SCOUT_DESCRIPTIONS_MODEL",
        "SCOUT_DESCRIPTIONS_DATABASE_TYPE",
        "SCOUT_DESCRIPTIONS_CACHE_PATH",
    ]:
        monkeypatch.delenv(key, raising=False)

    def _make(description_generator=None, catalog=None):
        runner = ScoutRunner(
            db_adapter=MagicMock(),
            catalog_dir=str(tmp_path / "catalog"),
            description_generator=description_generator,
        )
        # Replace store with a stub that yields our fake catalog.
        catalog_value = catalog if catalog is not None else _make_fake_catalog()
        runner.store = MagicMock()
        runner.store.load_catalog = lambda: {
            "metadata": dict(catalog_value["metadata"]),
            "tables": [dict(t) for t in catalog_value["tables"]],
        }
        return runner

    return _make


# ---------------------------------------------------------------------------
# Toggle OFF (default)
# ---------------------------------------------------------------------------

def test_default_runner_stamps_empty_descriptions(runner_factory):
    runner = runner_factory()  # no generator injected, env unset → Null

    catalog = runner.get_catalog()

    assert catalog is not None
    assert getattr(runner._description_generator, "enabled", False) is False
    for table in catalog["tables"]:
        assert table["description"] == ""


def test_default_runner_with_env_false_also_stamps_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("SCOUT_DESCRIPTIONS_ENABLED", "false")
    runner = ScoutRunner(db_adapter=MagicMock(), catalog_dir=str(tmp_path / "c"))
    runner.store = MagicMock()
    runner.store.load_catalog = lambda: _make_fake_catalog()

    catalog = runner.get_catalog()
    for table in catalog["tables"]:
        assert table["description"] == ""


# ---------------------------------------------------------------------------
# Toggle ON via injected generator (preferred in experimental tests)
# ---------------------------------------------------------------------------

def test_injected_generator_enriches_every_table(runner_factory):
    gen = _CountingGenerator()
    runner = runner_factory(description_generator=gen)

    catalog = runner.get_catalog()

    descriptions = {t["full_name"]: t["description"] for t in catalog["tables"]}
    assert descriptions == {
        "dbo.Customers": "description-of-dbo.Customers",
        "dbo.Orders": "description-of-dbo.Orders",
    }
    assert gen.calls == ["dbo.Customers", "dbo.Orders"]


def test_enrichment_is_cached_across_repeated_calls(runner_factory):
    gen = _CountingGenerator()
    runner = runner_factory(description_generator=gen)

    runner.get_catalog()
    runner.get_catalog()
    runner.get_catalog()

    # Generator invoked exactly once per table, regardless of how many times
    # callers ask for the catalog.
    assert gen.calls == ["dbo.Customers", "dbo.Orders"]


def test_invalidate_cache_forces_reenrichment(runner_factory):
    gen = _CountingGenerator()
    runner = runner_factory(description_generator=gen)

    runner.get_catalog()
    runner.invalidate_enrichment_cache()
    runner.get_catalog()

    # Two calls each since the cache was invalidated between them.
    assert gen.calls == [
        "dbo.Customers",
        "dbo.Orders",
        "dbo.Customers",
        "dbo.Orders",
    ]


# ---------------------------------------------------------------------------
# Toggle ON via environment variable (experimental "run-time" path)
# ---------------------------------------------------------------------------

def test_env_toggle_on_uses_factory_generator(tmp_path, monkeypatch):
    """
    SCOUT_DESCRIPTIONS_ENABLED=true without an injected generator should
    build one from env using the module-level factory. We monkeypatch the
    factory used by runner.py so we don't need an API key.
    """
    gen = _CountingGenerator()

    import mcp_server.scout.runner as runner_mod

    monkeypatch.setenv("SCOUT_DESCRIPTIONS_ENABLED", "true")
    monkeypatch.setattr(
        runner_mod, "build_description_generator_from_env", lambda: gen
    )

    runner = runner_mod.ScoutRunner(
        db_adapter=MagicMock(), catalog_dir=str(tmp_path / "c")
    )
    runner.store = MagicMock()
    runner.store.load_catalog = lambda: _make_fake_catalog()

    catalog = runner.get_catalog()
    assert catalog["tables"][0]["description"] == "description-of-dbo.Customers"
    assert gen.calls == ["dbo.Customers", "dbo.Orders"]


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

def test_missing_catalog_returns_none_and_does_not_crash(runner_factory):
    runner = runner_factory()
    runner.store.load_catalog = lambda: None
    assert runner.get_catalog() is None
