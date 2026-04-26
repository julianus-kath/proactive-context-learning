"""Tests for load_contracts() — the H2a ground-truth loader.

Replaces the earlier test_contracts.py, which exercised the deprecated
Pydantic classes in eval/contracts.py (unused by any active code path).

What's tested here is what H2a actually runs: plain JSON load of
*.contracts.json plus optional partner-label overrides (Cockpit).
"""
import json

import pytest

from eval.run_h2a_full_pipeline import load_contracts


# ---------------------------------------------------------------------------
# Fixtures — tiny JSON files written per test
# ---------------------------------------------------------------------------

@pytest.fixture
def write_json(tmp_path):
    def _write(name: str, payload) -> str:
        p = tmp_path / name
        p.write_text(json.dumps(payload))
        return str(p)
    return _write


# ---------------------------------------------------------------------------
# Format 1: list of {query_id, required_tables}
# ---------------------------------------------------------------------------

def test_list_format(write_json):
    path = write_json("c.json", [
        {"query_id": "NW1", "required_tables": ["products"]},
        {"query_id": "NW2", "required_tables": ["customers", "orders"]},
    ])
    out = load_contracts(path)
    assert out == {"NW1": ["products"], "NW2": ["customers", "orders"]}


# ---------------------------------------------------------------------------
# Format 2: {"labels": [...]}  — Cockpit partner-table labels shape
# ---------------------------------------------------------------------------

def test_labels_wrapped_format(write_json):
    path = write_json("c.json", {
        "labels": [
            {"query_id": "CP1", "required_tables": ["KHKAdressen"]},
            {"query_id": "CP2", "required_tables": ["BSBelege", "BSEinstellungen"]},
        ]
    })
    out = load_contracts(path)
    assert out == {
        "CP1": ["KHKAdressen"],
        "CP2": ["BSBelege", "BSEinstellungen"],
    }


# ---------------------------------------------------------------------------
# Format 3: bare map {query_id: [tables]}
# ---------------------------------------------------------------------------

def test_bare_map_format(write_json):
    path = write_json("c.json", {"Q1": ["a", "b"], "Q2": ["c"]})
    out = load_contracts(path)
    assert out == {"Q1": ["a", "b"], "Q2": ["c"]}


def test_bare_map_returns_fresh_dict(write_json):
    """Load must not return a reference into the parsed JSON — callers mutate."""
    path = write_json("c.json", {"Q1": ["a"]})
    out = load_contracts(path)
    out["Q1"].append("injected")
    # Re-loading must not see the injection.
    assert load_contracts(path) == {"Q1": ["a"]}


# ---------------------------------------------------------------------------
# Label overrides — used for Cockpit (partner_label → live_catalog_name)
# ---------------------------------------------------------------------------

def test_overrides_rename_required_tables(write_json):
    contracts = write_json("c.json", [
        {"query_id": "CP1", "required_tables": ["PartnerLabelA", "SharedTable"]},
    ])
    overrides = write_json("ov.json", {
        "overrides": [
            {"partner_label": "PartnerLabelA", "live_catalog_name": "LiveTableA"},
        ]
    })
    out = load_contracts(contracts, overrides)
    assert out == {"CP1": ["LiveTableA", "SharedTable"]}


def test_overrides_leave_unmatched_tables_untouched(write_json):
    contracts = write_json("c.json", [
        {"query_id": "CP1", "required_tables": ["X", "Y"]},
    ])
    overrides = write_json("ov.json", {
        "overrides": [
            {"partner_label": "Z", "live_catalog_name": "Zprime"},
        ]
    })
    out = load_contracts(contracts, overrides)
    assert out == {"CP1": ["X", "Y"]}


def test_overrides_path_missing_is_silent(write_json, tmp_path):
    """If the overrides path is set but the file doesn't exist, the loader
    silently proceeds — matches the original inline behaviour."""
    contracts = write_json("c.json", [
        {"query_id": "CP1", "required_tables": ["X"]},
    ])
    nonexistent = str(tmp_path / "missing.json")
    out = load_contracts(contracts, nonexistent)
    assert out == {"CP1": ["X"]}


def test_empty_overrides_entries_noop(write_json):
    contracts = write_json("c.json", [
        {"query_id": "CP1", "required_tables": ["X"]},
    ])
    overrides = write_json("ov.json", {"overrides": []})
    out = load_contracts(contracts, overrides)
    assert out == {"CP1": ["X"]}


# ---------------------------------------------------------------------------
# Malformed input — we don't mask bugs
# ---------------------------------------------------------------------------

def test_invalid_json_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json {{")
    with pytest.raises(json.JSONDecodeError):
        load_contracts(str(bad))


def test_list_entry_missing_required_tables_raises(write_json):
    path = write_json("c.json", [{"query_id": "NW1"}])
    with pytest.raises(KeyError):
        load_contracts(path)
