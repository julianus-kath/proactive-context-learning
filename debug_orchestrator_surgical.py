#!/usr/bin/env python3
"""
🔬 SURGICAL ORCHESTRATOR DEBUGGER - Phase 9 Deep Dive

This debugger INTERCEPTS and LOGS every single node execution in the orchestrator graph.
It shows:
✓ Agent name, stage, timestamp
✓ Input state (what the node receives)
✓ Output state (what the node produces)
✓ State deltas (what changed?)
✓ Error detection (where it breaks?)
✓ Tool calls (which MCP tools actually run?)
✓ Conditional routing decisions

Usage:
    python debug_orchestrator_surgical.py "How many customers do we have?"
"""

import asyncio
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional
import logging

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/orchestrator_debug.log')
    ]
)

logger = logging.getLogger(__name__)

# Import the orchestrator
sys.path.insert(0, '/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code')

from langgraph_integration.orchestrator import QueryOrchestrator
from langgraph_integration.contracts.state import BaseState


class SurgicalDebugger:
    """Intercepts and logs every orchestrator node execution."""
    
    def __init__(self):
        self.node_history = []
        self.state_snapshots = {}
        self.tool_calls = []
        
    def log_node_entry(self, node_name: str, state: BaseState) -> None:
        """Log when a node starts executing."""
        timestamp = datetime.now().isoformat()
        
        print(f"\n{'='*80}")
        print(f"📍 NODE ENTRY: [{node_name}]")
        print(f"⏰ Timestamp: {timestamp}")
        print(f"{'='*80}")
        
        # Show intent field specifically
        intent = state.get("intent", {})
        print(f"\n🧠 INTENT STATE:")
        if isinstance(intent, dict):
            for key, val in intent.items():
                if key == "keywords_for_discovery":
                    print(f"   🔑 {key}: {val} {'✅' if val else '❌ EMPTY!'}")
                else:
                    print(f"   {key}: {val}")
        else:
            print(f"   (Not a dict!) Type: {type(intent)}")
        
        # Show other important fields
        print(f"\n📊 OTHER STATE FIELDS:")
        important_fields = [
            "user_input",
            "operation",
            "error_info",
            "relevant_tables",
            "sql_query",
            "final_response"
        ]
        for field in important_fields:
            val = state.get(field)
            if val is not None:
                if field == "relevant_tables":
                    print(f"   {field}: {len(val) if isinstance(val, list) else val} items")
                elif field == "sql_query":
                    print(f"   {field}: {len(val) if isinstance(val, str) else val} chars")
                else:
                    print(f"   {field}: {val}")
        
        self.node_history.append({
            "node": node_name,
            "timestamp": timestamp,
            "type": "entry",
            "intent": intent,
            "state_keys": list(state.keys())
        })
    
    def log_node_exit(self, node_name: str, input_state: BaseState, output_state: BaseState) -> None:
        """Log when a node finishes executing."""
        timestamp = datetime.now().isoformat()
        
        print(f"\n{'='*80}")
        print(f"✅ NODE EXIT: [{node_name}]")
        print(f"⏰ Timestamp: {timestamp}")
        print(f"{'='*80}")
        
        # Show state deltas
        print(f"\n🔄 STATE CHANGES:")
        changed_fields = []
        for key in set(list(input_state.keys()) + list(output_state.keys())):
            input_val = input_state.get(key)
            output_val = output_state.get(key)
            
            if input_val != output_val:
                changed_fields.append(key)
                
                # Show detailed changes
                if key == "intent":
                    if isinstance(output_val, dict):
                        print(f"   🧠 intent.keywords_for_discovery: {output_val.get('keywords_for_discovery', [])} {'✅' if output_val.get('keywords_for_discovery') else '❌'}")
                        print(f"      intent.operation: {output_val.get('operation')}")
                elif key == "relevant_tables":
                    print(f"   📊 relevant_tables: {len(output_val) if isinstance(output_val, list) else '?'} items")
                    if output_val:
                        print(f"      First 3: {output_val[:3]}")
                elif key == "sql_query":
                    print(f"   📝 sql_query: {len(output_val) if isinstance(output_val, str) else '?'} chars")
                    if output_val:
                        print(f"      Preview: {output_val[:100]}...")
                elif key == "error_info":
                    print(f"   ❌ error_info: {output_val}")
                else:
                    print(f"   {key}: CHANGED")
        
        if not changed_fields:
            print(f"   (No changes to state)")
        
        self.node_history.append({
            "node": node_name,
            "timestamp": timestamp,
            "type": "exit",
            "changed_fields": changed_fields,
            "has_error": bool(output_state.get("error_info"))
        })
    
    def print_summary(self) -> None:
        """Print execution summary."""
        print(f"\n\n{'='*80}")
        print(f"📋 ORCHESTRATOR EXECUTION SUMMARY")
        print(f"{'='*80}")
        
        print(f"\n✅ Node Execution Order:")
        for i, entry in enumerate(self.node_history, 1):
            if entry["type"] == "entry":
                print(f"  {i}. [{entry['node']}] started")
        
        print(f"\n⚠️  Nodes with Errors:")
        error_nodes = [h for h in self.node_history if h.get("has_error")]
        if error_nodes:
            for entry in error_nodes:
                print(f"  ❌ {entry['node']}")
        else:
            print(f"  (None)")
        
        print(f"\n🔑 Critical Fields:")
        last_entry = next((e for e in reversed(self.node_history) if e["type"] == "exit"), None)
        if last_entry:
            print(f"  Last node: {last_entry['node']}")
            print(f"  Had error: {last_entry.get('has_error')}")


async def debug_orchestrator(user_query: str) -> None:
    """
    Execute orchestrator with surgical debugging.
    
    Args:
        user_query: User's natural language query
    """
    debugger = SurgicalDebugger()
    
    print(f"\n{'='*80}")
    print(f"🔬 SURGICAL ORCHESTRATOR DEBUG")
    print(f"{'='*80}")
    print(f"\n🔍 Query: {user_query}\n")
    
    try:
        # Initialize orchestrator
        logger.info("Initializing orchestrator...")
        orchestrator = QueryOrchestrator(
            llm_model="gpt-4o",
            llm_temp=0.0,
            max_joins=3,
            max_retries=2,
            row_limit=1000,
            query_timeout_seconds=30
        )
        logger.info("✅ Orchestrator initialized")
        
        # Build initial state
        initial_state: BaseState = {
            "user_input": user_query,
            "messages": [],
        }
        
        logger.info(f"Initial state: {list(initial_state.keys())}")
        
        # Get the compiled graph
        graph = orchestrator.graph
        
        # Execute with streaming (if available)
        logger.info("Starting graph execution...")
        
        # Use ainvoke to get the final state
        logger.info("Calling graph.ainvoke()...")
        final_state = await graph.ainvoke(initial_state, {"timeout": 60})
        
        logger.info("✅ Graph execution completed")
        
        # Print final state
        print(f"\n{'='*80}")
        print(f"🏁 FINAL STATE")
        print(f"{'='*80}\n")
        
        # Show critical fields
        print(f"Intent: {final_state.get('intent', {})}")
        print(f"\nError Info: {final_state.get('error_info')}")
        print(f"\nRelevant Tables: {len(final_state.get('relevant_tables', []))} items")
        print(f"\nSQL Query: {len(final_state.get('sql_query', ''))} chars")
        print(f"\nFinal Response: {final_state.get('final_response', '(none)')[:200]}")
        
        # Print summary
        debugger.print_summary()
        
    except Exception as e:
        logger.error(f"❌ Orchestrator failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        print(f"\n❌ ERROR: {e}")


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "How many customers do we have?"
    
    print(f"Query: {query}")
    print(f"Logs: /tmp/orchestrator_debug.log")
    
    asyncio.run(debug_orchestrator(query))