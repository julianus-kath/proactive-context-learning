from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


class ConceptMapper:
    def __init__(self, concepts_path: Optional[str] = None):
        base_path = (
            Path(concepts_path)
            if concepts_path
            else Path(__file__).resolve().parent.parent / "data" / "concepts.json"
        )
        self._concepts_path = base_path
        self._concepts = self._load_concepts()

    def map(self, user_input: str, intent: Optional[Dict[str, Any]] = None, catalog_concepts: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
        intent = intent or {}
        tokens = self._tokenize(user_input, intent)
        merged_concepts = self._merge_concepts(catalog_concepts)
        matched: List[Tuple[float, Dict[str, Any]]] = []
        for concept in merged_concepts:
            score = self._score_concept(concept, tokens, intent)
            if score > 0:
                matched.append((score, concept))
        matched.sort(key=lambda item: item[0], reverse=True)
        seed_tables: List[str] = []
        kpi_expressions: Dict[str, str] = {}
        time_fields: List[str] = []
        join_hints: Dict[str, List[Dict[str, Any]]] = {}
        explanations: List[str] = []
        concept_names: List[str] = []
        for score, concept in matched:
            name = str(concept.get("name") or "").strip()
            if not name:
                continue
            concept_names.append(name)
            for table in concept.get("tables", []):
                if table and table not in seed_tables:
                    seed_tables.append(table)
            expr = concept.get("kpi_expression")
            if isinstance(expr, str) and expr:
                kpi_expressions[name] = expr
            for time_field in concept.get("time_fields", []):
                if time_field and time_field not in time_fields:
                    time_fields.append(time_field)
            hints = concept.get("join_hints") or []
            if hints:
                join_hints[name] = hints
            desc = concept.get("description")
            if isinstance(desc, str) and desc:
                explanations.append(f"{name}: {desc}")
        return {
            "concepts": concept_names,
            "seed_tables": seed_tables,
            "kpi_expressions": kpi_expressions,
            "time_field_hints": time_fields,
            "join_hints": join_hints,
            "explanations": explanations,
            "matched_concepts": [concept for _, concept in matched],
        }

    def _load_concepts(self) -> List[Dict[str, Any]]:
        if self._concepts_path.exists():
            try:
                with self._concepts_path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                concepts = payload.get("concepts") or []
                return [c for c in concepts if isinstance(c, dict)]
            except Exception:
                return []
        return []

    def _merge_concepts(self, catalog_concepts: Optional[Sequence[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        merged = list(self._concepts)
        if catalog_concepts:
            seen = {str(c.get("name")).lower() for c in merged if c.get("name")}
            for concept in catalog_concepts:
                if not isinstance(concept, dict):
                    continue
                name = str(concept.get("name") or "").lower()
                if not name or name in seen:
                    continue
                merged.append(concept)
        return merged

    def _tokenize(self, user_input: str, intent: Dict[str, Any]) -> List[str]:
        tokens: List[str] = []
        if user_input:
            tokens.extend(self._split_text(user_input))
        for field in ["raw_query", "discovery_query"]:
            value = intent.get(field)
            if value:
                tokens.extend(self._split_text(value))
        for key in ["primary_entities", "secondary_entities", "metrics", "keywords_for_discovery", "filters"]:
            for item in intent.get(key, []) or []:
                if isinstance(item, dict):
                    tokens.extend(self._split_text(json.dumps(item)))
                else:
                    tokens.extend(self._split_text(str(item)))
        return list(dict.fromkeys(tokens))

    def _split_text(self, text: str) -> List[str]:
        parts = re.split(r"[^A-Za-z0-9]+", text.lower())
        return [p for p in parts if p]

    def _score_concept(self, concept: Dict[str, Any], tokens: Iterable[str], intent: Dict[str, Any]) -> float:
        token_set = set(tokens)
        metrics = {str(m).lower() for m in (intent.get("metrics") or [])}
        entities = {str(e).lower() for e in (intent.get("primary_entities") or [])}
        entity_aliases = {str(e).lower() for e in (intent.get("secondary_entities") or [])}
        keywords = {str(k).lower() for k in (intent.get("keywords_for_discovery") or [])}
        all_entities = entities | entity_aliases | keywords
        score = 0.0
        name = str(concept.get("name") or "").lower()
        if name and name in token_set:
            score += 2.0
        for alias in concept.get("aliases", []) or []:
            alias_l = str(alias).lower()
            if alias_l in token_set:
                score += 1.5
        for keyword in concept.get("keywords", []) or []:
            keyword_l = str(keyword).lower()
            if keyword_l in token_set:
                score += 1.0
        for required_metric in concept.get("required_metrics", []) or []:
            if str(required_metric).lower() in metrics:
                score += 0.8
        for required_entity in concept.get("required_entities", []) or []:
            required = str(required_entity).lower()
            if required in all_entities or required in token_set:
                score += 0.8
        if score <= 0 and (metrics or all_entities):
            intersects = False
            for keyword in concept.get("keywords", []) or []:
                if str(keyword).lower() in all_entities:
                    intersects = True
                    break
            if not intersects:
                for alias in concept.get("aliases", []) or []:
                    if str(alias).lower() in all_entities:
                        intersects = True
                        break
            if intersects:
                score += 0.5
        return score
