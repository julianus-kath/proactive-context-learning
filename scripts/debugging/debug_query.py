import asyncio
import logging
from langgraph_integration.orchestrator import QueryOrchestrator

logging.basicConfig(level=logging.DEBUG)

async def debug_query():
    orchestrator = QueryOrchestrator()
    await orchestrator.initialize()

    try:
        result = await orchestrator.process_query("How many customers do we have?")
        print(f"Final result: {result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_query())
