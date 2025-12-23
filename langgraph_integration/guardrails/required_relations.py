from typing import Any, Dict, List, Optional, Set

from langgraph_integration.contracts.state import BaseState


def _to_lower_set(values: List[str]) -> Set[str]:
    return {str(v).lower() for v in values if v}


def evaluate_required_relations(state: BaseState) -> Optional[Dict[str, Any]]:
    """
    Orchestrator-level guardrail for enforcing required physical tables.

    Current, minimal implementation:
    - Uses KPI-derived `required_tables_from_kpi` as the requirement source.
    - Compares against validator-derived `validator_tables_used` /
      `validator_tables_used_base` (canonical and base names).
    - On first violation, marks missing tables as forced and requests a replan.
    - On subsequent violations with the same missing set, stops replanning and
      surfaces a targeted diagnostic without further loops.

    This is intentionally generic and does NOT hard-code domain terms like
    "products"; it simply enforces that required tables appear in the final SQL.
    """
    required = state.get("required_tables_from_kpi") or []
    if not required:
        return None

    used_canonical = state.get("validator_tables_used") or []
    used_base = state.get("validator_tables_used_base") or []

    # If we don't have validator metadata yet, do not enforce.
    if not used_canonical and not used_base:
        return None

    used_canon_l = _to_lower_set(used_canonical)
    used_base_l = _to_lower_set(used_base)

    missing: List[str] = []
    for req in required:
        req_str = str(req)
        req_canon = req_str.lower()
        req_base = req_str.split(".")[-1].lower()
        if (req_canon not in used_canon_l) and (req_base not in used_base_l):
            missing.append(req_str)

    if not missing:
        return None

    # Loop control: first violation → allow one replan with forced_tables.
    # Subsequent violations with same missing set → stop replanning.
    attempts = state.get("required_enforcement_attempts", 0) or 0
    previous_missing = set(state.get("last_required_missing_tables", []) or [])
    current_missing_set = set(missing)

    replan_needed = False
    final_stop = False

    if attempts == 0 or previous_missing != current_missing_set:
        # First time (or different missing set): request replan and force tables.
        replan_needed = True
        state["required_enforcement_attempts"] = attempts + 1
        state["last_required_missing_tables"] = list(current_missing_set)

        forced = set(state.get("forced_tables", []) or [])
        forced.update(current_missing_set)
        state["forced_tables"] = list(forced)
    else:
        # Same missing set seen again → stop replanning to avoid thrash.
        final_stop = True
        state["required_enforcement_attempts"] = attempts + 1

    message_parts = [
        "Final SQL is missing required tables implied by KPI expressions.",
        f"Missing tables: {', '.join(sorted(current_missing_set))}.",
    ]
    if replan_needed:
        message_parts.append("Will attempt one more planning pass with these tables forced into discovery/join.")
    if final_stop:
        message_parts.append("Repeated failures with the same missing tables; stopping replanning to avoid loops.")

    error: Dict[str, Any] = {
        "type": "REQUIRED_TABLE_MISSING_IN_SQL",
        "message": " ".join(message_parts),
        "missing_required_tables": sorted(current_missing_set),
        "tables_used": used_canonical or used_base,
        "replan_needed": replan_needed,
        "validation_stage": "required_relations_guardrail",
    }

    return error

