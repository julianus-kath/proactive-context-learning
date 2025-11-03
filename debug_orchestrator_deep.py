#!/usr/bin/env python3
"""
🔬 ULTRA-DEEP ORCHESTRATOR DEBUGGER - Complete State Tracing

Shows EVERY step:
- Agent entry/exit with timestamps
- Complete state before/after each node
- Intent field through entire workflow
- Which agents actually run
- Where the workflow stops
- All MCP tool calls
- Internal agent reasoning

This is for fixing Phase 9 integration issues.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional

# Add repo to path
repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root))

from langgraph_integration.orchestrator import QueryOrchestrator
from langgraph_integration.contracts.state import BaseState

# ============= COLORS =============
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

# ============= LOGGING STATE =============
class DebugTracker:
    def __init__(self):
        self.node_sequence = []  # Track which nodes actually ran
        self.state_history = {}  # state key -> list of (timestamp, value, source)
        self.agent_entry_count = 0
        self.agent_exit_count = 0
        self.mcp_calls = []
        
tracker = DebugTracker()

# ============= FORMATTING =============

def ts() -> str:
    """Get current timestamp"""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

def header(title: str, emoji: str = ""):
    """Print section header"""
    line = "═" * 120
    print(f"\n{C.BOLD}{C.CYAN}{line}{C.END}")
    print(f"{C.BOLD}{C.CYAN}{emoji} {title}{C.END}")
    print(f"{C.BOLD}{C.CYAN}{line}{C.END}\n")

def agent_entry(agent: str):
    """Log agent entry"""
    emoji_map = {
        "index_database": "📚",
        "parse_intent": "🧠",
        "route_operation": "🚦",
        "discovery": "🔍",
        "join_sql": "🔗",
        "exec_recovery": "⚡",
        "answer": "📝",
    }
    emoji = emoji_map.get(agent, "⚙️")
    print(f"{C.BOLD}{C.GREEN}[{ts()}] {emoji} ENTERING: {agent.upper()}{C.END}")
    tracker.node_sequence.append(('enter', agent, ts()))
    tracker.agent_entry_count += 1

def agent_exit(agent: str):
    """Log agent exit"""
    print(f"{C.BOLD}{C.GREEN}[{ts()}] ✅ EXITING:  {agent.upper()}{C.END}")
    tracker.node_sequence.append(('exit', agent, ts()))
    tracker.agent_exit_count += 1

def show_state_delta(state: BaseState, source: str):
    """Show what changed in state"""
    print(f"\n{C.BOLD}{C.CYAN}📊 STATE AFTER {source}:{C.END}")
    
    # Key fields to always show
    key_fields = [
        'user_input',
        'intent',
        'relevant_tables',
        'candidate_views',
        'schema_snippet',
        'column_index',
        'view_coverage_analysis',
        'join_plan',
        'generated_sql',
        'query_result',
        'formatted_answer',
        'error_info'
    ]
    
    for field in key_fields:
        if field in state:
            value = state[field]
            
            if field == 'intent':
                print(f"  {C.YELLOW}{field}:{C.END}")
                if isinstance(value, dict) and value:
                    print(f"    operation:              {C.WHITE}{value.get('operation')}{C.END}")
                    print(f"    confidence:             {C.YELLOW}{value.get('confidence', 0):.2f}{C.END}")
                    keywords = value.get('keywords_for_discovery', [])
                    print(f"    keywords_for_discovery: {C.BOLD}{C.WHITE}{keywords}{C.END} ← KEY FOR DISCOVERY!")
                    print(f"    primary_entities:       {C.WHITE}{value.get('primary_entities', [])}{C.END}")
                    print(f"    metrics:                {C.WHITE}{value.get('metrics', [])}{C.END}")
                else:
                    print(f"    {C.RED}[EMPTY/MISSING!]{C.END}")
                    
            elif field == 'relevant_tables':
                tables = value if isinstance(value, list) else []
                print(f"  {C.YELLOW}{field}:{C.END} {C.BOLD}{len(tables)}{C.END} tables")
                for t in tables[:3]:
                    print(f"    - {C.WHITE}{t}{C.END}")
                if len(tables) > 3:
                    print(f"    ... and {len(tables) - 3} more")
                    
            elif field == 'candidate_views':
                views = value if isinstance(value, list) else []
                print(f"  {C.YELLOW}{field}:{C.END} {C.BOLD}{len(views)}{C.END} views")
                for v in views[:2]:
                    name = v.get('name', v.get('full_name', '?'))
                    print(f"    - {C.WHITE}{name}{C.END}")
                    
            elif field == 'schema_snippet':
                if value:
                    lines = str(value).split('\n')
                    print(f"  {C.YELLOW}{field}:{C.END}")
                    for line in lines[:5]:
                        print(f"    {C.GREY}{line}{C.END}")
                    if len(lines) > 5:
                        print(f"    {C.GREY}... ({len(lines) - 5} more lines){C.END}")
                else:
                    print(f"  {C.YELLOW}{field}:{C.END} {C.RED}[EMPTY]{C.END}")
                    
            elif field == 'generated_sql':
                if value:
                    lines = value.strip().split('\n')
                    print(f"  {C.YELLOW}{field}:{C.END}")
                    for line in lines[:3]:
                        print(f"    {C.GREY}{line}{C.END}")
                    if len(lines) > 3:
                        print(f"    {C.GREY}... ({len(lines) - 3} more lines){C.END}")
                        
            elif field == 'error_info':
                if value:
                    print(f"  {C.RED}{field}: {value.get('type', '?')} - {value.get('message', '?')}{C.END}")
                    
            else:
                # Generic display
                val_str = str(value)
                if len(val_str) > 80:
                    val_str = val_str[:77] + "..."
                print(f"  {C.YELLOW}{field}:{C.END} {C.WHITE}{val_str}{C.END}")

def check_critical_issues(state: BaseState, after_node: str):
    """Check for known problems"""
    issues = []
    
    # After parse_intent: intent should be populated
    if after_node == "parse_intent":
        intent = state.get('intent')
        if not intent or not intent.get('keywords_for_discovery'):
            issues.append(f"{C.RED}❌ CRITICAL: Intent not populated or keywords_for_discovery missing!{C.END}")
            print(f"\n{C.BOLD}{C.RED}⚠️  ISSUE DETECTED:{C.END}")
            for issue in issues:
                print(f"  {issue}")
        else:
            keywords = intent.get('keywords_for_discovery')
            print(f"\n{C.BOLD}{C.GREEN}✅ Intent properly populated{C.END}")
            print(f"   Keywords: {C.WHITE}{keywords}{C.END}")
    
    # After discovery: should have relevant_tables
    if after_node == "discovery":
        relevant = state.get('relevant_tables', [])
        if not relevant:
            issues.append(f"{C.RED}❌ CRITICAL: Discovery didn't populate relevant_tables!{C.END}")
        if issues:
            print(f"\n{C.BOLD}{C.RED}⚠️  ISSUE DETECTED:{C.END}")
            for issue in issues:
                print(f"  {issue}")
        else:
            print(f"\n{C.BOLD}{C.GREEN}✅ Discovery found {len(relevant)} tables{C.END}")

async def debug_orchestrator():
    """Run orchestrator with deep tracing"""
    
    header("🔬 ULTRA-DEEP ORCHESTRATOR DEBUG", "🚀")
    print(f"Starting at: {ts()}\n")
    
    # Initialize orchestrator
    print(f"{C.BOLD}{C.BLUE}Initializing QueryOrchestrator...{C.END}")
    orchestrator = QueryOrchestrator()
    print(f"{C.BOLD}{C.GREEN}✅ Orchestrator initialized{C.END}\n")
    
    # Test query
    user_input = "How many customers do we have?"
    print(f"{C.BOLD}Test Query:{C.END} {C.YELLOW}\"{user_input}\"{C.END}\n")
    
    # Create initial state
    initial_state = {
        "user_input": user_input,
        "messages": [],
        "session_id": "debug_session_001",
    }
    
    print(f"{C.BOLD}{C.CYAN}Initial State Keys:{C.END}")
    for k in initial_state.keys():
        print(f"  - {k}")
    print()
    
    # Intercept state updates by using stream
    header("🚀 RUNNING ORCHESTRATOR", "▶️ ")
    
    node_count = 0
    for event in orchestrator.graph.stream(initial_state):
        node_count += 1
        
        if isinstance(event, dict):
            # Event is {node_name: state_dict}
            for node_name, state_value in event.items():
                if node_name == "__end__":
                    continue
                    
                print(f"\n{C.BOLD}{C.CYAN}Node Execution #{node_count}: {node_name}{C.END}")
                print(f"Timestamp: {ts()}\n")
                
                if isinstance(state_value, dict):
                    show_state_delta(state_value, node_name)
                    check_critical_issues(state_value, node_name)
    
    # Final summary
    header("📊 EXECUTION SUMMARY", "📈")
    
    print(f"{C.BOLD}Node Execution Sequence:{C.END}")
    for i, (action, node, ats) in enumerate(tracker.node_sequence, 1):
        emoji = "→" if action == "enter" else "✓"
        symbol = "🚀" if action == "enter" else "✅"
        print(f"  {i}. {symbol} {node:<20} ({ats})")
    
    print(f"\n{C.BOLD}Statistics:{C.END}")
    print(f"  Total nodes executed: {node_count}")
    print(f"  Agents entered: {tracker.agent_entry_count}")
    print(f"  Agents exited: {tracker.agent_exit_count}")
    
    # Check if all expected agents ran
    print(f"\n{C.BOLD}Expected Agents to Run:{C.END}")
    expected = ["index_database", "parse_intent", "route_operation", "discovery", "join_sql", "exec_recovery", "answer"]
    nodes_that_ran = [node for action, node, _ in tracker.node_sequence if action == 'enter']
    
    for agent in expected:
        status = "✅" if agent in nodes_that_ran else "❌"
        print(f"  {status} {agent}")
    
    # If any agents missing
    missing = [a for a in expected if a not in nodes_that_ran]
    if missing:
        print(f"\n{C.RED}{C.BOLD}⚠️  WORKFLOW INCOMPLETE - Missing agents:{C.END}")
        for agent in missing:
            print(f"  ❌ {agent}")
    else:
        print(f"\n{C.GREEN}{C.BOLD}✅ All agents ran successfully!{C.END}")

if __name__ == "__main__":
    try:
        asyncio.run(debug_orchestrator())
    except Exception as e:
        print(f"\n{C.RED}{C.BOLD}❌ ERROR: {e}{C.END}")
        import traceback
        traceback.print_exc()