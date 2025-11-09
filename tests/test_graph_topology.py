#!/usr/bin/env python3
"""
Smoke test: Verify all LangGraph agents have proper topology (no orphaned nodes).
"""

import os
import sys

# Set dummy OpenAI key for inspection
os.environ["OPENAI_API_KEY"] = "sk-test-dummy-key-for-inspection"

from langgraph_integration.agents.discovery.agent import DiscoveryAgent
from langgraph_integration.agents.answer.agent import AnswerAgent
from langgraph_integration.agents.exec_recovery.agent import ExecAndRecoveryAgent
from langgraph_integration.agents.join_sql.agent import JoinPlanAndSQLAgent


def inspect_graph(agent_name: str, agent_instance) -> bool:
    """Inspect a compiled graph and report topology."""
    print(f"\n{'='*60}")
    print(f"Agent: {agent_name}")
    print('='*60)
    
    try:
        g = agent_instance.build_subgraph()
        
        # Extract nodes and edges using get_graph()
        graph_spec = g.get_graph()
        nodes = set(graph_spec.nodes)
        edges = set()
        
        # Extract edges from the graph spec
        for edge_info in graph_spec.edges:
            # edge_info is typically a tuple of (source, target) or may have metadata
            if hasattr(edge_info, '__len__'):
                if len(edge_info) >= 2:
                    edges.add((edge_info[0], edge_info[1]))
            else:
                # If not a tuple, try to access as object
                if hasattr(edge_info, 'source') and hasattr(edge_info, 'target'):
                    edges.add((edge_info.source, edge_info.target))
        
        # Filter out special nodes
        user_nodes = {n for n in nodes if n not in {"__start__", "__end__"}}
        
        print(f"\n📊 Nodes ({len(user_nodes)} user-defined):")
        for node in sorted(user_nodes):
            print(f"  • {node}")
        
        print(f"\n🔗 Edges ({len(edges)} total):")
        for u, v in sorted(edges):
            # Hide internal edges
            if u not in {"__start__", "__end__"} or v not in {"__start__", "__end__"}:
                print(f"  • {u} → {v}")
        
        # Check for orphaned nodes
        in_degree = {n: 0 for n in user_nodes}
        out_degree = {n: 0 for n in user_nodes}
        
        for u, v in edges:
            if u in user_nodes:
                out_degree[u] += 1
            if v in user_nodes:
                in_degree[v] += 1
        
        orphaned = [n for n in user_nodes if in_degree[n] == 0 and out_degree[n] == 0]
        isolated_sources = [n for n in user_nodes if out_degree[n] == 0 and in_degree[n] > 0]
        isolated_sinks = [n for n in user_nodes if in_degree[n] == 0 and out_degree[n] > 0]
        
        print(f"\n⚠️  Orphaned nodes (no in/out edges): {orphaned if orphaned else 'None ✅'}")
        print(f"⚠️  Isolated sinks (in-only): {isolated_sinks if isolated_sinks else 'None ✅'}")
        print(f"⚠️  Isolated sources (out-only): {isolated_sources if isolated_sources else 'None ✅'}")
        
        # Verdict
        has_issues = bool(orphaned or isolated_sources or isolated_sinks)
        if not has_issues:
            print(f"\n✅ {agent_name} topology is HEALTHY")
            return True
        else:
            print(f"\n❌ {agent_name} has topology issues")
            return False
            
    except Exception as e:
        print(f"\n❌ Error inspecting {agent_name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run topology checks on all agents."""
    print("🔍 LangGraph Topology Smoke Test\n")
    
    results = {}
    
    # Test all agents
    results["DiscoveryAgent"] = inspect_graph(
        "DiscoveryAgent",
        DiscoveryAgent()
    )
    
    results["AnswerAgent"] = inspect_graph(
        "AnswerAgent",
        AnswerAgent()
    )
    
    results["ExecAndRecoveryAgent"] = inspect_graph(
        "ExecAndRecoveryAgent",
        ExecAndRecoveryAgent()
    )
    
    results["JoinPlanAndSQLAgent"] = inspect_graph(
        "JoinPlanAndSQLAgent",
        JoinPlanAndSQLAgent()
    )
    
    # Summary
    print(f"\n{'='*60}")
    print("📋 Summary")
    print('='*60)
    for agent, healthy in results.items():
        status = "✅" if healthy else "❌"
        print(f"{status} {agent}")
    
    all_healthy = all(results.values())
    print(f"\n{'='*60}")
    if all_healthy:
        print("🎉 All agents have healthy topology!")
        return 0
    else:
        print("⚠️  Some agents need fixing")
        return 1


if __name__ == "__main__":
    sys.exit(main())