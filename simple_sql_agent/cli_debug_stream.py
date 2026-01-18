#!/usr/bin/env python3
"""
CLI tool for debugging Simple SQL Agent with live streaming.

Usage:
    python -m simple_sql_agent.cli_debug_stream "Your question here"
    python -m simple_sql_agent.cli_debug_stream --interactive
"""

import asyncio
import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

from simple_sql_agent.agent import create_sql_agent
from simple_sql_agent.debug_stream import debug_stream_cli, DebugStreamFormatter, stream_agent_execution


async def run_single_query(question: str) -> None:
    """Run a single query with debug stream."""
    print("🚀 Initializing SQL Agent...")
    agent = create_sql_agent()
    print("✅ Agent ready\n")

    await debug_stream_cli(agent, question)


async def run_interactive_mode() -> None:
    """Run in interactive mode."""
    print("🚀 Initializing SQL Agent...")
    agent = create_sql_agent()
    print("✅ Agent ready\n")

    print("=" * 80)
    print("📝 DEBUG STREAM - Interactive Mode")
    print("=" * 80)
    print("Type your questions and press Enter to execute.")
    print("Type 'exit' or 'quit' to exit.\n")

    while True:
        try:
            question = input("🔍 Question: ").strip()

            if not question:
                print("⚠️  Please enter a question.\n")
                continue

            if question.lower() in ("exit", "quit"):
                print("\n✨ Goodbye!")
                break

            print()
            await debug_stream_cli(agent, question)
            print()

        except KeyboardInterrupt:
            print("\n\n✨ Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}\n")


async def stream_and_collect(agent, question: str) -> dict:
    """Stream execution and collect all events."""
    events = []
    async for event in stream_agent_execution(agent, question):
        events.append(event)
    return {
        "question": question,
        "events": events,
        "event_count": len(events),
    }


async def run_batch_queries(queries_file: str) -> None:
    """Run multiple queries from a file."""
    file_path = Path(queries_file)
    if not file_path.exists():
        print(f"❌ File not found: {queries_file}")
        return

    print("🚀 Initializing SQL Agent...")
    agent = create_sql_agent()
    print("✅ Agent ready\n")

    with open(file_path) as f:
        lines = f.readlines()

    questions = [line.strip() for line in lines if line.strip() and not line.startswith("#")]

    print(f"📋 Running {len(questions)} queries...\n")

    for i, question in enumerate(questions, 1):
        print(f"\n{'=' * 80}")
        print(f"[{i}/{len(questions)}] Query")
        print(f"{'=' * 80}\n")

        await debug_stream_cli(agent, question)


def main():
    parser = argparse.ArgumentParser(
        description="Debug Simple SQL Agent with live streaming",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single query
  python -m simple_sql_agent.cli_debug_stream "How many customers do we have?"

  # Interactive mode
  python -m simple_sql_agent.cli_debug_stream --interactive

  # Batch mode from file
  python -m simple_sql_agent.cli_debug_stream --batch queries.txt
        """,
    )

    parser.add_argument(
        "question",
        nargs="?",
        help="Natural language question to ask the agent",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive mode (ask multiple questions)",
    )
    parser.add_argument(
        "--batch",
        help="Run queries from a text file (one per line)",
    )

    args = parser.parse_args()

    try:
        if args.interactive:
            asyncio.run(run_interactive_mode())
        elif args.batch:
            asyncio.run(run_batch_queries(args.batch))
        elif args.question:
            asyncio.run(run_single_query(args.question))
        else:
            parser.print_help()
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n✨ Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
