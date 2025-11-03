#!/usr/bin/env python3
"""
🔬 DEEP WORKFLOW DEBUGGER - Phase 9 Intent Parser Investigation

Real-time debug monitor that PAINFULLY SHOWS:
✓ Exact agent name and execution stage
✓ Input state (what agent receives)
✓ Output state (what agent produces)
✓ State mutations (what changed?)
✓ Intent field tracking (is it being passed correctly?)
✓ MCP tool calls (which discovery tools are actually used?)
✓ Internal reasoning steps (LLM prompts, decisions, etc.)
✓ State isolation issues (are agents seeing each other's data?)

This debugger exposes Phase 9 intent parser integration issues
by showing the complete flow through the multi-agent orchestrator.

Usage:
    python debug_stream_v2.py
    # Will connect to http://localhost:5001 by default
    # Or: python debug_stream_v2.py --url http://custom:5001 --api-key key
"""

import asyncio
import aiohttp
import json
import sys
import argparse
from datetime import datetime
from typing import Dict, Any, Optional
import textwrap

# ============= COLOR SCHEME =============
class C:
    """Color constants for terminal output"""
    # Colors
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    PURPLE = '\033[35m'
    WHITE = '\033[97m'
    GREY = '\033[90m'
    
    # Emphasis
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'

# Track state
node_colors = {}
node_activity_count = {}
prev_state = {}


def stamp(msg: str, emoji: str = "•", color: str = C.CYAN) -> str:
    """Create a timestamped log line"""
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    return f"{color}{emoji} [{ts}] {msg}{C.END}"


def agent_header(agent: str, stage: str = "ENTRY") -> str:
    """Create agent execution header"""
    emoji_map = {
        "index_database": "📚",
        "parse_intent": "🧠",
        "route_operation": "🚦",
        "discovery": "🔍",
        "join_sql": "🔗",
        "exec_recovery": "⚡",
        "answer": "📝",
        "search_candidates": "🔎",
        "describe_selected": "📊",
    }
    
    emoji = emoji_map.get(agent, "⚙️")
    stage_emoji = "🔄" if stage == "PROCESSING" else "✅" if stage == "EXIT" else "🚀"
    
    header = f"\n{C.BOLD}{C.CYAN}{'═' * 120}{C.END}"
    header += f"\n{C.BOLD}{C.CYAN}{emoji} AGENT: {agent.upper():<25} | {stage_emoji} {stage}{C.END}"
    header += f"\n{C.BOLD}{C.CYAN}{'═' * 120}{C.END}"
    
    return header


def show_intent(intent: Dict[str, Any], label: str = "Intent") -> str:
    """Format ParsedIntent for display"""
    if not intent:
        return f"{C.GREY}[No intent]{C.END}"
    
    operation = intent.get("operation", "?")
    keywords = intent.get("keywords_for_discovery", [])
    confidence = intent.get("confidence", 0)
    entities = intent.get("primary_entities", [])
    metrics = intent.get("metrics", [])
    
    result = f"{C.BOLD}{C.CYAN}{label}:{C.END}\n"
    result += f"  {C.GREEN}operation{C.END}:                 {C.WHITE}{operation}{C.END}\n"
    result += f"  {C.GREEN}confidence{C.END}:                {C.YELLOW}{confidence:.2f}{C.END}\n"
    result += f"  {C.GREEN}primary_entities{C.END}:          {C.WHITE}{entities}{C.END}\n"
    result += f"  {C.GREEN}keywords_for_discovery{C.END}:    {C.BOLD}{C.WHITE}{keywords}{C.END}\n"
    result += f"  {C.GREEN}metrics{C.END}:                    {C.WHITE}{metrics}{C.END}\n"
    
    return result


def show_mcp_call(data: Dict[str, Any]) -> str:
    """Show MCP tool invocation"""
    tool = data.get("tool", "?")
    params = data.get("params", {})
    
    result = f"\n{C.PURPLE}📡 MCP TOOL CALL{C.END}\n"
    result += f"  {C.BOLD}Tool:{C.END} {tool}\n"
    result += f"  {C.BOLD}Params:{C.END}\n"
    for k, v in params.items():
        if isinstance(v, (list, dict)):
            v_str = json.dumps(v)[:100]
        else:
            v_str = str(v)[:100]
        result += f"    {C.CYAN}{k}{C.END}: {v_str}\n"
    
    return result


def show_mcp_result(data: Dict[str, Any]) -> str:
    """Show MCP tool result"""
    tool = data.get("tool", "?")
    result_data = data.get("result", {})
    
    result = f"\n{C.PURPLE}📊 MCP RESULT{C.END}\n"
    result += f"  {C.BOLD}Tool:{C.END} {tool}\n"
    
    if isinstance(result_data, dict):
        for k, v in result_data.items():
            if k in ["ok", "error"]:
                v_str = str(v)
            elif isinstance(v, list):
                v_str = f"[{len(v)} items]"
            elif isinstance(v, dict):
                v_str = f"{{...{len(v)} keys}}"
            else:
                v_str = str(v)[:50]
            result += f"    {C.CYAN}{k}{C.END}: {v_str}\n"
    else:
        result += f"  Result: {str(result_data)[:200]}\n"
    
    return result


def show_state_delta(before: Dict[str, Any], after: Dict[str, Any]) -> str:
    """Show state changes"""
    if before == after:
        return f"{C.GREY}[No state changes]{C.END}"
    
    # Find differences
    added = set(after.keys()) - set(before.keys())
    removed = set(before.keys()) - set(after.keys())
    changed = []
    
    for k in set(before.keys()) & set(after.keys()):
        if before[k] != after[k]:
            changed.append(k)
    
    result = f"\n{C.BOLD}🔄 STATE CHANGES:{C.END}\n"
    
    if added:
        result += f"  {C.GREEN}➕ Added keys:{C.END} {', '.join(added)}\n"
    if removed:
        result += f"  {C.RED}➖ Removed keys:{C.END} {', '.join(removed)}\n"
    if changed:
        result += f"  {C.YELLOW}🔄 Modified keys:{C.END} {', '.join(changed)}\n"
        
        # Show intent changes in detail
        if "intent" in changed:
            result += f"\n  {C.BOLD}Intent Changes:{C.END}\n"
            before_intent = before.get("intent", {})
            after_intent = after.get("intent", {})
            
            for k in set(before_intent.keys()) | set(after_intent.keys()):
                if before_intent.get(k) != after_intent.get(k):
                    old = before_intent.get(k)
                    new = after_intent.get(k)
                    result += f"    {C.CYAN}{k}{C.END}: {C.RED}{old}{C.END} → {C.GREEN}{new}{C.END}\n"
    
    return result


async def stream_logs(service_url: str = "http://localhost:5001", api_key: str = "supersecretapikey"):
    """Main streaming function"""
    print(f"\n{C.BOLD}{C.GREEN}🔬 DEEP WORKFLOW DEBUGGER - Phase 9 Intent Parser Investigation{C.END}")
    print(f"{C.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.END}")
    print(f"{C.CYAN}Connecting to: {service_url}{C.END}\n")
    
    last_log_count = 0
    retry_count = 0
    max_retries = 5
    
    while retry_count < max_retries:
        try:
            async with aiohttp.ClientSession() as session:
                retry_count = 0
                
                while True:
                    try:
                        # Fetch logs
                        async with session.get(
                            f"{service_url}/debug/logs/stream",
                            headers={"X-API-Key": api_key},
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                logs = data.get("logs", [])
                                
                                # Process new logs
                                if len(logs) > last_log_count:
                                    new_logs = logs[last_log_count:]
                                    for log in new_logs:
                                        log_type = log.get("type", "INFO")
                                        message = log.get("message", "")
                                        log_data = log.get("data", {})
                                        node = log.get("node")
                                        
                                        # Route based on log type
                                        if log_type == "AGENT_ENTRY":
                                            print(agent_header(node, "ENTRY"))
                                            state = log_data.get("state", {})
                                            intent = state.get("intent")
                                            if intent:
                                                print(show_intent(intent))
                                            print(stamp(f"Entering with {len(state)} state keys", "🚀", C.CYAN))
                                            print(f"State keys: {', '.join(list(state.keys())[:10])}")
                                            
                                        elif log_type == "AGENT_EXIT":
                                            state = log_data.get("state", {})
                                            prev_state_node = log_data.get("prev_state", {})
                                            print(agent_header(node, "EXIT"))
                                            print(stamp(f"Exiting after processing", "✅", C.GREEN))
                                            print(show_state_delta(prev_state_node, state))
                                            
                                        elif log_type == "MCP_CALL":
                                            print(show_mcp_call(log_data))
                                            
                                        elif log_type == "MCP_RESULT":
                                            print(show_mcp_result(log_data))
                                            
                                        elif log_type == "INTENT_CHECK":
                                            intent = log_data.get("intent")
                                            keywords = intent.get("keywords_for_discovery", []) if intent else []
                                            print(stamp(f"Intent keywords for discovery: {keywords}", "🧠", C.CYAN))
                                            if intent:
                                                print(show_intent(intent, "Current Intent"))
                                            
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
                                            print(stamp(message, emoji, color))
                                            if log_data:
                                                for k, v in log_data.items():
                                                    if isinstance(v, (dict, list)):
                                                        v_str = json.dumps(v)[:100]
                                                    else:
                                                        v_str = str(v)
                                                    print(f"  {C.GREY}{k}: {v_str}{C.END}")
                                        
                                        print()  # Blank line for readability
                                    
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
                print(f"{C.YELLOW}⚠️  Cannot connect to service (attempt {retry_count}/{max_retries})...{C.END}")
                print(f"{C.YELLOW}   Retrying in 3 seconds...{C.END}")
                await asyncio.sleep(3)
            else:
                print(f"{C.RED}❌ Failed to connect after {max_retries} attempts.{C.END}")
                print(f"{C.YELLOW}   Make sure LangGraph service is running on {service_url}{C.END}")
                return
        except Exception as e:
            print(f"{C.RED}❌ Unexpected error: {e}{C.END}")
            retry_count += 1
            if retry_count < max_retries:
                await asyncio.sleep(3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deep Workflow Debugger for Phase 9 Intent Parser")
    parser.add_argument("--url", default="http://localhost:5001", help="LangGraph service URL")
    parser.add_argument("--api-key", default="supersecretapikey", help="API key for authentication")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(stream_logs(args.url, args.api_key))
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}👋 Stopped monitoring{C.END}")
        sys.exit(0)