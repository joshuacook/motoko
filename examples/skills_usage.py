"""Skills usage examples.

This example demonstrates how to use the Skills framework with motoko.
Skills are reusable capabilities defined in markdown files with YAML frontmatter.
"""

from pathlib import Path

from motoko import Agent, create_model, ReadFileTool, GlobTool, GrepTool


def example_1_basic_skill_usage():
    """Example 1: Basic skill invocation."""
    print("=" * 60)
    print("Example 1: Basic Skill Usage")
    print("=" * 60)

    # Create agent with tools and skills directory
    workspace = Path.cwd()
    skills_dir = workspace / "skills"

    model = create_model("claude-3-5-sonnet-20241022")
    tools = [
        ReadFileTool(workspace=workspace),
        GlobTool(workspace=workspace),
        GrepTool(workspace=workspace),
    ]

    agent = Agent(
        model=model, tools=tools, workspace=workspace, skills_dir=skills_dir
    )

    # List available skills
    print("\nAvailable skills:")
    for skill in agent.list_skills():
        print(f"  - {skill['name']}: {skill['description']}")

    # Invoke a skill with parameters
    print("\n\nInvoking 'summarize-file' skill...")
    response = agent.invoke_skill(
        skill_name="summarize-file",
        file_path="motoko/agent.py",
        detail_level="medium",
        system_prompt="You are a helpful code documentation assistant.",
    )

    print("\nResponse:")
    print(response.text)


def example_2_code_review_skill():
    """Example 2: Using the code-review skill."""
    print("\n" + "=" * 60)
    print("Example 2: Code Review Skill")
    print("=" * 60)

    workspace = Path.cwd()
    skills_dir = workspace / "skills"

    model = create_model("gemini-2.0-flash-exp")  # Try with Gemini
    tools = [
        ReadFileTool(workspace=workspace),
        GlobTool(workspace=workspace),
    ]

    agent = Agent(model=model, tools=tools, workspace=workspace, skills_dir=skills_dir)

    print("\nInvoking 'code-review' skill on Python files...")
    response = agent.invoke_skill(
        skill_name="code-review",
        file_pattern="motoko/tools/*.py",
        focus="best practices and security",
        system_prompt="You are an expert Python code reviewer.",
    )

    print("\nReview Results:")
    print(response.text)


def example_3_search_and_explain():
    """Example 3: Search and explain patterns in code."""
    print("\n" + "=" * 60)
    print("Example 3: Search and Explain Skill")
    print("=" * 60)

    workspace = Path.cwd()
    skills_dir = workspace / "skills"

    model = create_model("claude-3-5-sonnet-20241022")
    tools = [
        ReadFileTool(workspace=workspace),
        GrepTool(workspace=workspace),
    ]

    agent = Agent(model=model, tools=tools, workspace=workspace, skills_dir=skills_dir)

    print("\nSearching for 'BaseModel' pattern and explaining usage...")
    response = agent.invoke_skill(
        skill_name="search-and-explain",
        pattern="BaseModel",
        file_pattern="**/*.py",
        context="Understanding the model abstraction pattern",
        system_prompt="You are an expert at explaining code architecture.",
    )

    print("\nExplanation:")
    print(response.text)


def example_4_streaming_skill():
    """Example 4: Using skills with streaming."""
    import asyncio

    print("\n" + "=" * 60)
    print("Example 4: Streaming Skill Invocation")
    print("=" * 60)

    async def run_streaming():
        workspace = Path.cwd()
        skills_dir = workspace / "skills"

        model = create_model("claude-3-5-sonnet-20241022")
        tools = [
            ReadFileTool(workspace=workspace),
            GlobTool(workspace=workspace),
            GrepTool(workspace=workspace),
        ]

        agent = Agent(
            model=model, tools=tools, workspace=workspace, skills_dir=skills_dir
        )

        print("\nStreaming 'refactor-suggestions' skill...")
        print("-" * 60)

        async for event in agent.invoke_skill_stream(
            skill_name="refactor-suggestions",
            target="motoko/agent.py",
            focus="complexity",
            system_prompt="You are a software architect specializing in clean code.",
        ):
            if event.type == "text_chunk":
                print(event.data, end="", flush=True)
            elif event.type == "tool_start":
                print(f"\n[Using tool: {event.data.name}]", flush=True)
            elif event.type == "tool_end":
                if event.data.is_error:
                    print(f"\n[Tool error: {event.data.content}]", flush=True)
            elif event.type == "done":
                print("\n" + "-" * 60)
                print("Stream complete!")

    asyncio.run(run_streaming())


def example_5_custom_skills_directory():
    """Example 5: Loading skills from multiple directories."""
    print("\n" + "=" * 60)
    print("Example 5: Custom Skills Directory")
    print("=" * 60)

    workspace = Path.cwd()
    default_skills = workspace / "skills"
    custom_skills = workspace / "my_custom_skills"  # Your own skills

    model = create_model("claude-3-5-sonnet-20241022")
    tools = [ReadFileTool(workspace=workspace)]

    # Load from default directory
    agent = Agent(
        model=model, tools=tools, workspace=workspace, skills_dir=default_skills
    )

    # Add additional skills directory
    if custom_skills.exists():
        agent.skill_loader.add_skill_directory(custom_skills)

    print("\nLoaded skills from multiple directories:")
    for skill in agent.list_skills():
        print(f"  - {skill['name']}: {skill['description']}")


def example_6_skill_validation():
    """Example 6: Skill validation."""
    print("\n" + "=" * 60)
    print("Example 6: Skill Validation")
    print("=" * 60)

    workspace = Path.cwd()
    skills_dir = workspace / "skills"

    # Create agent with limited tools
    model = create_model("claude-3-5-sonnet-20241022")
    tools = [ReadFileTool(workspace=workspace)]  # Only ReadFileTool

    agent = Agent(model=model, tools=tools, workspace=workspace, skills_dir=skills_dir)

    print("\nAgent has tools:", [tool.name for tool in agent.tools])

    # Try to invoke a skill that requires GrepTool
    try:
        print("\nAttempting to invoke 'search-and-explain' (requires GrepTool)...")
        response = agent.invoke_skill(
            skill_name="search-and-explain", pattern="test", context="testing"
        )
    except ValueError as e:
        print(f"❌ Validation failed: {e}")
        print("\nThis is expected - skill requires tools we don't have!")

    # Invoke a skill that works with available tools
    print("\nInvoking 'summarize-file' (only requires ReadFileTool)...")
    try:
        response = agent.invoke_skill(
            skill_name="summarize-file",
            file_path="README.md",
            detail_level="low",
        )
        print("✓ Success! Skill executed.")
        print("\nSummary:")
        print(response.text[:200] + "...")
    except ValueError as e:
        print(f"❌ Error: {e}")


def example_7_reload_skills():
    """Example 7: Reloading skills during development."""
    print("\n" + "=" * 60)
    print("Example 7: Reloading Skills")
    print("=" * 60)

    workspace = Path.cwd()
    skills_dir = workspace / "skills"

    model = create_model("claude-3-5-sonnet-20241022")
    tools = [ReadFileTool(workspace=workspace)]

    agent = Agent(model=model, tools=tools, workspace=workspace, skills_dir=skills_dir)

    print(f"\nInitially loaded {len(agent.skill_loader)} skills")

    # During development, you might modify skill files
    print("\n[Imagine you edited a skill file...]")

    # Reload skills to pick up changes
    agent.reload_skills()
    print(f"After reload: {len(agent.skill_loader)} skills")
    print("\nSkills are now up to date with disk!")


if __name__ == "__main__":
    print("Motoko Skills Framework Examples")
    print("=" * 60)
    print()
    print("These examples demonstrate the Skills framework.")
    print("Skills are reusable capabilities defined in markdown files.")
    print()
    print("Note: These examples require API keys:")
    print("  - ANTHROPIC_API_KEY for Claude")
    print("  - GOOGLE_API_KEY for Gemini")
    print()
    print("Running examples...\n")

    # Run examples that don't require API calls
    try:
        # Example 1: Basic usage (requires API)
        # example_1_basic_skill_usage()

        # Example 2: Code review (requires API)
        # example_2_code_review_skill()

        # Example 3: Search and explain (requires API)
        # example_3_search_and_explain()

        # Example 4: Streaming (requires API)
        # example_4_streaming_skill()

        # Example 5: Custom skills directory (no API needed)
        example_5_custom_skills_directory()

        # Example 6: Validation (no API needed if skill fails validation)
        example_6_skill_validation()

        # Example 7: Reload skills (no API needed)
        example_7_reload_skills()

        print("\n" + "=" * 60)
        print("Examples complete!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError running examples: {e}")
        print("\nMake sure you:")
        print("  1. Have the required API keys set")
        print("  2. Have the skills directory with skill files")
        print("  3. Are running from the motoko project root")
