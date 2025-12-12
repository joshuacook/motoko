"""Tachikoma prompts - loads from skills if available, falls back to embedded."""

from pathlib import Path

# Skill locations to check (in order of preference)
SKILL_LOCATIONS = [
    Path(__file__).parent.parent.parent.parent.parent / ".claude" / "skills",  # Project skills (motoko/.claude/skills)
    Path.home() / ".claude" / "skills",  # Personal skills
]


def load_skill_prompt(skill_name: str) -> str | None:
    """Load prompt from a skill's SKILL.md file.

    Args:
        skill_name: Name of the skill directory (e.g., 'tachikoma-schema')

    Returns:
        The skill content (without frontmatter) or None if not found
    """
    for skills_dir in SKILL_LOCATIONS:
        skill_path = skills_dir / skill_name / "SKILL.md"
        if skill_path.exists():
            content = skill_path.read_text()
            # Strip YAML frontmatter if present
            if content.startswith("---"):
                # Find the closing ---
                end = content.find("---", 3)
                if end != -1:
                    content = content[end + 3:].strip()
            return content
    return None


def get_prompt(cleanup_mode: str) -> str:
    """Get the prompt for a cleanup mode.

    Tries to load from skills first, falls back to embedded prompts.

    Args:
        cleanup_mode: One of 'schema', 'frontmatter', 'structure'

    Returns:
        The prompt string
    """
    skill_name = f"tachikoma-{cleanup_mode}"

    # Try loading from skill
    skill_prompt = load_skill_prompt(skill_name)
    if skill_prompt:
        return skill_prompt

    # Fall back to embedded prompts
    from .schema import SCHEMA_CLEANUP_PROMPT
    from .frontmatter import FRONTMATTER_CLEANUP_PROMPT
    from .structure import STRUCTURE_CLEANUP_PROMPT

    fallback = {
        "schema": SCHEMA_CLEANUP_PROMPT,
        "frontmatter": FRONTMATTER_CLEANUP_PROMPT,
        "structure": STRUCTURE_CLEANUP_PROMPT,
    }

    if cleanup_mode not in fallback:
        raise ValueError(f"Unknown cleanup mode: {cleanup_mode}")

    return fallback[cleanup_mode]


class PromptDict(dict):
    """Dict-like object that lazily loads prompts from skills."""

    def __getitem__(self, key):
        return get_prompt(key)

    def __contains__(self, key):
        return key in ["schema", "frontmatter", "structure"]

    def keys(self):
        return ["schema", "frontmatter", "structure"]


PROMPTS = PromptDict()

# For backwards compatibility
from .schema import SCHEMA_CLEANUP_PROMPT
from .frontmatter import FRONTMATTER_CLEANUP_PROMPT
from .structure import STRUCTURE_CLEANUP_PROMPT

__all__ = ["PROMPTS", "SCHEMA_CLEANUP_PROMPT", "FRONTMATTER_CLEANUP_PROMPT", "STRUCTURE_CLEANUP_PROMPT", "get_prompt"]
