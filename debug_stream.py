#!/usr/bin/env python3
"""
Real-time Debug Stream Monitor
Streams LangGraph workflow events in real-time from the LangGraph service
Shows tool calls, scout mode operations, SQL generation, and query execution
Enhanced with per-agent tracking and visual separation
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime
from typing import Dict, Any, Optional

# Color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    PURPLE = '\033[35m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    
    # Background colors for agent headers
    BG_BLUE = '\033[44m'
    BG_CYAN = '\033[46m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_PURPLE = '\033[45m'

# Agent/Node specific coloring
NODE_COLOR_PALETTE = [
    Colors.HEADER,
    Colors.BLUE,
    Colors.CYAN,
    Colors.GREEN,
    Colors.YELLOW,
    Colors.PURPLE,
]

NODE_BG_PALETTE = [
    Colors.BG_BLUE,
    Colors.BG_CYAN,
    Colors.BG_GREEN,
    Colors.BG_YELLOW,
    Colors.BG_PURPLE,
]

node_colors: Dict[str, str] = {}
node_bg_colors: Dict[str, str] = {}
current_node_context: Optional[str] = None
node_activity_log: Dict[str, int] = {}  # Track activity count per node

def get_node_color(node: str) -> tuple:
    """Assigns and retrieves consistent colors (fg, bg) for a given node name."""
    if node not in node_colors:
        idx = len(node_colors) % len(NODE_COLOR_PALETTE)
        node_colors[node] = NODE_COLOR_PALETTE[idx]
        node_bg_colors[node] = NODE_BG_PALETTE[idx]
    return node_colors[node], node_bg_colors[node]


def format_agent_header(node: str, activity_num: int = None) -> str:
    """Create a prominent header for agent section."""
    node_fg, node_bg = get_node_color(node)
    
    # Track activity
    if node not in node_activity_log:
        node_activity_log[node] = 0
    node_activity_log[node] += 1
    
    activity_num = node_activity_log[node]
    
    header_text = f" AGENT: {node} (Activity #{activity_num}) "
    padding = (80 - len(header_text)) // 2
    
    return (
        f"\n{node_fg}{node_bg}{Colors.BOLD}{'=' * 80}\n"
        f"{' ' * padding}{header_text}{' ' * padding}\n"
        f"{'=' * 80}{Colors.END}\n"
    )


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