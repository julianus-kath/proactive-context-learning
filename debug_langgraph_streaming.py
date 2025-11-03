#!/usr/bin/env python3
"""
🔬 LANGGRAPH STREAMING DEBUGGER - Real-Time Node Execution Tracking

This debugger uses LangGraph's built-in streaming interface to show EXACTLY
which nodes execute, in what order, and what state they produce.

This will definitively answer: "Why is the workflow stopping after search_tables?"

Usage:
    python debug_langgraph_streaming.py "How many customers do we have?"
"""

import asyncio
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

sys.path.insert(0, '/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code')

from langgraph_integration.orchestrator import QueryOrchestrator
from langgraph_integration.contracts.state import BaseState
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class StreamingDebugger:
    """Real-time LangGraph execution debugger."""
    
    def __init__(self):
        self.events = []
        self.nodes_executed = []
        
    def print_banner(self, text: str, width: int = 80) -> None:
        """Print a formatted banner."""
        print(f"\n{'='*width}")
        print(f"  {text}")
        print(f"{'='*width}")
    
    def print_section(self, text: str) -> None:
        """Print a section header."""
        print(f"\n>>> {text}")
    
    async def stream_orchestrator(self, user_query: str) -> Dict[str, Any]:
        """
        Execute orchestrator with LangGraph streaming.
        
        This will show EVERY event from the graph execution.
        """
        self.print_banner("🔬 LANGGRAPH STREAMING DEBUGGER")
        print(f"\n📝 Query: {user_query}")
        self.print_banner("")
        
        try:
            # Initialize orchestrator
            logger.info("Initializing orchestrator...")
            orchestrator = QueryOrchestrator(
                llm_model="gpt-4o",
                llm_temp=0.0,
            )
            logger.info("✅ Orchestrator initialized")
            
            # Initial state
            initial_state: BaseState = {
                "user_input": user_query,
                "messages": [],
            }
            
            # Execute with streaming
            logger.info("Starting LangGraph execution with streaming...")
            
            self.print_section("⏳ EXECUTION EVENTS (streaming)")
            
            node_count = 0
            events_by_node = {}
            
            # Use astream_events() if available, else ainvoke()
            try:
                # Try using astream_events (LangGraph 0.1.x+)
                async for event in orchestrator.graph.astream_events(
                    initial_state,
                    config={"recursion_limit": 25}
                ):
                    self._handle_stream_event(event, events_by_node)
                    
            except AttributeError:
                # Fallback: Use ainvoke and show state changes
                logger.warning("astream_events not available, using ainvoke fallback")
                self.print_section("⚠️  Using ainvoke (less detailed)")
                
                final_state = await orchestrator.graph.ainvoke(
                    initial_state,
                    config={"timeout": 60}
                )
                
                # Show final state
                self.print_section("📊 FINAL STATE")
                self._show_state_summary(final_state)
                
                return final_state
            
            # Print events summary
            self.print_section("📋 EVENTS SUMMARY")
            for node_name in sorted(events_by_node.keys()):
                events = events_by_node[node_name]
                print(f"\n  {node_name}:")
                for evt in events:
                    print(f"    - {evt}")
            
            logger.info("✅ Streaming execution completed")
            
        except Exception as e:
            logger.error(f"❌ Execution failed: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _handle_stream_event(self, event: Dict[str, Any], events_by_node: Dict) -> None:
        """Handle a single stream event from LangGraph."""
        event_type = event.get("event", "")
        data = event.get("data", {})
        
        if event_type == "on_chain_start":
            # Node is starting
            name = event.get("name", "?")
            if name not in events_by_node:
                events_by_node[name] = []
            events_by_node[name].append(f"🟢 START")
            
            print(f"\n🟢 NODE START: {name}")
            print(f"   Timestamp: {datetime.now().isoformat()}")
            
            if "input" in data:
                input_data = data["input"]
                print(f"   Input keys: {list(input_data.keys()) if isinstance(input_data, dict) else type(input_data)}")
        
        elif event_type == "on_chain_end":
            # Node completed
            name = event.get("name", "?")
            if name not in events_by_node:
                events_by_node[name] = []
            events_by_node[name].append(f"🔴 END")
            
            print(f"\n🔴 NODE END: {name}")
            print(f"   Timestamp: {datetime.now().isoformat()}")
            
            if "output" in data:
                output_data = data["output"]
                if isinstance(output_data, dict):
                    print(f"   Output keys: {list(output_data.keys())}")
                    # Show critical fields
                    if "intent" in output_data:
                        intent = output_data["intent"]
                        if isinstance(intent, dict):
                            kfd = intent.get("keywords_for_discovery", [])
                            print(f"   ✓ intent.keywords_for_discovery: {kfd}")
                    if "relevant_tables" in output_data:
                        tables = output_data["relevant_tables"]
                        print(f"   ✓ relevant_tables: {len(tables) if isinstance(tables, list) else '?'} items")
                    if "error_info" in output_data and output_data["error_info"]:
                        print(f"   ❌ error_info: {output_data['error_info']}")
        
        elif event_type == "on_llm_start":
            # LLM call starting
            name = event.get("name", "LLM")
            print(f"\n💬 LLM CALL: {name}")
        
        elif event_type == "on_tool_start":
            # Tool call starting
            name = event.get("name", "tool")
            print(f"\n🔧 TOOL CALL: {name}")
            if "input" in data:
                print(f"   Input: {data['input']}")
        
        elif event_type == "on_tool_end":
            # Tool call completed
            name = event.get("name", "tool")
            print(f"\n✅ TOOL END: {name}")
            if "output" in data:
                output = data["output"]
                if isinstance(output, dict):
                    print(f"   Output keys: {list(output.keys())}")
                else:
                    print(f"   Output: {str(output)[:100]}")
        
        self.events.append({
            "type": event_type,
            "name": event.get("name"),
            "timestamp": datetime.now().isoformat()
        })
    
    def _show_state_summary(self, state: BaseState) -> None:
        """Show a summary of the final state."""
        print(f"\n📊 FULL STATE SUMMARY:")
        
        # Intent
        intent = state.get("intent", {})
        print(f"\n🧠 Intent:")
        if intent:
            print(f"   operation: {intent.get('operation')}")
            print(f"   keywords_for_discovery: {intent.get('keywords_for_discovery')} {'✅' if intent.get('keywords_for_discovery') else '❌'}")
            print(f"   confidence: {intent.get('confidence')}")
        else:
            print(f"   (empty or not set)")
        
        # Discovery
        relevant_tables = state.get("relevant_tables", [])
        print(f"\n🔍 Discovery:")
        print(f"   relevant_tables: {len(relevant_tables) if isinstance(relevant_tables, list) else '?'} items")
        if relevant_tables:
            for i, table in enumerate(relevant_tables[:3]):
                print(f"      {i+1}. {table}")
        
        # Join SQL
        sql_query = state.get("sql_query", "")
        print(f"\n🔗 Join SQL:")
        print(f"   sql_query: {len(sql_query)} chars")
        if sql_query:
            print(f"   Preview: {sql_query[:150]}...")
        
        # Execution
        exec_result = state.get("exec_result", {})
        print(f"\n⚡ Execution:")
        if exec_result:
            print(f"   ok: {exec_result.get('ok')}")
            print(f"   row_count: {exec_result.get('row_count')}")
        else:
            print(f"   (no results)")
        
        # Answer
        final_response = state.get("final_response", "")
        print(f"\n📝 Answer:")
        print(f"   {final_response[:200]}")
        
        # Errors
        error_info = state.get("error_info")
        if error_info:
            print(f"\n❌ ERROR INFO:")
            print(f"   type: {error_info.get('type')}")
            print(f"   message: {error_info.get('message')}")
            print(f"   context: {error_info.get('context')}")


async def main():
    """Main entry point."""
    query = sys.argv[1] if len(sys.argv) > 1 else "How many customers do we have?"
    
    debugger = StreamingDebugger()
    await debugger.stream_orchestrator(query)


if __name__ == "__main__":
    asyncio.run(main())