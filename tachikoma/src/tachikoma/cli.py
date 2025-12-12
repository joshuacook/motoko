#!/usr/bin/env python3
"""Tachikoma CLI - Workspace maintenance agent."""

from __future__ import annotations

import argparse
import logging
import os
import sys

from .agent import TachikomaAgent


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Tachikoma - Workspace maintenance agent for the Context Lake",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Cleanup modes:
  schema      Analyze and propose schema improvements (run first)
  frontmatter Fix frontmatter fields to match schema
  structure   Relocate, archive, delete, or merge files

Examples:
  tachikoma --workspace ~/workspaces/personal --mode schema
  tachikoma -w ~/workspaces/coyote -m frontmatter
  tachikoma -m structure  # uses WORKSPACE_PATH env var
        """,
    )

    parser.add_argument(
        "-w", "--workspace",
        default=os.environ.get("WORKSPACE_PATH", os.getcwd()),
        help="Path to workspace (default: WORKSPACE_PATH env var or current directory)",
    )

    parser.add_argument(
        "-m", "--mode",
        choices=["schema", "frontmatter", "structure"],
        required=True,
        help="Cleanup mode to run",
    )

    parser.add_argument(
        "--model",
        default="claude-sonnet-4-20250514",
        help="Anthropic model to use (default: claude-sonnet-4-20250514)",
    )

    parser.add_argument(
        "--max-turns",
        type=int,
        default=20,
        help="Maximum conversation turns (default: 20)",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Validate workspace
    if not os.path.isdir(args.workspace):
        print(f"Error: Workspace not found: {args.workspace}", file=sys.stderr)
        sys.exit(1)

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable required", file=sys.stderr)
        sys.exit(1)

    # Run agent
    print(f"Tachikoma - {args.mode} cleanup")
    print(f"Workspace: {args.workspace}")
    print("-" * 50)

    agent = TachikomaAgent(
        workspace_path=args.workspace,
        cleanup_mode=args.mode,
        model=args.model,
        max_turns=args.max_turns,
    )

    result = agent.run()

    print("-" * 50)
    print(f"Completed in {result['turns']} turns")
    print(f"Decisions created: {len(result['decisions_created'])}")

    if result["decisions_created"]:
        print("\nDecisions:")
        for decision in result["decisions_created"]:
            print(f"  - decisions/{decision}")


if __name__ == "__main__":
    main()
