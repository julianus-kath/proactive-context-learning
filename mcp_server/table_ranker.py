"""
Table & View Ranker for Semantic Relevance Scoring

Phase 7.1 baseline (tables) + extended Phase 7.x (views-first capability).

- Tables: keeps existing heuristics (entity/fuzzy/type/metadata) to remain stable.
- Views: adds unified scoring with normalized signals and lightweight BM25 over
  name + columns + sanitized definition + subject tags.

All ranking uses catalog-only metadata (Scout cache). No live DB calls.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Dict, Optional, Tuple, Any, Set

try:
    # Local config for thresholds/flags
    from mcp_server.config import config as mcp_config
except Exception:  # pragma: no cover - allow import without full server boot
    mcp_config = None

logger = logging.getLogger(__name__)


# Generic table classification based on Scout catalog metadata
# No hardcoded terms - classification is data-driven


def classify_table_by_metadata(table: Dict[str, Any], catalog_adapter=None) -> Dict[str, Any]:
    """
    Classify table purpose based on Scout catalog metadata.
    Returns classification scores for different table types.
    """
    classification = {
        "customer_table": 0.0,
        "product_table": 0.0,
        "transaction_table": 0.0,
        "financial_table": 0.0,
        "relationship_table": 0.0
    }

    table_name = table.get("name", "").lower()
    estimated_rows = table.get("estimated_rows", 0)
    fk_count = table.get("fk_count", 0)

    # Get column metadata from catalog if available
    if catalog_adapter and hasattr(catalog_adapter, 'get_table_columns'):
        try:
            columns = catalog_adapter.get_table_columns(table.get("schema"), table.get("name"))
        except:
            columns = []
    else:
        columns = []

    # Classify based on column types and names
    id_columns = 0
    name_columns = 0
    date_columns = 0
    numeric_columns = 0
    fk_columns = 0

    for col in columns:
        col_name = col.get("name", "").lower()
        col_type = col.get("data_type", "").lower()

        # Count different column types
        if "id" in col_name or "key" in col_name:
            id_columns += 1
        if any(term in col_name for term in ["name", "title", "description"]):
            name_columns += 1
        if any(term in col_type for term in ["date", "time", "datetime"]):
            date_columns += 1
        if any(term in col_type for term in ["int", "float", "decimal", "numeric", "money"]):
            numeric_columns += 1
        if col.get("is_foreign_key"):
            fk_columns += 1

    # Classification logic based on metadata patterns
    total_columns = len(columns) if columns else table.get("column_count", 0)

    # Customer table indicators
    if name_columns >= 1 and fk_count <= 3 and estimated_rows > 10:
        classification["customer_table"] = min(0.8, (name_columns / max(total_columns, 1)) * 2)

    # Product table indicators
    if name_columns >= 1 and numeric_columns >= 1 and fk_count <= 2:
        classification["product_table"] = min(0.8, (name_columns + numeric_columns) / max(total_columns, 1))

    # Transaction table indicators
    if date_columns >= 1 and numeric_columns >= 2 and fk_count >= 2:
        classification["transaction_table"] = min(0.9, (date_columns + numeric_columns + fk_count) / max(total_columns, 3))

    # Financial table indicators
    if numeric_columns >= 3 and date_columns >= 1:
        classification["financial_table"] = min(0.8, (numeric_columns + date_columns) / max(total_columns, 2))

    # Relationship table indicators (junction tables)
    if fk_count >= 3 and id_columns >= 2 and estimated_rows < 1000:
        classification["relationship_table"] = min(0.7, fk_count / max(total_columns, 1))

    return classification


def tokenize_table_name(table_name: str) -> List[str]:
    """Generic tokenization of table names using common separators."""
    if not table_name:
        return []

    # Convert to lowercase and split on common separators
    tokens = []
    name = table_name.lower()

    # Split on underscores, camelCase, and numbers
    import re
    # Split on underscores
    parts = name.split('_')
    for part in parts:
        # Split camelCase
        camel_parts = re.findall(r'[a-z]+|[A-Z][a-z]+', part)
        if camel_parts:
            tokens.extend([p.lower() for p in camel_parts if len(p) > 1])
        else:
            tokens.append(part)

    # Remove duplicates and short tokens
    tokens = list(set(tokens))
    tokens = [t for t in tokens if len(t) > 1]

    return tokens


# -----------------------------
# Existing Table Ranking (kept)
# -----------------------------

@dataclass
class RankedTable:
    """A table with its relevance score."""
    schema: str
    name: str
    full_name: str
    score: float  # 0.0 to 1.0
    reasons: List[str]  # Why this table was ranked high
    estimated_rows: Optional[int] = None
    column_count: Optional[int] = None
    fk_count: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": self.schema,
            "name": self.name,
            "full_name": self.full_name,
            "score": self.score,
            "reasons": self.reasons,
            "estimated_rows": self.estimated_rows,
            "column_count": self.column_count,
            "fk_count": self.fk_count,
        }


class TableRanker:
    """
    Ranks database tables by relevance to user queries.

    Uses multiple scoring dimensions:
    - Exact name matches (highest weight)
    - Fuzzy/substring matches
    - Entity keywords in column names
    - Type compatibility with query intent
    - Table connectedness (foreign keys, row volume)
    """

    # Scoring weights
    EXACT_MATCH_WEIGHT = 1.0
    ENTITY_MATCH_WEIGHT = 0.8
    COLUMN_MATCH_WEIGHT = 0.6
    FUZZY_MATCH_WEIGHT = 0.4
    FK_BONUS = 0.1  # Bonus for tables with foreign keys
    SIZE_FACTOR = 0.05  # Small bonus for larger tables

    # Column type indicators
    NUMERIC_TYPES = {"int", "float", "decimal", "numeric", "bigint", "smallint", "money", "real"}
    DATE_TYPES = {"date", "datetime", "datetime2", "timestamp", "time"}
    TEXT_TYPES = {"varchar", "text", "nvarchar", "char", "string"}

    def rank_tables(
        self,
        tables: List[Dict[str, Any]],
        entities: List[str],
        intent_operations: List[str],
        catalog_adapter=None,
    ) -> List[RankedTable]:
        ranked: List[RankedTable] = []

        for table in tables:
            score = 0.0
            reasons: List[str] = []

            # Extract table info
            schema = table.get("schema", "")
            name = table.get("name", table.get("table", ""))
            full_name = table.get("full_name") or table.get("fqtn") or (
                f"{schema}.{name}" if schema and name else name
            )
            estimated_rows = table.get("estimated_rows")
            column_count = table.get("column_count")
            fk_count = table.get("fk_count")

            # 1. Entity matches using generic tokenization
            for entity in entities or []:
                if not name:
                    continue

                entity_lower = entity.lower()
                table_tokens = tokenize_table_name(name)

                # Exact match against table name
                if entity_lower == name.lower():
                    score += self.EXACT_MATCH_WEIGHT
                    reasons.append(f"Exact table name match: '{entity}'")
                    continue

                # Token-based matching
                for token in table_tokens:
                    token_lower = token.lower()

                    # Exact token match
                    if entity_lower == token_lower:
                        score += self.ENTITY_MATCH_WEIGHT
                        reasons.append(f"Exact token match: '{entity}' in table token '{token}'")
                        break

                    # Substring match in token
                    elif entity_lower in token_lower or token_lower in entity_lower:
                        score += self.COLUMN_MATCH_WEIGHT
                        reasons.append(f"Substring match: '{entity}' in token '{token}'")
                        break

            # 2. Generic fuzzy matching as fallback
            for entity in entities or []:
                if not name:
                    continue

                fuzzy_score = self._fuzzy_match(entity, name)
                if fuzzy_score > 0.7:
                    score += fuzzy_score * self.FUZZY_MATCH_WEIGHT
                    reasons.append(f"Fuzzy match: '{entity}' ~ '{name}' ({fuzzy_score:.2f})")

            # 4. Table classification bonus based on query intent
            table_classification = classify_table_by_metadata(table, catalog_adapter)

            # Map query entities to table types for semantic matching
            entity_to_table_type = {
                "customer": "customer_table",
                "customers": "customer_table",
                "product": "product_table",
                "products": "product_table",
                "item": "product_table",
                "items": "product_table",
                "order": "transaction_table",
                "orders": "transaction_table",
                "transaction": "transaction_table",
                "transactions": "transaction_table",
                "sale": "transaction_table",
                "sales": "transaction_table",
                "invoice": "financial_table",
                "invoices": "financial_table",
                "payment": "financial_table",
                "payments": "financial_table"
            }

            # Check if any entity matches a known table type
            for entity in entities or []:
                entity_lower = entity.lower()
                if entity_lower in entity_to_table_type:
                    table_type = entity_to_table_type[entity_lower]
                    type_score = table_classification.get(table_type, 0.0)
                    if type_score > 0.5:
                        score += type_score * 0.5  # Bonus for matching table type
                        reasons.append(f"Table type match: '{entity}' → {table_type} ({type_score:.2f})")

            # 5. Type compatibility
            type_score = self._score_type_compatibility(name or "", intent_operations or [], catalog_adapter, table)
            if type_score > 0:
                score += type_score
                if intent_operations:
                    reasons.append(
                        f"Type compatible for operations: {', '.join(intent_operations)}"
                    )

            # 4. Connectedness
            if isinstance(fk_count, int) and fk_count > 0:
                score += self.FK_BONUS * min(fk_count / 5, 1.0)  # Cap at 5 FKs
                reasons.append(f"Well-connected ({fk_count} foreign keys)")

            # 5. Size bonus
            if isinstance(estimated_rows, int) and estimated_rows > 1000:
                size_bonus = min(estimated_rows / 100000, 1.0) * self.SIZE_FACTOR
                score += size_bonus
                reasons.append(f"Sizeable table ({estimated_rows} rows)")

            # Only include tables with meaningful scores
            # If entities is provided, require score > 0
            # If entities is empty/missing, skip (don't pollute results with all tables)
            if score > 0:
                ranked.append(
                    RankedTable(
                        schema=schema,
                        name=name,
                        full_name=full_name or name,
                        score=min(score, 1.0),
                        reasons=reasons,
                        estimated_rows=estimated_rows,
                        column_count=column_count,
                        fk_count=fk_count,
                    )
                )

        ranked.sort(key=lambda t: (-t.score, t.name))
        return ranked

    def _fuzzy_match(self, entity: str, table_name: str) -> float:
        entity_lower = entity.lower()
        table_lower = table_name.lower()
        if entity_lower in table_lower or table_lower in entity_lower:
            return 0.9
        matcher = SequenceMatcher(None, entity_lower, table_lower)
        return matcher.ratio()

    def _score_type_compatibility(
        self, table_name: str, operations: List[str], catalog_adapter, table: Dict[str, Any]
    ) -> float:
        if not operations:
            return 0.2  # Small baseline
        score = 0.0
        numeric_columns = table.get("numeric_columns", [])
        date_columns = table.get("date_columns", [])
        if any(op in ["sum", "avg", "average", "max", "min", "total"] for op in operations):
            if numeric_columns:
                score += 0.3 * min(
                    len(numeric_columns) / max(table.get("column_count", 1), 1), 1.0
                )
            elif self._has_numeric_indicator(table_name):
                score += 0.3
        if any(op in ["trend", "trend_over_time", "monthly", "yearly"] for op in operations):
            if date_columns:
                score += 0.3
            elif self._has_date_indicator(table_name):
                score += 0.3
        if operations:
            score += 0.1
        return min(score, 1.0)

    def _has_numeric_indicator(self, table_name: str) -> bool:
        indicators = [
            "sales",
            "revenue",
            "profit",
            "cost",
            "amount",
            "price",
            "quantity",
            "count",
        ]
        return any(indicator in table_name.lower() for indicator in indicators)

    def _has_date_indicator(self, table_name: str) -> bool:
        indicators = ["sales", "order", "transaction", "event", "log", "history"]
        return any(indicator in table_name.lower() for indicator in indicators)

    def select_best_tables(
        self, ranked_tables: List[RankedTable], max_tables: int = 3, min_score: float = 0.3
    ) -> List[RankedTable]:
        qualified = [t for t in ranked_tables if t.score >= min_score]
        return qualified[:max_tables]


def rank_tables(
    tables: List[Dict[str, Any]],
    entities: List[str],
    operations: List[str] | None = None,
    catalog_adapter=None,
) -> List[RankedTable]:
    ranker = TableRanker()
    return ranker.rank_tables(tables, entities, operations or [], catalog_adapter)


# -----------------------------
# Views Ranking (new)
# -----------------------------

@dataclass
class RankedView:
    schema: str
    name: str
    full_name: str
    score: float
    reasons: List[str]
    role_coverage: float
    has_rows: int
    estimated_rows: int
    subject_match: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": self.schema,
            "name": self.name,
            "full_name": self.full_name,
            "score": self.score,
            "reasons": self.reasons,
            "role_coverage": self.role_coverage,
            "has_rows": self.has_rows,
            "estimated_rows": self.estimated_rows,
            "subject_match": self.subject_match,
        }


_WORD_RE = re.compile(r"[a-z0-9_]+")
_STOP = {
    "the",
    "and",
    "of",
    "in",
    "by",
    "for",
    "to",
    "a",
    "on",
    "with",
    "view",
    "vw",
    "dbo",
}


def _tokenize(text: str) -> List[str]:
    text = (text or "").lower()
    return [t for t in _WORD_RE.findall(text) if t and t not in _STOP]


def _infer_query_subject_tags(query: str) -> Set[str]:
    q = (query or "").lower()
    tags = set()
    mapping = {
        "sales": ["sale", "sales", "revenue", "amount", "gross", "net"],
        "invoice": ["invoice", "invoices", "billing", "bill"],
        "stock": ["stock", "inventory", "warehouse"],
        "crm": ["crm", "customer", "lead", "opportunity"],
        "product": ["product", "sku", "item"],
        "customer": ["customer", "client", "account"],
        "supplier": ["supplier", "vendor"],
        "employee": ["employee", "staff"],
    }
    for tag, kws in mapping.items():
        if any(kw in q for kw in kws):
            tags.add(tag)
    return tags


def _infer_required_roles(query: str) -> List[str]:
    q = (query or "").lower()
    roles: List[str] = []
    # Date/time intent
    if any(k in q for k in ["last quarter", "last month", "this month", "this quarter", "year", "month", "date", "trend", "over time"]):
        roles.append("date")
    # Measure intent
    if any(k in q for k in ["sum", "total", "top", "revenue", "sales", "amount", "count", "avg", "average"]):
        roles.append("measure")
    # Product/customer keys
    if any(k in q for k in ["product", "sku", "item"]):
        roles.append("product_key")
    if any(k in q for k in ["customer", "client", "account"]):
        roles.append("customer_key")
    # Deduplicate while preserving order
    seen = set()
    return [r for r in roles if not (r in seen or seen.add(r))]


def _detect_roles_in_view(view: Dict[str, Any]) -> Set[str]:
    roles: Set[str] = set()
    # Columns may come as list of dicts ({name: .., type: ..}) or list of names
    cols_raw = view.get("columns", [])
    col_names: List[str] = []
    for c in cols_raw:
        if isinstance(c, dict):
            col_names.append(str(c.get("name", "")))
        else:
            col_names.append(str(c))
    # Use cached hints if present
    numeric_cols = set(view.get("numeric_columns", []))
    date_cols = set(view.get("date_columns", []))
    names = [n.lower() for n in col_names]
    # Date role
    if date_cols or any(x for x in names if any(k in x for k in ["date", "dt", "time", "month", "year"])):
        roles.add("date")
    # Measure role
    if numeric_cols or any(x for x in names if any(k in x for k in ["amount", "qty", "quantity", "price", "revenue", "sales", "count"])):
        roles.add("measure")
    # Product/customer keys
    if any(x for x in names if any(k in x for k in ["product_id", "product_key", "sku"])):
        roles.add("product_key")
    if any(x for x in names if any(k in x for k in ["customer_id", "customer_key", "account_id"])):
        roles.add("customer_key")
    return roles


def _prepare_doc_text_for_view(view: Dict[str, Any]) -> str:
    name = view.get("name", "") or view.get("view", "")
    schema = view.get("schema", "")
    subject_tags = view.get("subject_tags", [])
    # Columns formatting
    cols_raw = view.get("columns", [])
    col_names: List[str] = []
    for c in cols_raw:
        if isinstance(c, dict):
            col_names.append(str(c.get("name", "")))
        else:
            col_names.append(str(c))
    definition = view.get("definition_sanitized", "")
    if definition and len(definition) > 2000:
        definition = definition[:2000]
    parts = [schema, name] + col_names + subject_tags + [definition]
    return " ".join([p for p in parts if p])


def _bm25_scores(query: str, docs: List[str]) -> List[float]:
    # Lightweight BM25 (Okapi) with corpus-local IDF
    k1, b = 1.5, 0.75
    q_tokens = _tokenize(query)
    if not docs:
        return []
    tokenized_docs = [_tokenize(d) for d in docs]
    doc_lens = [len(t) or 1 for t in tokenized_docs]
    avgdl = sum(doc_lens) / max(len(doc_lens), 1)
    N = len(tokenized_docs)
    # Document frequencies
    df = defaultdict(int)
    for tset in [set(ts) for ts in tokenized_docs]:
        for t in tset:
            df[t] += 1
    # Compute scores per document
    scores: List[float] = []
    for idx, terms in enumerate(tokenized_docs):
        tf = Counter(terms)
        dl = doc_lens[idx]
        s = 0.0
        for qt in q_tokens:
            if qt not in df:
                continue
            idf = math.log((N - df[qt] + 0.5) / (df[qt] + 0.5) + 1.0)
            freq = tf.get(qt, 0)
            if freq == 0:
                continue
            denom = freq + k1 * (1 - b + b * (dl / avgdl))
            s += idf * ((freq * (k1 + 1)) / denom)
        scores.append(s)
    # Normalize to [0,1]
    if not scores:
        return []
    max_s = max(scores) or 1.0
    return [min(s / max_s, 1.0) for s in scores]


def rank_views(
    query: str,
    views: List[Dict[str, Any]],
    include_empty: Optional[bool] = None,
    *,
    view_priority_bonus: Optional[float] = None,
    role_coverage_threshold: Optional[float] = None,
) -> List[RankedView]:
    """
    Rank views using normalized signals and optional empty filtering.

    score = 0.45*bm25_text + 0.25*role_coverage + 0.15*subject_match + 0.10*has_rows + 0.05*is_view_bonus
    """
    cfg_bonus = (
        view_priority_bonus
        if view_priority_bonus is not None
        else (mcp_config.ranker_view_priority_bonus if mcp_config else 0.15)
    )
    cfg_threshold = (
        role_coverage_threshold
        if role_coverage_threshold is not None
        else (mcp_config.view_role_coverage_threshold if mcp_config else 0.7)
    )
    include_empty = (
        include_empty
        if include_empty is not None
        else (mcp_config.include_empty_by_default if mcp_config else False)
    )

    # Prepare BM25 corpus
    docs = [_prepare_doc_text_for_view(v) for v in views]
    bm25_list = _bm25_scores(query, docs)

    # Subject tags overlap
    query_tags = _infer_query_subject_tags(query)

    ranked: List[RankedView] = []

    for idx, v in enumerate(views):
        schema = v.get("schema", "")
        name = v.get("name") or v.get("view") or ""
        full_name = v.get("full_name") or v.get("fqvn") or (f"{schema}.{name}" if schema and name else name)
        est_rows = int(v.get("est_rows") or v.get("estimated_rows") or 0)
        has_rows = 1 if (v.get("has_rows") is True or est_rows > 0) else 0

        # Filter empties if requested
        if not include_empty and has_rows == 0:
            continue

        # Role coverage
        required_roles = _infer_required_roles(query)
        present_roles = _detect_roles_in_view(v)
        role_coverage = 0.0
        contributing_roles: List[str] = []
        if required_roles:
            covered = [r for r in required_roles if r in present_roles]
            role_coverage = len(covered) / max(len(required_roles), 1)
            contributing_roles = covered

        # Subject match
        v_tags = set([t.lower() for t in v.get("subject_tags", [])])
        if not v_tags:
            # Infer from name/columns when tags absent
            inferred = set()
            tokens = set(_tokenize((v.get("name") or "") + " " + " ".join([c.get("name", c) if isinstance(c, dict) else str(c) for c in v.get("columns", [])])))
            mapping = {
                "sales": {"sales", "revenue", "amount"},
                "invoice": {"invoice", "billing"},
                "stock": {"stock", "inventory", "warehouse"},
                "crm": {"crm", "customer", "lead"},
                "product": {"product", "sku", "item"},
                "customer": {"customer", "client", "account"},
            }
            for tag, kws in mapping.items():
                if tokens & kws:
                    inferred.add(tag)
            v_tags = inferred
        # Jaccard overlap normalized
        inter = len(query_tags & v_tags)
        union = len(query_tags | v_tags) or 1
        subject_match = inter / union

        # BM25
        bm25_text = bm25_list[idx] if idx < len(bm25_list) else 0.0

        # View bonus when role coverage passes threshold
        is_view_bonus = cfg_bonus if role_coverage >= cfg_threshold and cfg_threshold > 0 else 0.0

        # Final weighted score
        score = (
            0.45 * bm25_text
            + 0.25 * role_coverage
            + 0.15 * subject_match
            + 0.10 * has_rows
            + 0.05 * is_view_bonus
        )

        reasons: List[str] = []
        reasons.append(f"bm25_text: {bm25_text:.2f}")
        if required_roles:
            if contributing_roles:
                missing = [r for r in required_roles if r not in contributing_roles]
                reasons.append(
                    f"role_coverage: {role_coverage:.2f} (covered: {', '.join(contributing_roles)}; missing: {', '.join(missing) if missing else 'none'})"
                )
            else:
                reasons.append(f"role_coverage: {role_coverage:.2f} (no required roles covered)")
        reasons.append(f"subject_match: {subject_match:.2f} (q_tags: {', '.join(sorted(query_tags))}; v_tags: {', '.join(sorted(v_tags))})")
        reasons.append(f"has_rows: {bool(has_rows)}{f' (est_rows={est_rows})' if est_rows else ''}")
        if is_view_bonus > 0:
            reasons.append(f"is_view_bonus applied: +{is_view_bonus:.2f}")

        ranked.append(
            RankedView(
                schema=schema,
                name=name,
                full_name=full_name,
                score=round(min(max(score, 0.0), 1.0), 4),
                reasons=reasons,
                role_coverage=round(role_coverage, 4),
                has_rows=has_rows,
                estimated_rows=est_rows,
                subject_match=round(subject_match, 4),
            )
        )

    ranked.sort(key=lambda r: (-r.score, -r.role_coverage, r.name))
    return ranked


def select_best_view(
    ranked_views: List[RankedView],
    *,
    min_score: float = 0.80,
    min_role_coverage: Optional[float] = None,
) -> Optional[RankedView]:
    threshold = min_role_coverage if min_role_coverage is not None else (
        mcp_config.view_role_coverage_threshold if mcp_config else 0.7
    )
    for rv in ranked_views:
        if rv.score >= min_score and rv.role_coverage >= threshold:
            return rv
    return None