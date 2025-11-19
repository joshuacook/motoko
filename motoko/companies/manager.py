"""Company management for motoko workspaces."""

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class CompanyRelationship(Enum):
    """Company relationship type."""

    FOUNDER = "founder"
    CLIENT = "client"
    EMPLOYER = "employer"
    INSTITUTION = "institution"


@dataclass
class Company:
    """Represents a company entity."""

    code: str
    name: str
    relationship: CompanyRelationship
    file_path: Path
    industry: str | None = None
    website: str | None = None
    content: str | None = None


class CompanyManager:
    """Manages companies in a motoko workspace."""

    def __init__(self, workspace: Path):
        """Initialize company manager.

        Args:
            workspace: Project workspace directory
        """
        self.workspace = Path(workspace)
        self.companies_dir = self.workspace / "data" / "companies"

    def ensure_companies_dir(self) -> None:
        """Create companies directory if it doesn't exist."""
        self.companies_dir.mkdir(parents=True, exist_ok=True)

    def _validate_code(self, code: str) -> bool:
        """Validate company CODE format.

        Args:
            code: Company CODE

        Returns:
            True if valid
        """
        # Must be uppercase letters, numbers, and underscores only
        return bool(re.match(r"^[A-Z0-9_]+$", code))

    def list_companies(self) -> list[Company]:
        """List companies in the workspace.

        Returns:
            List of Company objects, sorted by code
        """
        if not self.companies_dir.exists():
            return []

        companies = []
        for file_path in self.companies_dir.glob("*.md"):
            code = file_path.stem

            # Read file to get metadata
            try:
                content = file_path.read_text()

                # Parse frontmatter
                import yaml

                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        fm = yaml.safe_load(parts[1])
                        companies.append(
                            Company(
                                code=code,
                                name=fm.get("name", code),
                                relationship=CompanyRelationship(fm.get("relationship", "client")),
                                industry=fm.get("industry"),
                                website=fm.get("website"),
                                file_path=file_path,
                            )
                        )
            except Exception:
                # Skip files with parse errors
                continue

        # Sort by code
        companies.sort(key=lambda c: c.code)
        return companies

    def get_company(self, code: str, load_content: bool = True) -> Company | None:
        """Get a specific company by code.

        Args:
            code: Company CODE
            load_content: Whether to load file content

        Returns:
            Company object or None if not found
        """
        file_path = self.companies_dir / f"{code.upper()}.md"
        if not file_path.exists():
            return None

        try:
            content = file_path.read_text()

            # Parse frontmatter
            import yaml

            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    fm = yaml.safe_load(parts[1])
                    company = Company(
                        code=code.upper(),
                        name=fm.get("name", code),
                        relationship=CompanyRelationship(fm.get("relationship", "client")),
                        industry=fm.get("industry"),
                        website=fm.get("website"),
                        file_path=file_path,
                        content=content if load_content else None,
                    )
                    return company
        except Exception:
            return None

        return None

    def create_company(
        self,
        code: str,
        name: str,
        relationship: CompanyRelationship,
        industry: str | None = None,
        website: str | None = None,
        description: str = "",
    ) -> Company:
        """Create a new company.

        Args:
            code: Company CODE (uppercase)
            name: Company name
            relationship: Relationship type
            industry: Industry
            website: Website URL
            description: Company description

        Returns:
            Created Company object
        """
        self.ensure_companies_dir()

        # Validate code
        code = code.upper()
        if not self._validate_code(code):
            raise ValueError(f"Invalid company CODE: {code}. Must be uppercase letters, numbers, and underscores.")

        # Check if already exists
        file_path = self.companies_dir / f"{code}.md"
        if file_path.exists():
            raise ValueError(f"Company {code} already exists")

        # Build frontmatter
        fm_parts = [
            f"code: {code}",
            f"name: {name}",
            f"relationship: {relationship.value}",
        ]
        if industry:
            fm_parts.append(f"industry: {industry}")
        if website:
            fm_parts.append(f"website: {website}")

        # Build content
        content = "---\n" + "\n".join(fm_parts) + "\n---\n\n"
        if description:
            content += description
        else:
            content += f"# {name}\n\n## Background\n\n## Relationship Context\n\n## Key People\n\n"

        # Write file
        file_path.write_text(content)

        # Auto-commit
        self._auto_commit(file_path, f"Create company {code}: {name}")

        return Company(
            code=code,
            name=name,
            relationship=relationship,
            industry=industry,
            website=website,
            file_path=file_path,
            content=content,
        )

    def update_company(
        self,
        code: str,
        name: str | None = None,
        industry: str | None = None,
        website: str | None = None,
    ) -> Company | None:
        """Update company metadata.

        Args:
            code: Company CODE
            name: New name
            industry: New industry
            website: New website

        Returns:
            Updated Company or None if not found
        """
        company = self.get_company(code, load_content=True)
        if not company or not company.content:
            return None

        # Parse and update frontmatter
        import yaml

        parts = company.content.split("---", 2)
        if len(parts) >= 3:
            fm = yaml.safe_load(parts[1])

            if name:
                fm["name"] = name
                company.name = name
            if industry:
                fm["industry"] = industry
                company.industry = industry
            if website:
                fm["website"] = website
                company.website = website

            # Rebuild content
            new_fm = yaml.dump(fm, default_flow_style=False, sort_keys=False)
            new_content = f"---\n{new_fm}---{parts[2]}"

            # Write file
            company.file_path.write_text(new_content)

            # Auto-commit
            self._auto_commit(company.file_path, f"Update company {code}")

            company.content = new_content
            return company

        return None

    def _auto_commit(self, file_path: Path, commit_message: str) -> None:
        """Auto-commit a file to git.

        Args:
            file_path: Path to file to commit
            commit_message: Git commit message
        """
        import subprocess

        try:
            # Add file to git
            subprocess.run(
                ["git", "add", str(file_path)],
                cwd=self.workspace,
                check=True,
                capture_output=True,
            )

            # Commit with message
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=self.workspace,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError:
            # Git command failed - silently continue
            pass
