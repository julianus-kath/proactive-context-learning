"""
Test LangGraph Studio graph builders for event loop issues.

This test verifies that all graph builders are synchronous and can be called
from LangGraph dev server without "event loop is already running" errors.

Run with:
    pytest tests/test_langgraph_studio_builders.py -v
"""

import pytest
from inspect import iscoroutinefunction


class TestLangGraphBuilders:
    """Test that graph builders are synchronous and load without errors."""
    
    def test_builders_are_functions(self):
        """Verify all builders exist and are callable."""
        from langgraph_integration.graph_definition import build_graph
        from langgraph_integration.agents.discovery.agent import build_discovery_graph
        from langgraph_integration.agents.join_sql.agent import build_join_sql_graph
        from langgraph_integration.agents.exec_recovery.agent import build_exec_recovery_graph
        from langgraph_integration.agents.answer.agent import build_answer_graph
        
        builders = {
            "build_graph": build_graph,
            "build_discovery_graph": build_discovery_graph,
            "build_join_sql_graph": build_join_sql_graph,
            "build_exec_recovery_graph": build_exec_recovery_graph,
            "build_answer_graph": build_answer_graph,
        }
        
        for name, fn in builders.items():
            assert callable(fn), f"{name} is not callable"
    
    def test_builders_are_sync_not_async(self):
        """Verify builders are NOT async functions (required by LangGraph)."""
        from langgraph_integration.graph_definition import build_graph
        from langgraph_integration.agents.discovery.agent import build_discovery_graph
        from langgraph_integration.agents.join_sql.agent import build_join_sql_graph
        from langgraph_integration.agents.exec_recovery.agent import build_exec_recovery_graph
        from langgraph_integration.agents.answer.agent import build_answer_graph
        
        builders = [
            build_graph,
            build_discovery_graph,
            build_join_sql_graph,
            build_exec_recovery_graph,
            build_answer_graph,
        ]
        
        for fn in builders:
            assert not iscoroutinefunction(fn), \
                f"{fn.__name__} is async but should be sync (LangGraph requires sync builders)"
    
    def test_build_main_orchestrator(self):
        """Test main orchestrator builder."""
        from langgraph_integration.graph_definition import build_graph
        
        graph = build_graph()
        assert graph is not None, "build_graph() returned None"
        assert hasattr(graph, 'invoke'), f"Graph missing 'invoke' method: {type(graph)}"
    
    def test_build_discovery_agent(self):
        """Test discovery agent builder."""
        from langgraph_integration.agents.discovery.agent import build_discovery_graph
        
        graph = build_discovery_graph()
        assert graph is not None, "build_discovery_graph() returned None"
        assert hasattr(graph, 'invoke'), f"Graph missing 'invoke' method: {type(graph)}"
    
    def test_build_join_sql_agent(self):
        """Test join SQL agent builder."""
        from langgraph_integration.agents.join_sql.agent import build_join_sql_graph
        
        graph = build_join_sql_graph()
        assert graph is not None, "build_join_sql_graph() returned None"
        assert hasattr(graph, 'invoke'), f"Graph missing 'invoke' method: {type(graph)}"
    
    def test_build_exec_recovery_agent(self):
        """Test exec recovery agent builder."""
        from langgraph_integration.agents.exec_recovery.agent import build_exec_recovery_graph
        
        graph = build_exec_recovery_graph()
        assert graph is not None, "build_exec_recovery_graph() returned None"
        assert hasattr(graph, 'invoke'), f"Graph missing 'invoke' method: {type(graph)}"
    
    def test_build_answer_agent(self):
        """Test answer agent builder."""
        from langgraph_integration.agents.answer.agent import build_answer_graph
        
        graph = build_answer_graph()
        assert graph is not None, "build_answer_graph() returned None"
        assert hasattr(graph, 'invoke'), f"Graph missing 'invoke' method: {type(graph)}"
    
    def test_all_builders_return_compiled_graphs(self):
        """Verify all builders return compiled graph objects."""
        from langgraph_integration.graph_definition import build_graph
        from langgraph_integration.agents.discovery.agent import build_discovery_graph
        from langgraph_integration.agents.join_sql.agent import build_join_sql_graph
        from langgraph_integration.agents.exec_recovery.agent import build_exec_recovery_graph
        from langgraph_integration.agents.answer.agent import build_answer_graph
        
        builders = {
            "main_orchestrator": build_graph,
            "discovery_agent": build_discovery_graph,
            "join_sql_agent": build_join_sql_graph,
            "exec_recovery_agent": build_exec_recovery_graph,
            "answer_agent": build_answer_graph,
        }
        
        for name, fn in builders.items():
            graph = fn()
            graph_type = type(graph).__name__
            
            # Should be CompiledStateGraph or similar compiled graph
            assert "CompiledStateGraph" in graph_type or "Pregel" in graph_type, \
                f"{name} returned {graph_type}, expected compiled graph"
            
            print(f"✅ {name}: {graph_type}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])