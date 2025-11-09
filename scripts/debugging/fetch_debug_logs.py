#!/usr/bin/env python3
"""Fetch and display debug logs from LangGraph service"""
import requests
import json
from datetime import datetime

SERVICE_URL = "http://localhost:5001"
API_KEY = "supersecretapikey"

def fetch_logs():
    """Fetch logs from service"""
    try:
        resp = requests.get(
            f"{SERVICE_URL}/debug/logs/stream",
            headers={"X-API-Key": API_KEY},
            timeout=5
        )
        
        if resp.status_code == 200:
            data = resp.json()
            logs = data.get("logs", [])
            
            print(f"\n{'='*120}")
            print(f"📋 CURRENT DEBUG LOGS ({len(logs)} total)")
            print(f"{'='*120}\n")
            
            for i, log in enumerate(logs, 1):
                log_type = log.get("type", "INFO")
                node = log.get("node", "?")
                message = log.get("message", "")
                
                emoji_map = {
                    "AGENT_ENTRY": "🚀",
                    "AGENT_EXIT": "✅",
                    "MCP_CALL": "📡",
                    "MCP_RESULT": "📊",
                    "ERROR": "❌",
                    "WARNING": "⚠️ ",
                    "INFO": "ℹ️ ",
                    "DEBUG": "🐛",
                }
                emoji = emoji_map.get(log_type, "•")
                
                print(f"{i}. {emoji} [{log_type}] Node={node}")
                if message:
                    print(f"   Message: {message}")
                
                # Show data if present
                data = log.get("data", {})
                if data:
                    for k, v in data.items():
                        if isinstance(v, (dict, list)):
                            if isinstance(v, list):
                                print(f"     {k}: [list: {len(v)} items]")
                            else:
                                print(f"     {k}: [dict: {len(v)} keys]")
                        else:
                            v_str = str(v)[:80]
                            print(f"     {k}: {v_str}")
                print()
            
        else:
            print(f"Error: {resp.status_code}")
            print(resp.text)
    
    except Exception as e:
        print(f"Could not fetch logs: {e}")


if __name__ == "__main__":
    fetch_logs()
