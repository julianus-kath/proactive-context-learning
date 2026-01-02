#!/usr/bin/env python3
"""
🔬 DEEP WORKFLOW DEBUGGER

Real-time debug monitor that PAINFULLY SHOWS:
✓ Exact agent name and execution stage
✓ Input state (what agent receives)
✓ Output state (what agent produces)
✓ State mutations (what changed?)
✓ Intent field tracking (is it being passed correctly?)
✓ MCP tool calls (which discovery tools are actually used?)
✓ Internal reasoning steps (LLM prompts, decisions, etc.)
✓ State isolation issues (are agents seeing each other's data?)

This debugger is designed to expose Phase 9 intent parser integration issues
by showing the complete flow through the multi-agent orchestrator.
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime
from typing import Dict, Any, Optional
import difflib

# ============= COLOR SCHEME FOR MAXIMUM CLARITY =============
class Colors:
    # Core colors
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    PURPLE = '\033[35m'
    WHITE = '\033[97m'
    GREY = '\033[90m'
    
    # Emphasis
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    DIM = '\033[2m'
    
    # Background colors
    BG_BLUE = '\033[44m'
    BG_CYAN = '\033[46m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_RED = '\033[41m'
    BG_PURPLE = '\033[45m'
    BG_WHITE = '\033[47m'
    
    END = '\033[0m'

# Agent/Node specific coloring for visual distinction
NODE_COLOR_PALETTE = [
    Colors.BLUE,
    Colors.CYAN,
    Colors.GREEN,
    Colors.YELLOW,
    Colors.PURPLE,
    Colors.WHITE,
]

NODE_BG_PALETTE = [
    Colors.BG_BLUE,
    Colors.BG_CYAN,
    Colors.BG_GREEN,
    Colors.BG_YELLOW,
    Colors.BG_PURPLE,
    Colors.BG_WHITE,
]

# Phase-specific colors
PHASE_COLORS = {
    "index_database": (Colors.BLUE, Colors.BG_BLUE, "📚"),
    "parse_intent": (Colors.CYAN, Colors.BG_CYAN, "🧠"),
    "route_operation": (Colors.YELLOW, Colors.BG_YELLOW, "🚦"),
    "discovery": (Colors.GREEN, Colors.BG_GREEN, "🔍"),
    "join_sql": (Colors.PURPLE, Colors.BG_PURPLE, "🔗"),
    "exec_recovery": (Colors.YELLOW, Colors.BG_YELLOW, "⚡"),
    "answer": (Colors.WHITE, Colors.BG_WHITE, "📝"),
    "search_candidates": (Colors.GREEN, Colors.BG_GREEN, "🔎"),
    "describe_selected": (Colors.GREEN, Colors.BG_GREEN, "📊"),
}

node_colors: Dict[str, str] = {}
node_bg_colors: Dict[str, str] = {}
node_emojis: Dict[str, str] = {}
current_node_context: Optional[str] = None
node_activity_log: Dict[str, int] = {}  # Track activity count per node
state_snapshots: Dict[str, Dict[str, Any]] = {}  # Track state before/after each node
global_flow_log: list = []  # Track complete flow

def get_node_color(node: str) -> tuple:
    """Assigns and retrieves consistent colors (fg, bg) for a given node name."""
    if node not in node_colors:
        # Check if we have a phase-specific color
        if node in PHASE_COLORS:
            fg, bg, emoji = PHASE_COLORS[node]
            node_colors[node] = fg
            node_bg_colors[node] = bg
            node_emojis[node] = emoji
        else:
            idx = len(node_colors) % len(NODE_COLOR_PALETTE)
            node_colors[node] = NODE_COLOR_PALETTE[idx]
            node_bg_colors[node] = NODE_BG_PALETTE[idx]
            node_emojis[node] = "⚙️"
    return node_colors[node], node_bg_colors[node]


def get_node_emoji(node: str) -> str:
    """Get emoji for node."""
    if node not in node_emojis:
        get_node_color(node)  # Initialize
    return node_emojis.get(node, "⚙️")


def format_agent_header(node: str, stage: str = "EXECUTION", state_keys: list = None) -> str:
    """
    Create a prominent header for agent section with context.
    
    Args:
        node: Node/agent name
        stage: What stage (ENTRY, PROCESSING, EXIT, ERROR)
        state_keys: Keys available in state (for tracking what data is available)
    """
    node_fg, node_bg = get_node_color(node)
    emoji = get_node_emoji(node)
    
    # Track activity
    if node not in node_activity_log:
        node_activity_log[node] = 0
    node_activity_log[node] += 1
    
    activity_num = node_activity_log[node]
    
    # Stage indicator
    stage_color = Colors.GREEN if stage == "EXIT" else Colors.YELLOW if stage == "PROCESSING" else Colors.CYAN
    
    header_text = f" {emoji} {node.upper()} #{activity_num} | {stage} "
    padding = (100 - len(header_text)) // 2
    
    result = (
        f"\n{node_fg}{node_bg}{Colors.BOLD}{'═' * 100}\n"
        f"{' ' * padding}{header_text}{' ' * padding}\n"
        f"{'═' * 100}{Colors.END}\n"
    )
    
    # Add available state keys if provided
    if state_keys:
        available = ", ".join(state_keys[:8])
        if len(state_keys) > 8:
            available += f", +{len(state_keys)-8} more"
        result += f"{Colors.GREY}State keys: {available}{Colors.END}\n"
    
    return result


def format_state_field(label: str, value: Any, max_length: int = 200, indent: int = 2) -> str:
    """
    Format a single state field for readable output.
    
    Handles different value types specially:
    - Dicts/Lists: Pretty-printed JSON
    - Strings: Truncated if too long
    - Numbers: Direct display
    - ParsedIntent: Special formatting
    """
    indent_str = " " * indent
    
    if value is None:
        return f"{indent_str}{Colors.GREY}{label}: None{Colors.END}\n"
    
    if isinstance(value, dict):
        if "operation" in value and "keywords_for_discovery" in value:
            # This is likely a ParsedIntent
            return format_parsed_intent(label, value, indent)
        else:
            # Regular dict
            json_str = json.dumps(value, indent=2)[:500]
            return f"{indent_str}{Colors.CYAN}{label}:{Colors.END}\n{json.dumps(value, indent=4)[:500]}\n"
    elif isinstance(value, list):
        if not value:
            return f"{indent_str}{Colors.GREY}{label}: []{Colors.END}\n"
        items = json.dumps(value[:5], indent=2)
        if len(value) > 5:
            items += f"\n{indent_str}  ... and {len(value)-5} more items"
        return f"{indent_str}{Colors.CYAN}{label}:{Colors.END}\n{items}\n"
    elif isinstance(value, str):
        if len(value) > max_length:
            truncated = value[:max_length] + f"... ({len(value)} chars total)"
        else:
            truncated = value
        return f"{indent_str}{Colors.GREEN}{label}:{Colors.END} {truncated}\n"
    else:
        return f"{indent_str}{Colors.WHITE}{label}:{Colors.END} {value}\n"


def format_parsed_intent(label: str, intent: Dict[str, Any], indent: int = 2) -> str:
    """Format a ParsedIntent dict with special colors and structure."""
    indent_str = " " * indent
    result = f"{indent_str}{Colors.CYAN}{Colors.BOLD}{label}:{Colors.END}\n"
    result += f"{indent_str}  {Colors.GREEN}operation{Colors.END}: {Colors.WHITE}{intent.get('operation', 'N/A')}{Colors.END}\n"
    result += f"{indent_str}  {Colors.GREEN}confidence{Colors.END}: {Colors.YELLOW}{intent.get('confidence', 0):.2f}{Colors.END}\n"
    result += f"{indent_str}  {Colors.GREEN}primary_entities{Colors.END}: {Colors.WHITE}{intent.get('primary_entities', [])}{Colors.END}\n"
    result += f"{indent_str}  {Colors.GREEN}keywords_for_discovery{Colors.END}: {Colors.BOLD}{Colors.WHITE}{intent.get('keywords_for_discovery', [])}{Colors.END}\n"
    result += f"{indent_str}  {Colors.GREEN}metrics{Colors.END}: {Colors.WHITE}{intent.get('metrics', [])}{Colors.END}\n"
    result += f"{indent_str}  {Colors.GREEN}filters{Colors.END}: {Colors.WHITE}{len(intent.get('filters', []))} filter(s){Colors.END}\n"
    result += f"{indent_str}  {Colors.GREEN}time_window{Colors.END}: {Colors.WHITE}{intent.get('time_window', 'None')}{Colors.END}\n"
    return result


def format_state_delta(node: str, before: Dict[str, Any], after: Dict[str, Any]) -> str:
    """
    Format the state changes (delta) made by a node.
    
    Shows what changed and how.
    """
    if not before:
        return ""
    
    result = f"\n{Colors.BOLD}STATE MUTATIONS (What Changed?):{Colors.END}\n"
    
    # Keys that changed
    added_keys = set(after.keys()) - set(before.keys())
    removed_keys = set(before.keys()) - set(after.keys())
    common_keys = set(before.keys()) & set(after.keys())
    
    changed_keys = []
    for key in common_keys:
        if before[key] != after[key]:
            changed_keys.append(key)
    
    if added_keys:
        result += f"  {Colors.GREEN}➕ ADDED:{Colors.END} {list(added_keys)}\n"
    
    if removed_keys:
        result += f"  {Colors.RED}➖ REMOVED:{Colors.END} {list(removed_keys)}\n"
    
    if changed_keys:
        result += f"  {Colors.YELLOW}🔄 MODIFIED:{Colors.END} {changed_keys}\n"
        for key in changed_keys:
            before_val = before[key]
            after_val = after[key]
            
            # Special handling for intent
            if key == "intent":
                if isinstance(before_val, dict) and isinstance(after_val, dict):
                    intent_changes = {}
                    for k in set(before_val.keys()) | set(after_val.keys()):
                        if before_val.get(k) != after_val.get(k):
                            intent_changes[k] = (before_val.get(k), after_val.get(k))
                    if intent_changes:
                        result += f"    Intent field changes:\n"
                        for k, (old, new) in intent_changes.items():
                            result += f"      {Colors.CYAN}{k}{Colors.END}: {Colors.RED}{old}{Colors.END} → {Colors.GREEN}{new}{Colors.END}\n"
            else:
                # Show brief before/after for other fields
                if len(str(before_val)) < 100 and len(str(after_val)) < 100:
                    result += f"    {Colors.CYAN}{key}{Colors.END}: {before_val} → {after_val}\n"
                else:
                    result += f"    {Colors.CYAN}{key}{Colors.END}: [changed]\n"
    
    if not (added_keys or removed_keys or changed_keys):
        result += "  {Colors.GREY}No changes{Colors.END}\n"
    
    return result


def format_log(level: str, message: str, data: Dict[str, Any] = None, node: Optional[str] = None) -> str:
    """Format a log entry with colors, emojis, and agent/node identifiers."""
    global current_node_context
    
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    # Extract node/agent name from data if present
    if data and "node" in data:
        node = data.pop("node")
    
    emoji_map = {
        "TOOL_CALL": "🔧",
        "TOOL_RESULT": "✅",
        "SCOUT_MODE": "🔍",
        "INTENT_PARSE": "📝",
        "SCHEMA_DISCOVERY": "📊",
        "SQL_GENERATION": "🔄",
        "QUERY_EXECUTION": "⚡",
        "ERROR": "❌",
        "WARNING": "⚠️",
        "INFO": "ℹ️",
        "DECISION": "🎯",
        "STATE_UPDATE": "💾",
        "TIMING": "⏱️",
    }
    
    color_map = {
        "TOOL_CALL": Colors.CYAN,
        "TOOL_RESULT": Colors.GREEN,
        "SCOUT_MODE": Colors.BLUE,
        "INTENT_PARSE": Colors.CYAN,
        "SCHEMA_DISCOVERY": Colors.BLUE,
        "SQL_GENERATION": Colors.YELLOW,
        "QUERY_EXECUTION": Colors.GREEN,
        "ERROR": Colors.RED,
        "WARNING": Colors.YELLOW,
        "INFO": Colors.CYAN,
        "DECISION": Colors.BOLD,
        "STATE_UPDATE": Colors.CYAN,
        "TIMING": Colors.YELLOW,
    }
    
    emoji = emoji_map.get(level, "•")
    log_color = color_map.get(level, Colors.CYAN)
    
    # Build the log line
    output = ""
    
    # Add agent header if this is a new node
    if node and node != current_node_context:
        current_node_context = node
        output += format_agent_header(node)
    
    # Node prefix with visual distinction
    node_prefix = ""
    if node:
        node_fg, _ = get_node_color(node)
        # Fixed-width, bolded, colored prefix for the node name
        node_prefix = f"{node_fg}{Colors.BOLD}[{node:<16}]{Colors.END} "
    
    # Build main log line
    main_line = f"{node_prefix}{log_color}[{timestamp}] {emoji} {message}{Colors.END}"
    output += main_line
    
    # Append structured data if it exists, with indentation
    if data:
        output += "\n"
        indent = "                      " if node else "  "  # Align with node prefix
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                json_str = json.dumps(value, indent=2)
                output += f"{indent}{Colors.CYAN}{key}:{Colors.END}\n"
                for line in json_str.split('\n'):
                    output += f"{indent}  {line}\n"
            else:
                output += f"{indent}{Colors.CYAN}{key}:{Colors.END} {value}\n"
    
    return output

async def stream_debug_logs(service_url: str = "http://localhost:5001", api_key: str = "supersecretapikey"):
    """
    Stream debug logs from the LangGraph service.
    """
    print(f"{Colors.BOLD}{Colors.GREEN}🔍 LangGraph Real-time Debug Stream Monitor{Colors.END}")
    print(f"{Colors.CYAN}Connecting to {service_url}...{Colors.END}\n")
    
    last_log_count = 0
    retry_count = 0
    max_retries = 5
    
    while retry_count < max_retries:
        try:
            async with aiohttp.ClientSession() as session:
                retry_count = 0  # Reset on successful connection
                
                while True:
                    try:
                        # Fetch logs (non-destructive stream endpoint)
                        async with session.get(
                            f"{service_url}/debug/logs/stream",
                            headers={"X-API-Key": api_key},
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                logs = data.get("logs", [])
                                
                                # Print new logs
                                if len(logs) > last_log_count:
                                    new_logs = logs[last_log_count:]
                                    for log in new_logs:
                                        log_type = log.get("type", "INFO")
                                        message = log.get("message", "")
                                        # Pass all other log data to the formatter to make errors more descriptive
                                        log_data = {k: v for k, v in log.items() if k not in ["type", "message"]}
                                        print(format_log(log_type, message, data=log_data))
                                    last_log_count = len(logs)
                            elif resp.status == 401:
                                print(f"{Colors.RED}❌ Authentication failed. Check API_KEY.{Colors.END}")
                                return
                            else:
                                print(f"{Colors.RED}❌ Server error: {resp.status}{Colors.END}")
                        
                        # Poll every 500ms
                        await asyncio.sleep(0.5)
                    
                    except asyncio.TimeoutError:
                        print(f"{Colors.YELLOW}⚠️  Connection timeout, retrying...{Colors.END}")
                        await asyncio.sleep(2)
                    except Exception as e:
                        print(f"{Colors.YELLOW}⚠️  Error: {e}, retrying...{Colors.END}")
                        await asyncio.sleep(2)
        
        except aiohttp.ClientConnectorError:
            retry_count += 1
            if retry_count < max_retries:
                print(f"{Colors.YELLOW}⚠️  Cannot connect to service (attempt {retry_count}/{max_retries})...{Colors.END}")
                print(f"{Colors.YELLOW}   Retrying in 3 seconds...{Colors.END}")
                await asyncio.sleep(3)
            else:
                print(f"{Colors.RED}❌ Failed to connect after {max_retries} attempts.{Colors.END}")
                print(f"{Colors.YELLOW}   Make sure LangGraph service is running on {service_url}{Colors.END}")
                return
        except Exception as e:
            print(f"{Colors.RED}❌ Unexpected error: {e}{Colors.END}")
            retry_count += 1
            if retry_count < max_retries:
                await asyncio.sleep(3)

if __name__ == "__main__":
    try:
        asyncio.run(stream_debug_logs())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}👋 Stopped monitoring{Colors.END}")
        sys.exit(0)