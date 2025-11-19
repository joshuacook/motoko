"""Example of the agent loop with tool calling."""

import os
from pathlib import Path

from motoko import (
    Agent,
    ReadFileTool,
    WriteFileTool,
    GlobTool,
    GitStatusTool,
    create_model,
)

# Set up workspace
workspace = Path("/Users/joshuacook/working/motoko")

# Create tools
tools = [
    ReadFileTool(workspace=workspace),
    WriteFileTool(workspace=workspace),
    GlobTool(workspace=workspace),
    GitStatusTool(workspace=workspace),
]

# Create model (requires API key)
model = create_model("claude-3-5-sonnet-20241022")

# Create agent
agent = Agent(
    model=model,
    tools=tools,
    workspace=workspace,
)

print("=== Agent Loop Example ===\n")
print("Agent will use tools to answer questions about the codebase.\n")

# Example 1: Simple question that needs tools
print("Example 1: Finding Python files")
print("-" * 50)

response = agent.chat(
    message="How many Python files are in the motoko package?",
    system_prompt="You are a helpful coding assistant. Use tools to answer questions accurately.",
)

print(f"Agent: {response.text}")
print(f"Iterations: Used tools {response.metadata.get('iterations', 'N/A')} times")
print()

# Example 2: Multi-step task
print("Example 2: Reading and analyzing code")
print("-" * 50)

response = agent.chat(
    message="What does the Agent class in motoko/agent.py do? Read the file and summarize.",
    system_prompt="You are a helpful coding assistant.",
)

print(f"Agent: {response.text}")
print()

# Example 3: Creating a file
print("Example 3: Creating a file")
print("-" * 50)

response = agent.chat(
    message="Create a file called 'test_agent_output.txt' with a greeting message.",
    system_prompt="You are a helpful assistant.",
)

print(f"Agent: {response.text}")
print()

# Example 4: Multiple tools in sequence
print("Example 4: Checking git status")
print("-" * 50)

response = agent.chat(
    message="What is the current git status of this repository?",
    system_prompt="You are a helpful assistant.",
)

print(f"Agent: {response.text}")
print()

# Clean up
test_file = workspace / "test_agent_output.txt"
if test_file.exists():
    os.remove(test_file)
    print("Cleaned up test file")

print("\n=== Agent Loop Statistics ===")
print(f"Final conversation length: {len(agent.messages)} messages")
print(f"Tool registry: {len(agent.tools)} tools available")
