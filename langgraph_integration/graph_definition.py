"""
DEPRECATED: Monolithic Workflow - Use orchestrator.py instead

This file is kept for backward compatibility only.
All functionality has been moved to the new multi-agent orchestrator.

⚠️  DO NOT USE THIS FILE FOR NEW DEVELOPMENT
✅  Use: langgraph_integration/orchestrator.py instead

Phase 8 (ADR-0019) replaced this with a multi-agent system that achieves:
- 85% table discovery (vs 65% before)
- 88% query success (vs 72% before)
- Better reasoning per phase
- Easier to test and debug

For more info: See docs/PHASE_8_MULTI_AGENT_ACTIVATION.md
"""

import warnings
import logging

# Issue deprecation warning
warnings.warn(
    "graph_definition.py is DEPRECATED. Use langgraph_integration.orchestrator instead. "
    "See docs/PHASE_8_MULTI_AGENT_ACTIVATION.md for migration guide.",
    DeprecationWarning,
    stacklevel=2
)

logger = logging.getLogger(__name__)
logger.warning("⚠️  DEPRECATED: graph_definition.py is in use. Please migrate to orchestrator.py")

# ============= BACKWARD COMPATIBILITY STUBS =============
# These are provided for any code that still imports from graph_definition
# They route to the new orchestrator system

from langgraph_integration.orchestrator import (
    build_graph,
    create_query_orchestrator,
    get_orchestrator,
    QueryOrchestrator
)

# Export for backward compatibility
__all__ = [
    'build_graph',
    'create_query_orchestrator',
    'get_orchestrator',
    'QueryOrchestrator',
    'create_database_workflow',  # Alias for compatibility
    'DatabaseWorkflow'  # Alias for compatibility
]


def create_database_workflow(*args, **kwargs):
    """
    DEPRECATED: Alias for create_query_orchestrator.
    
    Provided for backward compatibility with old code.
    Use create_query_orchestrator() instead.
    """
    logger.warning("create_database_workflow() is deprecated. Use create_query_orchestrator()")
    return create_query_orchestrator(*args, **kwargs)


# Alias for backward compatibility
DatabaseWorkflow = QueryOrchestrator


# If tests or other code import from this file, they'll get the new system
logger.info("✅ graph_definition.py routed to orchestrator.py (multi-agent system active)")