"""System prompt building for Major agent."""

from pathlib import Path


DEFAULT_SYSTEM_PROMPT = """## Motoko: Knowledge Production Platform

You are Motoko, an AI assistant for producing and organizing knowledge. Unlike coding assistants that write software, your purpose is to help users create, structure, and evolve knowledge - always in markdown.

Your output is knowledge: structured entities (tasks, projects, journal entries, roles) and unstructured documents. Everything lives in the Context Lake.

## Context Lake

The Context Lake is a structured collection of markdown entities that serves as persistent memory and context. This is fundamental to how this application works.

### Structure

The workspace contains:
- **Root files**: README.md, key documentation
- **roles/**: Role definitions that shape how you approach tasks
- **docs/**: Documentation and reference materials
- **lake/**: Entity directories (tasks, journal, projects, companies, etc.)

### Tools

You have two ways to interact with the Context Lake:

1. **batou** (MCP server) - The ONLY way to create or modify entities. Use for:
   - Listing entity types and entities
   - Creating, reading, updating, deleting entities
   - Understanding workspace structure
   - Operations that should be git-committed

2. **Direct file tools** (Read, Glob) - For reading only:
   - Searching for content across files
   - Reading files that aren't entities (README.md, config files)

### CRITICAL: Entity Creation Rules

**ALWAYS use batou's `create_entity` tool to create new content.** NEVER use the Write tool or Bash to create markdown files directly. Files created outside of batou will not have proper frontmatter, won't follow naming conventions, and won't appear in the workspace.

When creating content:
1. Check the schema (`list_entity_types`) to find the right entity type
2. Use `create_entity` with the correct type, title, and content
3. If no entity type fits, ask the user which type to use - do NOT create loose files

**NEVER write .md files directly to the workspace root or any directory.** All content must go through batou's entity system.

### Working with Roles

When a role is loaded or referenced, embody that role's perspective and expertise. Roles are in the `roles/` directory.

## Workspace Boundaries

IMPORTANT: You are restricted to this workspace only. Never:
- Access, read, or reference files outside this workspace
- Navigate to parent directories (../) or sibling workspaces
- Suggest or reference work from other workspaces
- Use absolute paths outside the current workspace

If you become aware of other workspaces, do not mention or suggest work from them. Stay focused on the current workspace's entities and context.

"""


def load_prompt_file(path: Path) -> str | None:
    """Load prompt content from a file if it exists.

    Args:
        path: Path to the prompt file

    Returns:
        File contents if exists, None otherwise
    """
    if path.exists() and path.is_file():
        try:
            return path.read_text()
        except Exception:
            return None
    return None


def build_system_prompt(
    attached_entities: list[dict] | None = None,
    platform_config_path: str | None = None,
    workspace_path: str | None = None,
    source_constraint: list[dict] | None = None,
) -> str:
    """Build system prompt with app-level and workspace-level context.

    Prompt sources (in order):
    1. {platform_config_path}/PROMPT.md - App-level prompt (e.g., Motoko vs Motoko)
    2. Falls back to DEFAULT_SYSTEM_PROMPT if no app prompt
    3. {workspace_path}/CLAUDE.md - Workspace-level context (appended)
    4. Attached entities (appended)

    Args:
        attached_entities: Optional list of attached entity dicts with
            type, id, title, and content fields.
        platform_config_path: Path to platform config directory.
        workspace_path: Path to current workspace.

    Returns:
        Complete system prompt string
    """
    # 1. Try workspace prompt, then platform prompt, fall back to default
    prompt = None
    if workspace_path:
        workspace_prompt_path = Path(workspace_path) / ".claude" / "PROMPT.md"
        prompt = load_prompt_file(workspace_prompt_path)

    if not prompt and platform_config_path:
        app_prompt_path = Path(platform_config_path) / "PROMPT.md"
        prompt = load_prompt_file(app_prompt_path)

    if not prompt:
        prompt = DEFAULT_SYSTEM_PROMPT

    # 2. Append workspace-level context if exists
    if workspace_path:
        workspace_prompt_path = Path(workspace_path) / "CLAUDE.md"
        workspace_context = load_prompt_file(workspace_prompt_path)
        if workspace_context:
            prompt += "\n## Workspace Context\n\n"
            prompt += workspace_context
            prompt += "\n\n"

    # 3. Append source constraint (for source-grounded chat)
    if source_constraint:
        prompt += "## Source-Grounded Chat\n\n"
        prompt += "This conversation is grounded in the following sources. "
        prompt += "Base your answers on these sources and cite them by title when referencing specific information. "
        prompt += "If the user asks about something not covered in these sources, say so.\n\n"

        for source in source_constraint:
            prompt += f"### {source.get('title', 'Untitled')}\n"
            if source.get('content'):
                prompt += f"{source['content']}\n\n"
            prompt += "---\n\n"

    # 4. Append attached entities
    if attached_entities:
        prompt += "## Attached Documents\n\n"
        prompt += "The user has attached the following documents to this session. "
        prompt += "Use these as primary context for the conversation.\n\n"

        for entity in attached_entities:
            prompt += f"### {entity.get('title', 'Untitled')}\n"
            prompt += f"**Type**: {entity.get('type', 'unknown')}\n"
            prompt += f"**Path**: {entity.get('type', 'unknown')}/{entity.get('id', 'unknown')}.md\n\n"
            if entity.get('content'):
                prompt += f"{entity['content']}\n\n"
            prompt += "---\n\n"

    return prompt
