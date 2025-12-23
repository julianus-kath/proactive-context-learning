"""
Guardrail utilities for orchestrator-level validation and routing decisions.

These helpers operate on canonicalized metadata (e.g., validator_tables_used)
and structured hints (e.g., required_tables_from_kpi) to decide whether a
query should be replanned, forced toward specific tables, or failed early with
targeted diagnostics.
"""

