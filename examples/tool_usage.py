"""Example of using tools directly (without agent loop)."""

from pathlib import Path

from motoko import (
    BashTool,
    EditFileTool,
    GitStatusTool,
    GlobTool,
    GrepTool,
    ReadFileTool,
    WebFetchTool,
    WriteFileTool,
)

# Set workspace
workspace = Path("/Users/joshuacook/working/motoko")

print("=== File Tools Examples ===\n")

# Example 1: Read a file
print("1. Reading README.md...")
read_tool = ReadFileTool(workspace=workspace)
result = read_tool.execute(file_path="README.md", limit=10)
print(f"Result: {result.summary()}")
print(f"First 10 lines:\n{result.standard()}\n")

# Example 2: Write a file
print("2. Writing test file...")
write_tool = WriteFileTool(workspace=workspace)
result = write_tool.execute(
    file_path="examples/test_output.txt",
    content="Hello from motoko!\nThis is a test file.\n",
)
print(f"Result: {result.content}\n")

# Example 3: Edit a file
print("3. Editing test file...")
edit_tool = EditFileTool(workspace=workspace)
result = edit_tool.execute(
    file_path="examples/test_output.txt",
    old_string="Hello from motoko!",
    new_string="Hello from motoko tools!",
)
print(f"Result: {result.content}\n")

# Example 4: Glob for files
print("4. Finding Python files...")
glob_tool = GlobTool(workspace=workspace)
result = glob_tool.execute(pattern="**/*.py")
files = result.content.split("\n")[:5]
print(f"Found {result.metadata['matches']} Python files")
print(f"First 5:\n" + "\n".join(files) + "\n")

# Example 5: Grep search
print("5. Searching for 'BaseModel'...")
grep_tool = GrepTool(workspace=workspace)
result = grep_tool.execute(pattern="class BaseModel", file_pattern="*.py")
print(f"Found {result.metadata['total_matches']} matches")
print(f"Results:\n{result.standard()}\n")

print("\n=== Web Tools Examples ===\n")

# Example 6: Fetch web content
print("6. Fetching from GitHub API...")
web_tool = WebFetchTool()
result = web_tool.execute(url="https://api.github.com/zen")
print(f"GitHub Zen: {result.content}\n")

print("\n=== Git Tools Examples ===\n")

# Example 7: Git status
print("7. Checking git status...")
git_tool = GitStatusTool(workspace=workspace)
result = git_tool.execute()
print(f"Status:\n{result.content}\n")

print("\n=== Bash Tool Examples ===\n")

# Example 8: Run bash command
print("8. Running bash command...")
bash_tool = BashTool(workspace=workspace)
result = bash_tool.execute(command="ls -la examples/ | head -5")
print(f"Output:\n{result.content}\n")

# Example 9: Verbosity levels
print("\n=== Verbosity Examples ===\n")
result = read_tool.execute(file_path="README.md")

print("Minimal:", result.format("minimal"))
print("\nNormal (truncated):", result.format("normal")[:200] + "...")
print("\nVerbose includes metadata:", "Metadata:" in result.format("verbose"))

# Clean up test file
import os

test_file = workspace / "examples/test_output.txt"
if test_file.exists():
    os.remove(test_file)
    print("\nCleaned up test file")
