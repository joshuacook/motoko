"""Custom tools for Major agent using Claude Agent SDK."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

import yaml
import frontmatter
from claude_agent_sdk import tool, create_sdk_mcp_server

logger = logging.getLogger("major.tools")


def create_major_tools(workspace_path: str):
    """Create Major custom tools for the given workspace.

    Args:
        workspace_path: Root path of the workspace

    Returns:
        SDK MCP server with all tools
    """
    workspace = Path(workspace_path).resolve()
    reports_dir = workspace / "reports"
    skills_dir = workspace / ".claude" / "skills"

    @tool(
        name="generate_report",
        description=(
            "Generate a report by running a skill. "
            "The skill will be executed and its output saved as a dated report file. "
            "Use this when the user asks you to generate or run a report."
        ),
        input_schema={
            "skill_name": str,
            "instructions": str,
        }
    )
    async def generate_report(args: dict[str, Any]) -> dict:
        """Generate a report by running a skill.

        This tool:
        1. Looks up the skill by name
        2. Returns the skill content for the agent to execute
        3. Expects the caller to save the output via save_report tool

        The actual skill execution happens in the parent agent context.
        This tool prepares the skill for execution.
        """
        try:
            skill_name = args["skill_name"]
            instructions = args.get("instructions", "")

            # Find the skill file - skills are in directories: {skill_name}/SKILL.md
            skill_file = skills_dir / skill_name / "SKILL.md"
            if not skill_file.exists():
                # Try legacy flat file format
                skill_file = skills_dir / f"{skill_name}.md"
            if not skill_file.exists():
                # Try with report suffix
                skill_file = skills_dir / f"{skill_name}-report.md"

            if not skill_file.exists():
                # List available skills (directories with SKILL.md)
                available = []
                if skills_dir.exists():
                    for d in skills_dir.iterdir():
                        if d.is_dir() and (d / "SKILL.md").exists():
                            available.append(d.name)
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Error: Skill '{skill_name}' not found. Available skills: {', '.join(sorted(available)) or '(none)'}"
                    }]
                }

            # Load skill content
            post = frontmatter.load(skill_file)
            skill_content = post.content
            skill_metadata = dict(post.metadata)

            # Build report type from skill name
            report_type = skill_name.replace("_", "-")
            if report_type.endswith("-report"):
                report_type = report_type[:-7]  # Remove -report suffix

            today = date.today().isoformat()

            return {
                "content": [{
                    "type": "text",
                    "text": (
                        f"# Report Generation: {skill_name}\n\n"
                        f"**Report Type:** {report_type}\n"
                        f"**Date:** {today}\n"
                        f"**Instructions:** {instructions or '(none provided)'}\n\n"
                        f"## Skill Content\n\n{skill_content}\n\n"
                        f"---\n\n"
                        f"Execute this skill and save the output using the reports MCP server's "
                        f"`save_report` tool with report_type='{report_type}'."
                    )
                }]
            }
        except Exception as e:
            logger.exception(f"Error in generate_report: {e}")
            return {"content": [{"type": "text", "text": f"Error: {e}"}]}

    @tool(
        name="list_skills",
        description="List available skills that can be used for report generation.",
        input_schema={}
    )
    async def list_skills(args: dict[str, Any]) -> dict:
        """List available skills in the workspace."""
        try:
            if not skills_dir.exists():
                return {
                    "content": [{
                        "type": "text",
                        "text": "No skills directory found at .claude/skills/"
                    }]
                }

            skills = []
            # Skills are in directories: {skill_name}/SKILL.md
            for skill_dir in sorted(skills_dir.iterdir()):
                if not skill_dir.is_dir():
                    continue
                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue
                try:
                    post = frontmatter.load(skill_file)
                    title = post.get("title", skill_dir.name)
                    description = post.get("description", "")
                    skills.append({
                        "name": skill_dir.name,
                        "title": title,
                        "description": description[:100] + "..." if len(description) > 100 else description,
                    })
                except Exception:
                    skills.append({
                        "name": skill_dir.name,
                        "title": skill_dir.name,
                        "description": "(failed to load metadata)",
                    })

            if not skills:
                return {
                    "content": [{
                        "type": "text",
                        "text": "No skills found in .claude/skills/"
                    }]
                }

            lines = ["# Available Skills\n"]
            for skill in skills:
                lines.append(f"- **{skill['name']}**: {skill['title']}")
                if skill['description']:
                    lines.append(f"  {skill['description']}")

            return {
                "content": [{
                    "type": "text",
                    "text": "\n".join(lines)
                }]
            }
        except Exception as e:
            logger.exception(f"Error in list_skills: {e}")
            return {"content": [{"type": "text", "text": f"Error: {e}"}]}

    schema_path = workspace / ".claude" / "schema.yaml"

    @tool(
        name="get_workflow",
        description=(
            "Get the current production workflow for this workspace. "
            "Returns the ordered list of entity types that define the knowledge production pipeline. "
            "Returns null if no workflow is configured."
        ),
        input_schema={}
    )
    async def get_workflow(args: dict[str, Any]) -> dict:
        """Get the current workflow from schema.yaml."""
        try:
            if not schema_path.exists():
                return {"content": [{"type": "text", "text": "No schema.yaml found — workflow not configured."}]}

            data = yaml.safe_load(schema_path.read_text()) or {}
            workflow = data.get("workflow")
            if not workflow or not isinstance(workflow, list):
                return {"content": [{"type": "text", "text": "No workflow configured in schema.yaml."}]}

            lines = ["# Current Workflow\n"]
            for i, stage in enumerate(workflow, 1):
                entity = data.get("entities", {}).get(stage, {})
                desc = entity.get("description", "")
                lines.append(f"{i}. **{stage}**{f' — {desc}' if desc else ''}")

            return {"content": [{"type": "text", "text": "\n".join(lines)}]}
        except Exception as e:
            logger.exception(f"Error in get_workflow: {e}")
            return {"content": [{"type": "text", "text": f"Error: {e}"}]}

    @tool(
        name="update_workflow",
        description=(
            "Update the production workflow order. "
            "Provide the new ordered list of entity type names. "
            "All names must be valid entity types defined in the schema. "
            "Use this when the user wants to reorder, add, or remove stages from the pipeline."
        ),
        input_schema={
            "workflow": list[str],
        }
    )
    async def update_workflow(args: dict[str, Any]) -> dict:
        """Update the workflow in schema.yaml."""
        try:
            if not schema_path.exists():
                return {"content": [{"type": "text", "text": "Error: No schema.yaml found."}]}

            new_workflow = args.get("workflow", [])
            if not new_workflow or not isinstance(new_workflow, list):
                return {"content": [{"type": "text", "text": "Error: workflow must be a non-empty list of entity type names."}]}

            data = yaml.safe_load(schema_path.read_text()) or {}
            entity_names = set(data.get("entities", {}).keys())

            invalid = [w for w in new_workflow if w not in entity_names]
            if invalid:
                return {"content": [{"type": "text", "text": f"Error: Invalid entity types: {invalid}. Valid types: {sorted(entity_names)}"}]}

            data["workflow"] = new_workflow
            schema_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True))

            return {"content": [{"type": "text", "text": f"Workflow updated: {' → '.join(new_workflow)}"}]}
        except Exception as e:
            logger.exception(f"Error in update_workflow: {e}")
            return {"content": [{"type": "text", "text": f"Error: {e}"}]}

    # Create and return the SDK MCP server
    return create_sdk_mcp_server(
        name="major-tools",
        version="0.1.0",
        tools=[generate_report, list_skills, get_workflow, update_workflow]
    )
