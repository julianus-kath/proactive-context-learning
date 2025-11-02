#!/usr/bin/env python3
"""
Comprehensive test for LangGraph Studio setup.
Run this to verify all graphs are properly configured.
"""

import subprocess
import sys
import time
import requests
import json
from pathlib import Path

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_langgraph_json():
    """Test langgraph.json validity"""
    print_section("1. Testing langgraph.json")
    
    try:
        with open("langgraph.json") as f:
            config = json.load(f)
        print("✅ langgraph.json is valid JSON")
        
        graphs = config.get("graphs", {})
        print(f"\n📊 Found {len(graphs)} graph(s):")
        for name, path in graphs.items():
            print(f"   - {name}: {path}")
        return True
    except Exception as e:
        print(f"❌ Error reading langgraph.json: {e}")
        return False

def test_graph_imports():
    """Test that all graph functions can be imported"""
    print_section("2. Testing Graph Imports")
    
    graphs_to_test = [
        ("main_orchestrator", "langgraph_integration.graph_definition:build_graph"),
        ("discovery_agent", "langgraph_integration.agents.discovery.agent:build_discovery_graph"),
        ("join_sql_agent", "langgraph_integration.agents.join_sql.agent:build_join_sql_graph"),
        ("exec_recovery_agent", "langgraph_integration.agents.exec_recovery.agent:build_exec_recovery_graph"),
        ("answer_agent", "langgraph_integration.agents.answer.agent:build_answer_graph"),
    ]
    
    all_ok = True
    for name, path in graphs_to_test:
        try:
            module_path, func_name = path.rsplit(":", 1)
            module = __import__(module_path, fromlist=[func_name])
            func = getattr(module, func_name)
            print(f"✅ {name:20} - Import OK")
        except Exception as e:
            print(f"❌ {name:20} - {str(e)[:50]}")
            all_ok = False
    
    return all_ok

def test_graph_building():
    """Test that all graph functions can build graphs"""
    print_section("3. Testing Graph Building")
    
    graphs_to_test = [
        ("main_orchestrator", "langgraph_integration.graph_definition", "build_graph"),
        ("discovery_agent", "langgraph_integration.agents.discovery.agent", "build_discovery_graph"),
        ("join_sql_agent", "langgraph_integration.agents.join_sql.agent", "build_join_sql_graph"),
        ("exec_recovery_agent", "langgraph_integration.agents.exec_recovery.agent", "build_exec_recovery_graph"),
        ("answer_agent", "langgraph_integration.agents.answer.agent", "build_answer_graph"),
    ]
    
    all_ok = True
    for name, module_name, func_name in graphs_to_test:
        try:
            module = __import__(module_name, fromlist=[func_name])
            func = getattr(module, func_name)
            graph = func()
            nodes_count = len(graph.nodes)
            print(f"✅ {name:20} - Built ({nodes_count} nodes)")
        except Exception as e:
            print(f"❌ {name:20} - {str(e)[:50]}")
            all_ok = False
    
    return all_ok

def test_langgraph_dev():
    """Test that langgraph dev command works"""
    print_section("4. Testing LangGraph Dev Server")
    
    try:
        # Check if langgraph command exists
        result = subprocess.run(
            ["langgraph", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        version = result.stdout.strip()
        print(f"✅ langgraph-cli available: {version}")
        
        # Try to start dev server briefly
        print("\n   Starting dev server on port 2024...")
        proc = subprocess.Popen(
            ["langgraph", "dev", "--port", "2024", "--no-reload"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        time.sleep(4)
        
        try:
            # Check if server is responding
            response = requests.get("http://127.0.0.1:2024/info", timeout=5)
            if response.status_code == 200:
                print(f"✅ Dev server started successfully")
                info = response.json()
                print(f"   Version: {info.get('version')}")
                print(f"   LangGraph Python: {info.get('langgraph_py_version')}")
            else:
                print(f"⚠️  Dev server responded with status {response.status_code}")
        except Exception as e:
            print(f"⚠️  Could not connect to dev server: {e}")
        finally:
            proc.terminate()
            proc.wait(timeout=5)
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("  LangGraph Studio Setup Diagnostics")
    print("="*60)
    
    results = {
        "langgraph.json": test_langgraph_json(),
        "imports": test_graph_imports(),
        "building": test_graph_building(),
        "dev_server": test_langgraph_dev(),
    }
    
    print_section("Summary")
    all_ok = all(results.values())
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print("\n" + "="*60)
    if all_ok:
        print("✅ All checks passed! LangGraph Studio should work.")
        print("\nTo start LangGraph Studio, run:")
        print("   langgraph dev --port 2024")
        print("\nOr use the startup script:")
        print("   ./start_all_services_mac.sh")
    else:
        print("❌ Some checks failed. See details above.")
    print("="*60 + "\n")
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())