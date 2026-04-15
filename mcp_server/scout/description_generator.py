"""
Runtime Semantic Description Generator (SDG v2)
================================================================================
Produces business-level descriptions for database tables, used as LLM context
in the Scout Mode catalog. This is the experimental independent variable for
the Scout+descriptions vs Scout structural-only ablation.

Design:
- `DescriptionGenerator` is the minimal interface any implementation provides.
- `NullDescriptionGenerator` always returns "" — used when the feature is
  toggled off. This keeps the catalog schema stable while ensuring the agent
  sees no description content.
- `LLMDescriptionGenerator` calls the Anthropic API. The `client` is injectable
  so tests can exercise the code path without an API key.
- `DiskCachedDescriptionGenerator` wraps any inner generator and persists
  results to a JSON file keyed by table `full_name`. This avoids paying for
  repeated generation across server restarts during the same experimental run.
- `build_description_generator_from_env()` is the factory used by ScoutRunner.

Environment variables:
- SCOUT_DESCRIPTIONS_ENABLED: "true" / "false"  (default: "false")
- SCOUT_DESCRIPTIONS_PROVIDER: "openai" | "anthropic"  (default: "openai")
- SCOUT_DESCRIPTIONS_MODEL:   model id
    default: "gpt-4o-mini" for openai, "claude-sonnet-4-20250514" for anthropic
- SCOUT_DESCRIPTIONS_DATABASE_TYPE: "northwind" | "sage"  (default: "northwind")
- SCOUT_DESCRIPTIONS_CACHE_PATH: path to JSON cache        (default: "" = disabled)
- OPENAI_API_KEY:    required when provider=openai
- ANTHROPIC_API_KEY: required when provider=anthropic
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ============================================================================
# Interface
# ============================================================================

@runtime_checkable
class DescriptionGenerator(Protocol):
    """Protocol: anything with these attributes is a description generator."""

    enabled: bool

    def generate(self, table_info: Dict[str, Any]) -> str:  # pragma: no cover - protocol
        """Return a description string for a single table. Never raises."""
        ...


# ============================================================================
# Null implementation — used when the feature is disabled
# ============================================================================

class NullDescriptionGenerator:
    """No-op generator. Returns empty strings. Used when toggle is off."""

    enabled = False

    def generate(self, table_info: Dict[str, Any]) -> str:
        return ""


# ============================================================================
# Prompt construction
# ============================================================================

def _format_columns_for_prompt(columns: List[Dict[str, Any]], limit: int = 20) -> str:
    """Render up to `limit` columns as ' - name: type' lines for the prompt."""
    lines: List[str] = []
    for col in columns[:limit]:
        if not isinstance(col, dict):
            continue
        name = col.get("name") or ""
        dtype = col.get("type") or ""
        if name:
            lines.append(f"  - {name}: {dtype}")
    return "\n".join(lines) if lines else "  (no columns)"


def _format_fk_targets(foreign_keys: List[Dict[str, Any]]) -> str:
    targets: List[str] = []
    for fk in foreign_keys or []:
        if not isinstance(fk, dict):
            continue
        ref = fk.get("referenced_table") or fk.get("ref_table") or ""
        ref_schema = fk.get("referenced_schema") or fk.get("ref_schema") or ""
        if ref:
            targets.append(f"{ref_schema}.{ref}" if ref_schema else ref)
    return ", ".join(targets) if targets else "(none)"


def _build_prompt(table_info: Dict[str, Any], database_type: str) -> str:
    """Construct the per-table prompt. Kept as a pure function for unit testing."""
    full_name = table_info.get("full_name", table_info.get("name", "(unknown)"))
    ttype = table_info.get("type", "TABLE")
    estimated_rows = table_info.get("estimated_rows", 0)
    columns = table_info.get("columns", []) or []
    column_count = table_info.get("column_count", len(columns))
    primary_keys = ", ".join(table_info.get("primary_keys", []) or []) or "(none)"
    fk_targets = _format_fk_targets(table_info.get("foreign_keys", []) or [])
    col_block = _format_columns_for_prompt(columns, limit=20)

    return (
        f"You are a database documentation expert. Given the following table metadata "
        f"from a {database_type} ERP system, generate a concise business-level "
        f"description.\n\n"
        f"Table: {full_name}\n"
        f"Type: {ttype}\n"
        f"Estimated rows: {estimated_rows}\n"
        f"Columns ({column_count} total, showing top 20):\n"
        f"{col_block}\n\n"
        f"Primary keys: {primary_keys}\n"
        f"Foreign keys to: {fk_targets}\n\n"
        f"Instructions:\n"
        f"1. First line: German business name + English translation in parentheses.\n"
        f"2. What this table stores and what business process it belongs to.\n"
        f"3. Key columns and their business meaning.\n"
        f"4. Common German business terms that would refer to this table's data.\n"
        f"5. Keep under 200 words.\n\n"
        f"Output the description directly, no JSON wrapping."
    )


# ============================================================================
# LLM-backed implementation
# ============================================================================

class LLMDescriptionGenerator:
    """
    Anthropic-API-backed description generator.

    The `client` is injectable for tests. In production the factory creates
    `anthropic.Anthropic()` from `ANTHROPIC_API_KEY`.
    """

    enabled = True

    def __init__(
        self,
        client: Any,
        model: str = "claude-sonnet-4-20250514",
        database_type: str = "northwind",
        max_tokens: int = 400,
    ):
        self.client = client
        self.model = model
        self.database_type = database_type
        self.max_tokens = max_tokens

    def generate(self, table_info: Dict[str, Any]) -> str:
        prompt = _build_prompt(table_info, self.database_type)
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            logger.warning(
                "LLM description generation failed for %s: %s",
                table_info.get("full_name", "?"),
                exc,
            )
            return ""

        return _extract_text_from_response(response).strip()


class OpenAIDescriptionGenerator:
    """
    OpenAI Chat Completions-backed description generator.

    Mirrors LLMDescriptionGenerator's interface but uses the OpenAI SDK.
    The `client` is injectable for tests; in production the factory builds
    `openai.OpenAI()` from `OPENAI_API_KEY`.
    """

    enabled = True

    def __init__(
        self,
        client: Any,
        model: str = "gpt-4o-mini",
        database_type: str = "northwind",
        max_tokens: int = 400,
    ):
        self.client = client
        self.model = model
        self.database_type = database_type
        self.max_tokens = max_tokens

    def generate(self, table_info: Dict[str, Any]) -> str:
        prompt = _build_prompt(table_info, self.database_type)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            logger.warning(
                "LLM description generation failed for %s: %s",
                table_info.get("full_name", "?"),
                exc,
            )
            return ""

        return _extract_text_from_openai_response(response).strip()


def _extract_text_from_openai_response(response: Any) -> str:
    """
    Pull text out of an OpenAI chat.completions response. Tolerates mock
    shapes used in tests (plain dicts, bare strings).
    """
    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, dict):
        choices = response.get("choices")
    if not choices:
        return ""
    first = choices[0]
    message = getattr(first, "message", None)
    if message is None and isinstance(first, dict):
        message = first.get("message")
    if message is None:
        return ""
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    return content if isinstance(content, str) else ""


def _extract_text_from_response(response: Any) -> str:
    """
    Pull text out of an Anthropic Messages API response. Tolerates mock shapes
    used in tests (plain dicts, bare strings on `.content`).
    """
    content = getattr(response, "content", None)
    if content is None and isinstance(response, dict):
        content = response.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            text = getattr(block, "text", None)
            if text is None and isinstance(block, dict):
                text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
        return "".join(parts)
    return ""


# ============================================================================
# Disk cache wrapper — keyed by table full_name
# ============================================================================

class DiskCachedDescriptionGenerator:
    """
    Wrap an inner generator with a JSON-file cache.

    Cache shape: {"full_name": "description", ...}
    Cache hit → return cached value without invoking inner generator.
    Cache miss → invoke inner, persist non-empty results immediately.
    """

    enabled = True

    def __init__(self, inner: DescriptionGenerator, cache_path: str):
        self.inner = inner
        self.cache_path = Path(cache_path)
        self._cache: Dict[str, str] = self._load()

    @property
    def cache_size(self) -> int:
        return len(self._cache)

    def _load(self) -> Dict[str, str]:
        if not self.cache_path.exists():
            return {}
        try:
            with self.cache_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except Exception as exc:
            logger.warning(
                "Failed to load description cache at %s: %s", self.cache_path, exc
            )
        return {}

    def _persist(self) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with self.cache_path.open("w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.warning(
                "Failed to persist description cache at %s: %s", self.cache_path, exc
            )

    def generate(self, table_info: Dict[str, Any]) -> str:
        full_name = str(table_info.get("full_name") or table_info.get("name") or "")
        if not full_name:
            return ""

        if full_name in self._cache:
            return self._cache[full_name]

        description = self.inner.generate(table_info) or ""
        if description:
            self._cache[full_name] = description
            self._persist()
        return description


# ============================================================================
# Factory
# ============================================================================

def _parse_bool(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def build_description_generator_from_env(
    env: Optional[Dict[str, str]] = None,
    client_factory=None,
) -> DescriptionGenerator:
    """
    Construct a description generator from environment variables.

    Args:
        env: Optional dict of env vars, used for tests. Defaults to os.environ.
        client_factory: Optional callable returning an Anthropic client, used
                        for tests to inject a mock.

    Returns:
        A DescriptionGenerator instance. Never raises — on misconfiguration
        it logs and returns NullDescriptionGenerator so startup is never broken.
    """
    env = env if env is not None else os.environ
    if not _parse_bool(env.get("SCOUT_DESCRIPTIONS_ENABLED")):
        return NullDescriptionGenerator()

    provider = (env.get("SCOUT_DESCRIPTIONS_PROVIDER") or "openai").strip().lower()
    default_model = "gpt-4o-mini" if provider == "openai" else "claude-sonnet-4-20250514"
    model = env.get("SCOUT_DESCRIPTIONS_MODEL") or default_model
    database_type = env.get("SCOUT_DESCRIPTIONS_DATABASE_TYPE") or "northwind"
    cache_path = env.get("SCOUT_DESCRIPTIONS_CACHE_PATH") or ""

    if client_factory is None:
        if provider == "anthropic":
            def client_factory():  # type: ignore[no-redef]
                import anthropic  # lazy import

                return anthropic.Anthropic(api_key=env.get("ANTHROPIC_API_KEY"))
        else:
            def client_factory():  # type: ignore[no-redef]
                import openai  # lazy import

                return openai.OpenAI(api_key=env.get("OPENAI_API_KEY"))

    try:
        client = client_factory()
    except Exception as exc:
        logger.error(
            "SCOUT_DESCRIPTIONS_ENABLED=true but %s client init failed: %s. "
            "Falling back to NullDescriptionGenerator.",
            provider,
            exc,
        )
        return NullDescriptionGenerator()

    inner: DescriptionGenerator
    if provider == "anthropic":
        inner = LLMDescriptionGenerator(
            client=client, model=model, database_type=database_type
        )
    else:
        inner = OpenAIDescriptionGenerator(
            client=client, model=model, database_type=database_type
        )

    if cache_path:
        inner = DiskCachedDescriptionGenerator(inner=inner, cache_path=cache_path)

    return inner
