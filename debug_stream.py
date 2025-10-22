#!/usr/bin/env python3
"""
Real-time Debug Stream Monitor
Streams LangGraph workflow events in real-time from the LangGraph service
Shows tool calls, scout mode operations, SQL generation, and query execution
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime
from typing import Dict, Any

# Color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def format_log(level: str, message: str, data: Dict[str, Any] = None) -> str:
    """Format a log entry with colors and emojis."""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
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
    color = color_map.get(level, Colors.CYAN)
    
    output = f"{color}[{timestamp}] {emoji} {message}{Colors.END}"
    
    if data:
        output += "\n"
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                output += f"  {key}: {json.dumps(value, indent=2)}\n"
            else:
                output += f"  {key}: {value}\n"
    
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
                                        print(format_log(log_type, message))
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