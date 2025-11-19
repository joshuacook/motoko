"""Skill definition and execution."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Skill:
    """A reusable capability that can be invoked by the agent.

    Skills are specialized prompts with optional tool access and parameters.
    They provide pre-defined behaviors that can be invoked by name.
    """

    name: str
    description: str
    instructions: str
    tools: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_markdown(cls, path: Path) -> "Skill":
        """Load skill from markdown file with YAML frontmatter.

        Format:
            ---
            name: skill-name
            description: Short description
            tools: [tool1, tool2]
            parameters:
              param1: default_value
            ---

            # Skill Instructions

            Detailed instructions for the skill...

        Args:
            path: Path to skill markdown file

        Returns:
            Skill instance
        """
        content = path.read_text()

        # Parse frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                instructions = parts[2].strip()
            else:
                raise ValueError(f"Invalid skill format in {path}")
        else:
            raise ValueError(f"Skill file must start with YAML frontmatter: {path}")

        # Extract fields
        name = frontmatter.get("name", path.stem)
        description = frontmatter.get("description", "")
        tools = frontmatter.get("tools", [])
        parameters = frontmatter.get("parameters", {})
        metadata = frontmatter.get("metadata", {})

        return cls(
            name=name,
            description=description,
            instructions=instructions,
            tools=tools,
            parameters=parameters,
            metadata=metadata,
        )

    def format_prompt(self, **kwargs: Any) -> str:
        """Format skill instructions with parameters.

        Args:
            **kwargs: Parameter values to substitute

        Returns:
            Formatted instructions
        """
        # Merge default parameters with provided ones
        params = {**self.parameters, **kwargs}

        # Simple template substitution
        prompt = self.instructions
        for key, value in params.items():
            placeholder = f"{{{key}}}"
            prompt = prompt.replace(placeholder, str(value))

        return prompt

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with skill data
        """
        return {
            "name": self.name,
            "description": self.description,
            "instructions": self.instructions,
            "tools": self.tools,
            "parameters": self.parameters,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        """String representation."""
        return f"Skill(name={self.name}, tools={len(self.tools)})"
