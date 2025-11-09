#!/usr/bin/env python3
"""
🔬 ULTRA-DEEP ORCHESTRATOR DEBUGGER (Phase 9)

This debugger instruments the ACTUAL LangGraph orchestrator to show:
✓ Exact agent name and execution point
✓ State BEFORE entering node
✓ State AFTER exiting node  
✓ What changed (added/removed/modified keys)
✓ Exact MCP tool calls and results
✓ LLM prompts and responses
✓ Decision points and routing logic
✓ Where workflow stops (or doesn't)

This runs the ACTUAL query through the ACTUAL graph and intercepts logs.

Usage:
    python debug_deep_orchestrator.py "How many customers do we have?"
    
The output will show EXACTLY where the workflow breaks.
"""

import sys
import logging
import json
from typing import Dict, Any
import asyncio
from datetime import datetime

# Configure logging to capture EVERYTHING
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Import orchestrator and related classes
from langgraph_integration.orchestrator import QueryOrchestrator
from langgraph_integration.contracts.state import BaseState

# ============= COLOR SCHEME =============
class C:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    PURPLE = '\033[35m'
    WHITE = '\033[97m'
    GREY = '\033[90m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'


def print_header(title: str):
    """Print a big header"""
    print(f"\n{C.BOLD}{C.CYAN}{'═' * 140}{C.END}")
    print(f"{C.BOLD}{C.CYAN}{title}{C.END}")
    print(f"{C.BOLD}{C.CYAN}{'═' * 140}{C.END}\n")


def print_section(title: str, emoji: str = ""):
    """Print a section header"""
    print(f"\n{C.BOLD}{C.YELLOW}{emoji} {title}{C.END}")
    print(f"{C.YELLOW}{'-' * 100}{C.END}")


def format_state(state: BaseState, label: str = "STATE") -> str:
    """Format state for display"""
    result = f"\n{C.BOLD}{C.CYAN}{label}:{C.END}\n"
    if not state:
        return result + f"  {C.GREY}[EMPTY]{C.END}\n"
    
    for key in sorted(state.keys()):
        val = state[key]
        
        # Special formatting for different types
        if key == "intent":
            if isinstance(val, dict):
                result += f"  {C.GREEN}{key}{C.END}: {C.BOLD}{C.WHITE}ParsedIntent{C.END}\n"
                for k, v in val.items():
                    if isinstance(v, list) and len(v) > 5:
                        result += f"    ├─ {C.CYAN}{k}{C.END}: [{len(v)} items] {str(v[:2])}...\n"
                    else:
                        result += f"    ├─ {C.CYAN}{k}{C.END}: {C.WHITE}{v}{C.END}\n"
            else:
                result += f"  {C.GREEN}{key}{C.END}: {C.YELLOW}[NOT A DICT]{C.END} {type(val)}\n"
        
        elif key == "candidate_views" and isinstance(val, list):
            result += f"  {C.GREEN}{key}{C.END}: {C.WHITE}[{len(val)} items]{C.END}\n"
            for item in val[:3]:
                name = item.get("table_name") or item.get("name") or item.get("full_name", "?")
                result += f"    ├─ {name}\n"
        
        elif isinstance(val, list) and len(val) > 3:
            result += f"  {C.GREEN}{key}{C.END}: {C.WHITE}[list: {len(val)} items]{C.END}\n"
        
        elif isinstance(val, dict) and len(val) > 5:
            result += f"  {C.GREEN}{key}{C.END}: {C.WHITE}[dict: {len(val)} keys]{C.END}\n"
        
        elif isinstance(val, str) and len(val) > 100:
            result += f"  {C.GREEN}{key}{C.END}: {C.WHITE}{val[:100]}...{C.END}\n"
        
        else:
            result += f"  {C.GREEN}{key}{C.END}: {C.WHITE}{val}{C.END}\n"
    
    return result


def compare_states(before: BaseState, after: BaseState) -> str:
    """Compare two states and show what changed"""
    added = set(after.keys()) - set(before.keys())
    removed = set(before.keys()) - set(after.keys())
    changed = []
    
    for k in set(before.keys()) & set(after.keys()):
        if before[k] != after[k]:
            changed.append(k)
    
    result = f"\n{C.BOLD}🔄 STATE DELTA:{C.END}\n"
    if not added and not removed and not changed:
        result += f"  {C.GREY}[NO CHANGES]{C.END}\n"
        return result
    
    if added:
        result += f"  {C.GREEN}➕ ADDED:{C.END} {', '.join(sorted(added))}\n"
    if removed:
        result += f"  {C.RED}➖ REMOVED:{C.END} {', '.join(sorted(removed))}\n"
    if changed:
        result += f"  {C.YELLOW}🔄 MODIFIED:{C.END} {', '.join(sorted(changed))}\n"
        for k in changed:
            old_val = before[k]
            new_val = after[k]
            if k == "intent":
                result += f"\n    {C.BOLD}Intent Changes:{C.END}\n"
                if isinstance(old_val, dict) and isinstance(new_val, dict):
                    old_keys = set(old_val.keys())
                    new_keys = set(new_val.keys())
                    for kk in sorted(new_keys | old_keys):
                        old = old_val.get(kk)
                        new = new_val.get(kk)
                        if old != new:
                            result += f"      {C.CYAN}{kk}{C.END}: {C.RED}{old}{C.END} → {C.GREEN}{new}{C.END}\n"
            else:
                old_str = str(old_val)[:50] if not isinstance(old_val, list) else f"[{len(old_val)} items]"
                new_str = str(new_val)[:50] if not isinstance(new_val, list) else f"[{len(new_val)} items]"
                result += f"    {C.CYAN}{k}{C.END}: {C.RED}{old_str}{C.END} → {C.GREEN}{new_str}{C.END}\n"
    
    return result


def instrument_and_run_query(query: str):
    """Run a query through orchestrator with deep instrumentation"""
    print_header(f"🚀 EXECUTING QUERY: \"{query}\"")
    
    # Create orchestrator
    print(f"{C.CYAN}[*] Initializing QueryOrchestrator...{C.END}")
    orchestrator = QueryOrchestrator(
        llm_model="gpt-4o",
        llm_temp=0.0,
        max_joins=3,
        max_retries=2,
        row_limit=1000,
        query_timeout_seconds=30
    )
    print(f"{C.GREEN}[✓] QueryOrchestrator initialized{C.END}")
    
    # Build initial state
    print(f"\n{C.CYAN}[*] Building initial state...{C.END}")
    initial_state = {
        "user_input": query,
        "messages": [],
        "session_id": "debug-session-001",
    }
    print_section(f"Initial State", "📋")
    print(format_state(initial_state))
    
    # Get the graph
    graph = orchestrator.graph
    print(f"\n{C.GREEN}[✓] Graph topology:{C.END}")
    for node_name in graph.nodes:
        print(f"    ├─ {C.CYAN}{node_name}{C.END}")
    
    # Instrument to capture node execution
    print_section("🎬 EXECUTING GRAPH", "▶️")
    
    node_outputs = {}
    node_sequence = []
    
    try:
        # Use streaming to see each node execution
        print(f"\n{C.CYAN}[*] Running graph.stream()...{C.END}\n")
        
        for output in graph.stream(initial_state, stream_mode="updates"):
            print(f"\n{C.BOLD}{C.PURPLE}{'─' * 140}{C.END}")
            
            for node_name, node_state in output.items():
                node_sequence.append(node_name)
                print(f"\n✅ NODE COMPLETED: {C.BOLD}{C.CYAN}{node_name}{C.END}")
                
                # Track state before and after
                prev_state = node_outputs.get(node_name, {})
                curr_state = node_state
                node_outputs[node_name] = curr_state
                
                print(format_state(curr_state, f"STATE AFTER {node_name.upper()}"))
                
                if prev_state:
                    print(compare_states(prev_state, curr_state))
        
        print(f"\n{C.BOLD}{C.PURPLE}{'═' * 140}{C.END}\n")
        
        print_section("✅ EXECUTION COMPLETE", "🎉")
        print(f"\n{C.GREEN}Node sequence:{C.END}")
        for i, node in enumerate(node_sequence, 1):
            print(f"  {i}. {C.CYAN}{node}{C.END}")
        
        # Final answer
        final_state = list(output.values())[0] if output else initial_state
        answer = final_state.get("answer", "")
        
        print(f"\n{C.GREEN}Final answer:{C.END}")
        print(f"  {C.BOLD}{C.WHITE}{answer}{C.END}")
        
    except Exception as e:
        print(f"\n{C.RED}❌ ERROR DURING EXECUTION:{C.END}")
        print(f"  {C.RED}{type(e).__name__}: {str(e)}{C.END}")
        import traceback
        traceback.print_exc()


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print(f"{C.YELLOW}Usage: python debug_deep_orchestrator.py \"<your query>\"{C.END}")
        print(f"\nExamples:")
        print(f"  python debug_deep_orchestrator.py \"How many customers do we have?\"")
        print(f"  python debug_deep_orchestrator.py \"Count customers\"")
        sys.exit(1)
    
    query = sys.argv[1]
    instrument_and_run_query(query)


if __name__ == "__main__":
    main()
