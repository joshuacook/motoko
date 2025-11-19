"""Skill loader and registry."""

import builtins
from pathlib import Path

from .skill import Skill


class SkillLoader:
    """Loads and manages skills from a directory.

    Skills are defined as markdown files with YAML frontmatter.
    The loader discovers all .md files in the skills directory
    and makes them available to agents.
    """

    def __init__(self, skills_dir: Path | None = None):
        """Initialize skill loader.

        Args:
            skills_dir: Directory containing skill files.
                       If None, uses default 'skills' directory.
        """
        self.skills_dir = skills_dir or Path.cwd() / "skills"
        self.skills: dict[str, Skill] = {}
        self._loaded = False

    def load(self, force_reload: bool = False) -> None:
        """Load all skills from the skills directory.

        Args:
            force_reload: If True, reload even if already loaded
        """
        if self._loaded and not force_reload:
            return

        self.skills = {}

        if not self.skills_dir.exists():
            return

        # Find all .md files
        skill_files = list(self.skills_dir.glob("*.md"))

        # Load each skill
        for skill_file in skill_files:
            try:
                skill = Skill.from_markdown(skill_file)
                self.skills[skill.name] = skill
            except Exception as e:
                # Log error but continue loading other skills
                print(f"Warning: Failed to load skill from {skill_file}: {e}")

        self._loaded = True

    def get(self, name: str) -> Skill | None:
        """Get a skill by name.

        Args:
            name: Skill name

        Returns:
            Skill if found, None otherwise
        """
        if not self._loaded:
            self.load()

        return self.skills.get(name)

    def list(self) -> list[Skill]:
        """List all available skills.

        Returns:
            List of all loaded skills
        """
        if not self._loaded:
            self.load()

        return list(self.skills.values())

    def list_names(self) -> builtins.list[str]:
        """List all skill names.

        Returns:
            List of skill names
        """
        if not self._loaded:
            self.load()

        return list(self.skills.keys())

    def validate(self, skill_name: str, available_tools: builtins.list[str]) -> tuple[bool, str]:
        """Validate that a skill can be executed.

        Args:
            skill_name: Name of skill to validate
            available_tools: List of available tool names

        Returns:
            Tuple of (is_valid, error_message)
        """
        skill = self.get(skill_name)

        if not skill:
            return False, f"Skill '{skill_name}' not found"

        # Check if all required tools are available
        missing_tools = []
        for tool_name in skill.tools:
            if tool_name not in available_tools:
                missing_tools.append(tool_name)

        if missing_tools:
            return (
                False,
                f"Skill '{skill_name}' requires tools that are not available: {', '.join(missing_tools)}",
            )

        return True, ""

    def get_skill_definitions(self) -> builtins.list[dict]:
        """Get skill definitions for agent.

        Returns:
            List of skill metadata dictionaries
        """
        if not self._loaded:
            self.load()

        return [
            {
                "name": skill.name,
                "description": skill.description,
                "tools": skill.tools,
                "parameters": skill.parameters,
            }
            for skill in self.skills.values()
        ]

    def reload(self) -> None:
        """Reload all skills from disk."""
        self.load(force_reload=True)

    def add_skill_directory(self, directory: Path) -> None:
        """Add an additional skills directory.

        Args:
            directory: Additional directory to load skills from
        """
        if not directory.exists():
            raise ValueError(f"Skills directory does not exist: {directory}")

        # Load skills from the new directory
        skill_files = list(directory.glob("*.md"))

        for skill_file in skill_files:
            try:
                skill = Skill.from_markdown(skill_file)
                # Only add if not already present (existing skills take precedence)
                if skill.name not in self.skills:
                    self.skills[skill.name] = skill
            except Exception as e:
                print(f"Warning: Failed to load skill from {skill_file}: {e}")

    def __len__(self) -> int:
        """Return number of loaded skills."""
        if not self._loaded:
            self.load()
        return len(self.skills)

    def __contains__(self, skill_name: str) -> bool:
        """Check if a skill is loaded."""
        if not self._loaded:
            self.load()
        return skill_name in self.skills

    def __repr__(self) -> str:
        """String representation."""
        if not self._loaded:
            return f"SkillLoader(dir={self.skills_dir}, loaded=False)"
        return f"SkillLoader(dir={self.skills_dir}, skills={len(self.skills)})"
