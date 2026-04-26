"""
Unit tests for mcp_server.scout.description_generator.

Covers:
- NullDescriptionGenerator returns "" and reports enabled=False
- Factory with SCOUT_DESCRIPTIONS_ENABLED unset/false returns Null
- Factory with toggle on but misconfigured client falls back to Null
- Factory with toggle on and valid client_factory returns an LLM generator
- LLMDescriptionGenerator invokes the injected client with a well-formed prompt
- LLMDescriptionGenerator swallows API errors and returns ""
- DiskCachedDescriptionGenerator hits the cache on the second call and
  persists results to the cache file
- Prompt builder includes required fields (table name, columns, FK targets)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from mcp_server.scout.description_generator import (
    DescriptionGenerator,
    DiskCachedDescriptionGenerator,
    LLMDescriptionGenerator,
    NullDescriptionGenerator,
    OpenAIDescriptionGenerator,
    _build_prompt,
    build_description_generator_from_env,
)


SAMPLE_TABLE: Dict[str, Any] = {
    "full_name": "dbo.KHKAdressen",
    "name": "KHKAdressen",
    "schema": "dbo",
    "type": "TABLE",
    "estimated_rows": 3450,
    "column_count": 18,
    "columns": [
        {"name": "AdrNr", "type": "int"},
        {"name": "Name1", "type": "varchar"},
        {"name": "Ort", "type": "varchar"},
    ],
    "primary_keys": ["AdrNr"],
    "foreign_keys": [
        {"column": "LandId", "referenced_schema": "dbo", "referenced_table": "KHKLand"}
    ],
}


# ---------------------------------------------------------------------------
# Null generator
# ---------------------------------------------------------------------------

def test_null_generator_returns_empty_and_reports_disabled():
    gen = NullDescriptionGenerator()
    assert gen.enabled is False
    assert gen.generate(SAMPLE_TABLE) == ""
    assert gen.generate({}) == ""


def test_null_generator_satisfies_protocol():
    gen = NullDescriptionGenerator()
    assert isinstance(gen, DescriptionGenerator)


# ---------------------------------------------------------------------------
# Factory / env toggle
# ---------------------------------------------------------------------------

def test_factory_defaults_to_null_when_toggle_unset():
    gen = build_description_generator_from_env(env={})
    assert isinstance(gen, NullDescriptionGenerator)
    assert gen.enabled is False


@pytest.mark.parametrize("value", ["false", "FALSE", "0", "no", "off", ""])
def test_factory_returns_null_for_false_like_values(value):
    gen = build_description_generator_from_env(env={"SCOUT_DESCRIPTIONS_ENABLED": value})
    assert isinstance(gen, NullDescriptionGenerator)


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "on"])
def test_factory_returns_anthropic_llm_when_provider_anthropic(value):
    fake_client = object()
    gen = build_description_generator_from_env(
        env={
            "SCOUT_DESCRIPTIONS_ENABLED": value,
            "SCOUT_DESCRIPTIONS_PROVIDER": "anthropic",
        },
        client_factory=lambda: fake_client,
    )
    assert isinstance(gen, LLMDescriptionGenerator)
    assert gen.enabled is True
    assert gen.client is fake_client


def test_factory_defaults_to_openai_provider():
    fake_client = object()
    gen = build_description_generator_from_env(
        env={"SCOUT_DESCRIPTIONS_ENABLED": "true"},
        client_factory=lambda: fake_client,
    )
    assert isinstance(gen, OpenAIDescriptionGenerator)
    assert gen.enabled is True
    assert gen.client is fake_client
    assert gen.model == "gpt-4o-mini"


def test_factory_wraps_in_disk_cache_when_cache_path_set(tmp_path: Path):
    cache_file = tmp_path / "cache.json"
    gen = build_description_generator_from_env(
        env={
            "SCOUT_DESCRIPTIONS_ENABLED": "true",
            "SCOUT_DESCRIPTIONS_PROVIDER": "anthropic",
            "SCOUT_DESCRIPTIONS_CACHE_PATH": str(cache_file),
        },
        client_factory=lambda: object(),
    )
    assert isinstance(gen, DiskCachedDescriptionGenerator)
    assert gen.cache_path == cache_file
    assert isinstance(gen.inner, LLMDescriptionGenerator)


def test_factory_wraps_openai_in_disk_cache(tmp_path: Path):
    cache_file = tmp_path / "cache.json"
    gen = build_description_generator_from_env(
        env={
            "SCOUT_DESCRIPTIONS_ENABLED": "true",
            "SCOUT_DESCRIPTIONS_CACHE_PATH": str(cache_file),
        },
        client_factory=lambda: object(),
    )
    assert isinstance(gen, DiskCachedDescriptionGenerator)
    assert isinstance(gen.inner, OpenAIDescriptionGenerator)


def test_factory_falls_back_to_null_when_client_init_raises():
    def bad_factory():
        raise RuntimeError("no api key")

    gen = build_description_generator_from_env(
        env={"SCOUT_DESCRIPTIONS_ENABLED": "true"},
        client_factory=bad_factory,
    )
    assert isinstance(gen, NullDescriptionGenerator)


def test_factory_passes_model_and_database_type_from_env_anthropic():
    gen = build_description_generator_from_env(
        env={
            "SCOUT_DESCRIPTIONS_ENABLED": "true",
            "SCOUT_DESCRIPTIONS_PROVIDER": "anthropic",
            "SCOUT_DESCRIPTIONS_MODEL": "claude-opus-4-6",
            "SCOUT_DESCRIPTIONS_DATABASE_TYPE": "sage",
        },
        client_factory=lambda: object(),
    )
    assert isinstance(gen, LLMDescriptionGenerator)
    assert gen.model == "claude-opus-4-6"
    assert gen.database_type == "sage"


def test_factory_passes_model_and_database_type_from_env_openai():
    gen = build_description_generator_from_env(
        env={
            "SCOUT_DESCRIPTIONS_ENABLED": "true",
            "SCOUT_DESCRIPTIONS_MODEL": "gpt-4o",
            "SCOUT_DESCRIPTIONS_DATABASE_TYPE": "sage",
        },
        client_factory=lambda: object(),
    )
    assert isinstance(gen, OpenAIDescriptionGenerator)
    assert gen.model == "gpt-4o"
    assert gen.database_type == "sage"


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def test_prompt_contains_table_metadata_and_instructions():
    prompt = _build_prompt(SAMPLE_TABLE, database_type="sage")
    assert "sage" in prompt
    assert "dbo.KHKAdressen" in prompt
    assert "AdrNr: int" in prompt
    assert "Name1: varchar" in prompt
    assert "Primary keys: AdrNr" in prompt
    assert "dbo.KHKLand" in prompt  # FK target
    assert "Output the description directly" in prompt


def test_prompt_handles_empty_columns():
    prompt = _build_prompt({"full_name": "dbo.X", "name": "X"}, database_type="northwind")
    assert "dbo.X" in prompt
    assert "no columns" in prompt


# ---------------------------------------------------------------------------
# LLM generator — injected client
# ---------------------------------------------------------------------------

class _TextBlock:
    def __init__(self, text: str):
        self.text = text


class _Response:
    def __init__(self, text: str):
        self.content = [_TextBlock(text)]


class _RecordingMessagesAPI:
    def __init__(self, text: str = "Kundentabelle (Customer table)"):
        self.text = text
        self.calls: List[Dict[str, Any]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Response(self.text)


class _FakeClient:
    def __init__(self, messages_api):
        self.messages = messages_api


def test_llm_generator_calls_client_with_prompt_and_returns_text():
    api = _RecordingMessagesAPI(text="  Generated description.  ")
    gen = LLMDescriptionGenerator(
        client=_FakeClient(api), model="claude-sonnet-4-20250514", database_type="sage"
    )

    result = gen.generate(SAMPLE_TABLE)

    assert result == "Generated description."
    assert len(api.calls) == 1
    call = api.calls[0]
    assert call["model"] == "claude-sonnet-4-20250514"
    assert call["messages"][0]["role"] == "user"
    assert "dbo.KHKAdressen" in call["messages"][0]["content"]


def test_llm_generator_returns_empty_string_on_api_error():
    class _BoomAPI:
        def create(self, **kwargs):
            raise RuntimeError("rate limit")

    gen = LLMDescriptionGenerator(client=_FakeClient(_BoomAPI()))
    assert gen.generate(SAMPLE_TABLE) == ""


def test_llm_generator_handles_plain_string_content():
    class _StrResponse:
        content = "plain string"

    class _StrAPI:
        def create(self, **kwargs):
            return _StrResponse()

    gen = LLMDescriptionGenerator(client=_FakeClient(_StrAPI()))
    assert gen.generate(SAMPLE_TABLE) == "plain string"


# ---------------------------------------------------------------------------
# OpenAI generator — injected client
# ---------------------------------------------------------------------------

class _OAIMessage:
    def __init__(self, content):
        self.content = content


class _OAIChoice:
    def __init__(self, content):
        self.message = _OAIMessage(content)


class _OAIResponse:
    def __init__(self, content):
        self.choices = [_OAIChoice(content)]


class _RecordingChatCompletionsAPI:
    def __init__(self, text: str = "Kundentabelle (Customer table)"):
        self.text = text
        self.calls: List[Dict[str, Any]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _OAIResponse(self.text)


class _FakeOpenAIClient:
    def __init__(self, chat_api):
        self.chat = type("C", (), {"completions": chat_api})()


def test_openai_generator_calls_client_with_prompt_and_returns_text():
    api = _RecordingChatCompletionsAPI(text="  Generated via OpenAI.  ")
    gen = OpenAIDescriptionGenerator(
        client=_FakeOpenAIClient(api), model="gpt-4o-mini", database_type="northwind"
    )

    result = gen.generate(SAMPLE_TABLE)

    assert result == "Generated via OpenAI."
    assert len(api.calls) == 1
    call = api.calls[0]
    assert call["model"] == "gpt-4o-mini"
    assert call["messages"][0]["role"] == "user"
    assert "dbo.KHKAdressen" in call["messages"][0]["content"]


def test_openai_generator_returns_empty_on_api_error():
    class _BoomAPI:
        def create(self, **kwargs):
            raise RuntimeError("rate limit")

    gen = OpenAIDescriptionGenerator(client=_FakeOpenAIClient(_BoomAPI()))
    assert gen.generate(SAMPLE_TABLE) == ""


# ---------------------------------------------------------------------------
# Disk cache
# ---------------------------------------------------------------------------

def test_disk_cache_stores_and_serves_from_cache(tmp_path: Path):
    api = _RecordingMessagesAPI(text="first description")
    inner = LLMDescriptionGenerator(client=_FakeClient(api))
    cache_file = tmp_path / "descriptions.json"
    cached = DiskCachedDescriptionGenerator(inner=inner, cache_path=str(cache_file))

    # First call: miss, inner invoked, persisted to disk.
    result1 = cached.generate(SAMPLE_TABLE)
    assert result1 == "first description"
    assert len(api.calls) == 1
    assert cache_file.exists()
    persisted = json.loads(cache_file.read_text())
    assert persisted["dbo.KHKAdressen"] == "first description"

    # Second call: hit, inner not invoked again even if response text changed.
    api.text = "second description"
    result2 = cached.generate(SAMPLE_TABLE)
    assert result2 == "first description"
    assert len(api.calls) == 1  # unchanged


def test_disk_cache_loads_existing_file_on_construction(tmp_path: Path):
    cache_file = tmp_path / "descriptions.json"
    cache_file.write_text(json.dumps({"dbo.KHKAdressen": "preloaded"}))

    api = _RecordingMessagesAPI(text="should not be used")
    inner = LLMDescriptionGenerator(client=_FakeClient(api))
    cached = DiskCachedDescriptionGenerator(inner=inner, cache_path=str(cache_file))

    assert cached.cache_size == 1
    assert cached.generate(SAMPLE_TABLE) == "preloaded"
    assert len(api.calls) == 0


def test_disk_cache_does_not_persist_empty_results(tmp_path: Path):
    class _EmptyAPI:
        def create(self, **kwargs):
            return _Response("")

    inner = LLMDescriptionGenerator(client=_FakeClient(_EmptyAPI()))
    cache_file = tmp_path / "descriptions.json"
    cached = DiskCachedDescriptionGenerator(inner=inner, cache_path=str(cache_file))

    assert cached.generate(SAMPLE_TABLE) == ""
    assert not cache_file.exists()
