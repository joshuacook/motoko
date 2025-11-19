"""Role management examples.

This example demonstrates motoko's role management capabilities:
- Switching roles mid-conversation
- Multi-role conversations
- Role-specific tool access
- Role state tracking
"""

import asyncio
from pathlib import Path

from motoko import (
    Agent,
    create_model,
    ReadFileTool,
    WriteFileTool,
    GlobTool,
    GrepTool,
    WebFetchTool,
)


def example_1_basic_role_switching():
    """Example 1: Simple role switching mid-conversation."""
    print("=" * 60)
    print("Example 1: Basic Role Switching")
    print("=" * 60)

    workspace = Path.cwd()
    model = create_model("claude-3-5-sonnet-20241022")
    tools = [ReadFileTool(workspace=workspace), GlobTool(workspace=workspace)]

    agent = Agent(model=model, tools=tools, workspace=workspace)

    # Start with one role
    print("\n[Role: Code Reviewer]")
    response = agent.chat(
        message="Review the code quality in motoko/agent.py",
        system_prompt="You are an expert code reviewer focused on Python best practices.",
    )
    print(f"Response: {response.text[:200]}...\n")

    # Switch to different perspective mid-conversation
    agent.switch_role(
        "You are a security expert focused on finding vulnerabilities.",
        role_name="security_expert",
    )

    print("[Role: Security Expert]")
    response = agent.chat(
        message="Now analyze the same file for security issues.",
    )
    print(f"Response: {response.text[:200]}...\n")

    # Check role history
    print(f"Role history: {agent.role_history}")
    print(f"Current role: {agent.current_role}")


def example_2_multi_role_collaboration():
    """Example 2: Multiple roles collaborating."""
    print("\n" + "=" * 60)
    print("Example 2: Multi-Role Collaboration")
    print("=" * 60)

    workspace = Path.cwd()
    model = create_model("claude-3-5-sonnet-20241022")

    # Different tools for different roles
    read_tool = ReadFileTool(workspace=workspace)
    write_tool = WriteFileTool(workspace=workspace)
    glob_tool = GlobTool(workspace=workspace)
    web_tool = WebFetchTool()

    all_tools = [read_tool, write_tool, glob_tool, web_tool]

    agent = Agent(model=model, tools=all_tools, workspace=workspace)

    # Register multiple roles with different tool access
    agent.add_role(
        "researcher",
        "You are a research specialist who gathers information from files and the web.",
        tools=[read_tool, glob_tool, web_tool],  # Can read and fetch web
        category="information_gathering",
    )

    agent.add_role(
        "writer",
        "You are a technical writer who creates clear documentation.",
        tools=[read_tool, write_tool],  # Can read and write
        category="documentation",
    )

    agent.add_role(
        "reviewer",
        "You are a documentation reviewer who checks for clarity and accuracy.",
        tools=[read_tool],  # Can only read
        category="quality_assurance",
    )

    # List registered roles
    print("\nRegistered roles:")
    for role in agent.list_roles():
        print(f"  - {role['name']}: {len(role['tools'])} tools")

    # Have different roles work on a task
    print("\n[Researcher gathering information]")
    research = agent.chat_as(
        "researcher",
        "Find information about the Agent class in the codebase",
    )
    print(f"Findings: {research.text[:150]}...\n")

    print("[Writer creating documentation]")
    doc = agent.chat_as(
        "writer",
        f"Based on this research, create a brief guide: {research.text[:500]}",
    )
    print(f"Draft: {doc.text[:150]}...\n")

    print("[Reviewer checking the documentation]")
    review = agent.chat_as(
        "reviewer",
        f"Review this documentation for clarity: {doc.text[:500]}",
    )
    print(f"Review: {review.text[:150]}...")


def example_3_role_specific_tool_access():
    """Example 3: Role-specific tool restrictions."""
    print("\n" + "=" * 60)
    print("Example 3: Role-Specific Tool Access")
    print("=" * 60)

    workspace = Path.cwd()
    model = create_model("claude-3-5-sonnet-20241022")

    read_tool = ReadFileTool(workspace=workspace)
    write_tool = WriteFileTool(workspace=workspace)
    grep_tool = GrepTool(workspace=workspace)

    agent = Agent(model=model, tools=[read_tool, write_tool, grep_tool], workspace=workspace)

    # Read-only role (e.g., auditor)
    agent.add_role(
        "auditor",
        "You are an auditor who can only read and search files, never modify them.",
        tools=[read_tool, grep_tool],
    )

    # Full-access role (e.g., developer)
    agent.add_role(
        "developer",
        "You are a developer with full file access.",
        tools=[read_tool, write_tool, grep_tool],
    )

    print("\n[Auditor trying to read files]")
    response = agent.chat_as("auditor", "Read the README.md file")
    print("✓ Auditor can read files")

    print("\n[Auditor trying to modify files would fail]")
    print("(WriteFileTool not available to auditor role)")

    print("\n[Developer has full access]")
    print("✓ Developer can read, write, and search files")

    # Show tool access for each role
    print("\nTool access by role:")
    for role_name in ["auditor", "developer"]:
        role = agent.get_role(role_name)
        print(f"  {role_name}: {', '.join(role.tools)}")


def example_4_streaming_with_roles():
    """Example 4: Streaming responses with roles."""
    print("\n" + "=" * 60)
    print("Example 4: Streaming with Roles")
    print("=" * 60)

    async def run_streaming():
        workspace = Path.cwd()
        model = create_model("claude-3-5-sonnet-20241022")
        tools = [ReadFileTool(workspace=workspace)]

        agent = Agent(model=model, tools=tools, workspace=workspace)

        agent.add_role(
            "storyteller",
            "You are a creative storyteller who weaves engaging narratives.",
            tools=[ReadFileTool(workspace=workspace)],
        )

        print("\n[Storyteller streaming response]")
        print("-" * 60)

        async for event in agent.stream_as(
            "storyteller", "Tell me about the motoko package in story form"
        ):
            if event.type == "text_chunk":
                print(event.data, end="", flush=True)
            elif event.type == "done":
                print("\n" + "-" * 60)
                break

    asyncio.run(run_streaming())


def example_5_role_state_tracking():
    """Example 5: Tracking role history and state."""
    print("\n" + "=" * 60)
    print("Example 5: Role State Tracking")
    print("=" * 60)

    workspace = Path.cwd()
    model = create_model("claude-3-5-sonnet-20241022")
    tools = [ReadFileTool(workspace=workspace)]

    agent = Agent(model=model, tools=tools, workspace=workspace)

    # Start with initial role
    agent.switch_role("You are a helpful assistant", role_name="assistant")
    print(f"Current role: {agent.current_role}")

    # Switch roles multiple times
    agent.switch_role("You are a Python expert", role_name="python_expert")
    print(f"Current role: {agent.current_role}")

    agent.switch_role("You are an architect", role_name="architect")
    print(f"Current role: {agent.current_role}")

    # View role history
    print("\nRole history (chronological):")
    for i, (role_name, prompt) in enumerate(agent.role_history, 1):
        print(f"  {i}. {role_name}: {prompt[:50]}...")

    print(f"\nTotal role switches: {len(agent.role_history)}")


def example_6_artist_management_workflow():
    """Example 6: Real-world scenario - Artist management app."""
    print("\n" + "=" * 60)
    print("Example 6: Artist Management Workflow (Real-world)")
    print("=" * 60)

    workspace = Path.cwd()
    model = create_model("claude-3-5-sonnet-20241022")

    read_tool = ReadFileTool(workspace=workspace)
    write_tool = WriteFileTool(workspace=workspace)
    web_tool = WebFetchTool()

    agent = Agent(model=model, tools=[read_tool, write_tool, web_tool], workspace=workspace)

    # Define roles for artist management
    agent.add_role(
        "artist_manager",
        """You are an experienced artist manager who handles:
        - Artist career development
        - Strategic planning
        - Communication with artists
        You have access to artist files and can update them.""",
        tools=[read_tool, write_tool],
    )

    agent.add_role(
        "booking_agent",
        """You are a booking agent who handles:
        - Finding performance opportunities
        - Negotiating bookings
        - Researching venues
        You can read artist info and search the web for opportunities.""",
        tools=[read_tool, web_tool],
    )

    agent.add_role(
        "financial_advisor",
        """You are a financial advisor who handles:
        - Budget planning
        - Revenue analysis
        - Financial reporting
        You can read financial documents.""",
        tools=[read_tool],
    )

    print("\nArtist Management System - 3 Specialized Roles")
    print("-" * 60)

    # Simulate workflow
    print("\n[Artist Manager] Planning career strategy...")
    print("  ✓ Can read and update artist profiles")

    print("\n[Booking Agent] Finding performance opportunities...")
    print("  ✓ Can read artist info and search venues online")

    print("\n[Financial Advisor] Analyzing revenue...")
    print("  ✓ Can read financial documents (read-only)")

    print("\nRole capabilities:")
    for role in agent.list_roles():
        print(f"\n{role['name']}:")
        print(f"  Tools: {', '.join(role['tools'])}")
        print(f"  Description: {role['system_prompt'][:80]}...")


def example_7_role_management_api():
    """Example 7: Complete role management API."""
    print("\n" + "=" * 60)
    print("Example 7: Role Management API")
    print("=" * 60)

    workspace = Path.cwd()
    model = create_model("claude-3-5-sonnet-20241022")
    tools = [ReadFileTool(workspace=workspace)]

    agent = Agent(model=model, tools=tools, workspace=workspace)

    # Add roles
    print("\nAdding roles...")
    agent.add_role("role1", "First role", tools=[])
    agent.add_role("role2", "Second role", tools=[])
    agent.add_role("role3", "Third role", tools=[])
    print(f"  Added 3 roles")

    # List roles
    print("\nListing roles...")
    roles = agent.list_roles()
    print(f"  Total roles: {len(roles)}")
    for role in roles:
        print(f"    - {role['name']}")

    # Get specific role
    print("\nGetting specific role...")
    role = agent.get_role("role2")
    print(f"  Found: {role.name}")

    # Remove role
    print("\nRemoving role...")
    agent.remove_role("role2")
    print(f"  Removed 'role2'")
    print(f"  Remaining roles: {len(agent.list_roles())}")

    # Try to remove non-existent role
    print("\nTrying to remove non-existent role...")
    try:
        agent.remove_role("nonexistent")
    except ValueError as e:
        print(f"  ✓ Error caught: {e}")


if __name__ == "__main__":
    print("Motoko Role Management Examples")
    print("=" * 60)
    print()
    print("Demonstrating role switching and multi-role collaboration.")
    print()
    print("Note: Some examples require API keys:")
    print("  - ANTHROPIC_API_KEY for Claude")
    print()
    print("Running examples...\n")

    try:
        # Example 1: Basic role switching (requires API)
        # example_1_basic_role_switching()

        # Example 2: Multi-role collaboration (requires API)
        # example_2_multi_role_collaboration()

        # Example 3: Role-specific tool access (no API needed for demo)
        example_3_role_specific_tool_access()

        # Example 4: Streaming with roles (requires API)
        # example_4_streaming_with_roles()

        # Example 5: Role state tracking (no API needed)
        example_5_role_state_tracking()

        # Example 6: Real-world scenario (no API needed for demo)
        example_6_artist_management_workflow()

        # Example 7: Role management API (no API needed)
        example_7_role_management_api()

        print("\n" + "=" * 60)
        print("Examples complete!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError running examples: {e}")
        print("\nMake sure you:")
        print("  1. Have the required API keys set")
        print("  2. Are running from the motoko project root")
