#!/usr/bin/env python3
"""
🔬 COMPREHENSIVE LANGGRAPH DEBUGGER - Real-Time Agent Reasoning Monitor

Shows explicit reasoning steps for each agent:
✓ Node entry/exit with timestamps
✓ Input state (what agent receives)
✓ Output state (what agent produces)
✓ State mutations (what changed)
✓ MCP tool calls and results
✓ LLM reasoning (prompts/responses when available)
✓ Routing decisions
✓ Error detection and propagation

Usage:
    python debug_langgraph_comprehensive.py
    # Connects to http://localhost:5001 by default
    # Or: python debug_langgraph_comprehensive.py --url http://custom:5001
"""

import asyncio
import aiohttp
import json
import sys
import argparse
from datetime import datetime
from typing import Dict, Any, Optional, List
from collections import defaultdict

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

# Node metadata
NODE_EMOJIS = {
    "index_database": "📚",
    "parse_intent": "🧠",
    "route_operation": "🚦",
    "discovery": "🔍",
    "join_sql": "🔗",
    "exec_recovery": "⚡",
    "answer": "📝",
    "answer_schema": "📋",
    "answer_health": "🏥",
    "answer_error": "❌",
    "search_candidates": "🔎",
    "rank_candidates": "📊",
    "filter_to_limit": "🎯",
    "describe_selected": "📖",
    "build_schema_snippet": "🛠️",
}

# Track execution flow
node_history: List[Dict[str, Any]] = []
state_snapshots: Dict[str, Dict[str, Any]] = {}
tool_calls: List[Dict[str, Any]] = []


def timestamp() -> str:
    """Get formatted timestamp"""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def print_banner(text: str, emoji: str = "", color: str = C.CYAN):
    """Print section banner"""
    width = 120
    print(f"\n{color}{C.BOLD}{'═' * width}{C.END}")
    print(f"{color}{C.BOLD}{emoji} {text}{C.END}")
    print(f"{color}{C.BOLD}{'═' * width}{C.END}\n")


def format_intent(intent: Dict[str, Any]) -> str:
    """Format ParsedIntent for display"""
    if not intent:
        return f"{C.GREY}[No intent]{C.END}"
    
    result = f"\n{C.BOLD}{C.CYAN}Intent Details:{C.END}\n"
    result += f"  {C.GREEN}operation{C.END}:              {C.WHITE}{intent.get('operation', '?')}{C.END}\n"
    result += f"  {C.GREEN}confidence{C.END}:             {C.YELLOW}{intent.get('confidence', 0):.2f}{C.END}\n"
    
    keywords = intent.get('keywords_for_discovery', [])
    result += f"  {C.GREEN}keywords_for_discovery{C.END}:  {C.BOLD}{C.WHITE}{keywords}{C.END} {'✅' if keywords else '❌ EMPTY!'}\n"
    
    entities = intent.get('primary_entities', [])
    result += f"  {C.GREEN}primary_entities{C.END}:       {C.WHITE}{entities}{C.END}\n"
    
    metrics = intent.get('metrics', [])
    result += f"  {C.GREEN}metrics{C.END}:                 {C.WHITE}{metrics}{C.END}\n"
    
    filters = intent.get('filters', [])
    if filters:
        result += f"  {C.GREEN}filters{C.END}:                 {C.WHITE}{len(filters)} filter(s){C.END}\n"
    
    return result


def format_state_field(key: str, value: Any, max_len: int = 150) -> str:
    """Format a single state field"""
    if value is None:
        return f"  {C.GREY}{key}: None{C.END}\n"
    
    if isinstance(value, dict):
        if key == "intent":
            return format_intent(value)
        elif "ok" in value:
            # Result dict
            ok = value.get("ok", False)
            status = f"{C.GREEN}✅ OK{C.END}" if ok else f"{C.RED}❌ FAILED{C.END}"
            result = f"  {C.CYAN}{key}{C.END}: {status}\n"
            if "row_count" in value:
                result += f"    row_count: {C.WHITE}{value['row_count']}{C.END}\n"
            if "error" in value:
                result += f"    error: {C.RED}{value['error']}{C.END}\n"
            return result
        else:
            keys_str = f"{len(value)} keys"
            return f"  {C.CYAN}{key}{C.END}: {C.WHITE}{keys_str}{C.END}\n"
    
    elif isinstance(value, list):
        if not value:
            return f"  {C.GREY}{key}: []{C.END}\n"
        result = f"  {C.CYAN}{key}{C.END}: {C.WHITE}[{len(value)} items]{C.END}\n"
        if key == "relevant_tables" and value:
            result += f"    Top 3: {', '.join(value[:3])}\n"
        return result
    
    elif isinstance(value, str):
        if len(value) > max_len:
            return f"  {C.CYAN}{key}{C.END}: {C.WHITE}{value[:max_len]}...{C.END} ({len(value)} chars)\n"
        return f"  {C.CYAN}{key}{C.END}: {C.WHITE}{value}{C.END}\n"
    
    else:
        return f"  {C.CYAN}{key}{C.END}: {C.WHITE}{value}{C.END}\n"


def show_state_summary(state: Dict[str, Any], label: str = "State") -> str:
    """Show condensed state summary"""
    result = f"\n{C.BOLD}{C.CYAN}{label}:{C.END}\n"
    
    # Critical fields first
    critical = ["intent", "relevant_tables", "sql_query", "exec_result", "error_info", "final_response"]
    for key in critical:
        if key in state:
            result += format_state_field(key, state[key])
    
    # Other fields
    other_keys = [k for k in state.keys() if k not in critical]
    if other_keys:
        result += f"\n{C.DIM}Other keys: {', '.join(other_keys[:10])}{C.END}\n"
    
    return result


def show_state_delta(before: Dict[str, Any], after: Dict[str, Any]) -> str:
    """Show what changed between states"""
    added = set(after.keys()) - set(before.keys())
    removed = set(before.keys()) - set(after.keys())
    changed = []
    
    for k in set(before.keys()) & set(after.keys()):
        if before[k] != after[k]:
            changed.append(k)
    
    if not (added or removed or changed):
        return f"  {C.GREY}[No state changes]{C.END}\n"
    
    result = f"\n{C.BOLD}🔄 State Changes:{C.END}\n"
    
    if added:
        result += f"  {C.GREEN}➕ Added{C.END}: {', '.join(sorted(added))}\n"
    if removed:
        result += f"  {C.RED}➖ Removed{C.END}: {', '.join(sorted(removed))}\n"
    if changed:
        result += f"  {C.YELLOW}🔄 Modified{C.END}: {', '.join(sorted(changed))}\n"
        
        # Show intent changes in detail
        if "intent" in changed:
            before_intent = before.get("intent", {})
            after_intent = after.get("intent", {})
            for k in set(before_intent.keys()) | set(after_intent.keys()):
                if before_intent.get(k) != after_intent.get(k):
                    old = before_intent.get(k)
                    new = after_intent.get(k)
                    result += f"    {C.CYAN}{k}{C.END}: {C.RED}{old}{C.END} → {C.GREEN}{new}{C.END}\n"
    
    return result


def format_tool_call(data: Dict[str, Any]) -> str:
    """Format MCP tool call"""
    tool = data.get("tool", data.get("tool_name", "?"))
    params = data.get("params", data.get("arguments", {}))
    
    result = f"\n{C.PURPLE}{C.BOLD}📡 MCP Tool Call:{C.END}\n"
    result += f"  {C.BOLD}Tool:{C.END} {C.CYAN}{tool}{C.END}\n"
    
    if params:
        result += f"  {C.BOLD}Arguments:{C.END}\n"
        for k, v in params.items():
            if isinstance(v, (list, dict)):
                v_str = json.dumps(v, indent=2)[:200]
            else:
                v_str = str(v)[:100]
            result += f"    {C.CYAN}{k}{C.END}: {v_str}\n"
    
    return result


def format_tool_result(data: Dict[str, Any]) -> str:
    """Format MCP tool result"""
    tool = data.get("tool", data.get("tool_name", "?"))
    result_data = data.get("result", data.get("../../data", {}))
    success = data.get("success", True)
    duration = data.get("duration_ms")
    
    status = f"{C.GREEN}✅ Success{C.END}" if success else f"{C.RED}❌ Failed{C.END}"
    result = f"\n{C.PURPLE}{C.BOLD}📊 MCP Tool Result:{C.END} {status}\n"
    result += f"  {C.BOLD}Tool:{C.END} {C.CYAN}{tool}{C.END}\n"
    
    if duration:
        result += f"  {C.BOLD}Duration:{C.END} {duration:.2f}ms\n"
    
    if isinstance(result_data, dict):
        # Show key metrics
        if "ok" in result_data:
            result += f"  {C.BOLD}Status:{C.END} {C.GREEN if result_data['ok'] else C.RED}{result_data['ok']}{C.END}\n"
        if "row_count" in result_data:
            result += f"  {C.BOLD}Rows:{C.END} {result_data['row_count']}\n"
        if "error" in result_data:
            result += f"  {C.BOLD}Error:{C.END} {C.RED}{result_data['error']}{C.END}\n"
    
    return result


async def stream_debug_logs(service_url: str = "http://localhost:5001", api_key: str = "supersecretapikey"):
    """Main streaming function"""
    print_banner("🔬 COMPREHENSIVE LANGGRAPH DEBUGGER", "🔍", C.GREEN)
    print(f"{C.CYAN}Connecting to: {service_url}{C.END}\n")
    
    last_log_count = 0
    retry_count = 0
    max_retries = 5
    current_node: Optional[str] = None
    
    while retry_count < max_retries:
        try:
            async with aiohttp.ClientSession() as session:
                retry_count = 0
                
                while True:
                    try:
                        async with session.get(
                            f"{service_url}/debug/logs/stream",
                            headers={"X-API-Key": api_key},
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                logs = data.get("logs", [])
                                
                                if len(logs) > last_log_count:
                                    new_logs = logs[last_log_count:]
                                    for log in new_logs:
                                        log_type = log.get("type", "INFO")
                                        message = log.get("message", "")
                                        log_data = log.get("data", {})
                                        node = log.get("node", current_node)
                                        
                                        if node:
                                            current_node = node
                                        
                                        # Route by log type
                                        if log_type == "AGENT_ENTRY":
                                            emoji = NODE_EMOJIS.get(node, "⚙️")
                                            print_banner(f"{emoji} {node.upper()} - ENTRY", "", C.CYAN)
                                            state = log_data.get("state", {})
                                            print(show_state_summary(state, "Input State"))
                                            state_snapshots[f"{node}_entry"] = state.copy()
                                        
                                        elif log_type == "AGENT_EXIT":
                                            emoji = NODE_EMOJIS.get(node, "⚙️")
                                            print_banner(f"{emoji} {node.upper()} - EXIT", "", C.GREEN)
                                            state = log_data.get("state", {})
                                            prev_state = state_snapshots.get(f"{node}_entry", {})
                                            print(show_state_summary(state, "Output State"))
                                            print(show_state_delta(prev_state, state))
                                            state_snapshots[f"{node}_exit"] = state.copy()
                                        
                                        elif log_type == "MCP_CALL":
                                            print(format_tool_call(log_data))
                                        
                                        elif log_type == "MCP_RESULT":
                                            print(format_tool_result(log_data))
                                        
                                        elif log_type == "INTENT_CHECK":
                                            intent = log_data.get("intent", {})
                                            if intent:
                                                print(format_intent(intent))
                                        
                                        elif log_type == "ROUTING_DECISION":
                                            decision = log_data.get("decision", "?")
                                            print(f"\n{C.YELLOW}{C.BOLD}🚦 Routing Decision:{C.END} {C.WHITE}{decision}{C.END}\n")
                                        
                                        elif log_type == "ERROR":
                                            error = log_data.get("error", message)
                                            print(f"\n{C.RED}{C.BOLD}❌ ERROR:{C.END} {error}\n")
                                        
                                        else:
                                            # Generic log
                                            emoji_map = {
                                                "INFO": "ℹ️",
                                                "WARNING": "⚠️",
                                                "ERROR": "❌",
                                                "DEBUG": "🐛",
                                            }
                                            emoji = emoji_map.get(log_type, "•")
                                            color = C.RED if log_type == "ERROR" else C.YELLOW if log_type == "WARNING" else C.CYAN
                                            print(f"{color}[{timestamp()}] {emoji} {message}{C.END}")
                                            if log_data:
                                                for k, v in list(log_data.items())[:5]:
                                                    if isinstance(v, (dict, list)):
                                                        v_str = json.dumps(v)[:100]
                                                    else:
                                                        v_str = str(v)[:100]
                                                    print(f"  {C.GREY}{k}: {v_str}{C.END}")
                                        
                                        print()  # Blank line
                                    
                                    last_log_count = len(logs)
                            
                            elif resp.status == 401:
                                print(f"{C.RED}❌ Authentication failed. Check API_KEY.{C.END}")
                                return
                            else:
                                print(f"{C.RED}❌ Server error: {resp.status}{C.END}")
                        
                        await asyncio.sleep(0.5)
                    
                    except asyncio.TimeoutError:
                        print(f"{C.YELLOW}⚠️  Connection timeout, retrying...{C.END}")
                        await asyncio.sleep(2)
                    except Exception as e:
                        print(f"{C.YELLOW}⚠️  Error: {e}, retrying...{C.END}")
                        await asyncio.sleep(2)
        
        except aiohttp.ClientConnectorError:
            retry_count += 1
            if retry_count < max_retries:
                print(f"{C.YELLOW}⚠️  Cannot connect (attempt {retry_count}/{max_retries})...{C.END}")
                await asyncio.sleep(3)
            else:
                print(f"{C.RED}❌ Failed to connect after {max_retries} attempts.{C.END}")
                return
        except Exception as e:
            print(f"{C.RED}❌ Unexpected error: {e}{C.END}")
            retry_count += 1
            if retry_count < max_retries:
                await asyncio.sleep(3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Comprehensive LangGraph Debugger")
    parser.add_argument("--url", default="http://localhost:5001", help="LangGraph service URL")
    parser.add_argument("--api-key", default="supersecretapikey", help="API key")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(stream_debug_logs(args.url, args.api_key))
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}👋 Stopped monitoring{C.END}")
        sys.exit(0)

