"""Report tools for file operations."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

import frontmatter


class ReportTools:
    """Tools for report storage and retrieval.

    Reports are stored as:
        /reports/{report_type}/{YYYY-MM-DD}.md

    Each report has optional frontmatter with metadata.
    """

    def __init__(self, workspace_path: str):
        """Initialize with workspace path."""
        self.workspace = Path(workspace_path)
        self.reports_dir = self.workspace / "reports"

    def list_reports(
        self,
        report_type: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List available report types and their versions.

        Args:
            report_type: Optional filter to specific report type
            limit: Maximum versions to return per type

        Returns:
            Dict with report types and their available dates
        """
        if not self.reports_dir.exists():
            return {
                "success": True,
                "report_types": [],
                "message": "No reports directory found",
            }

        results = []

        # Get report type directories
        type_dirs = [self.reports_dir / report_type] if report_type else list(self.reports_dir.iterdir())

        for type_dir in type_dirs:
            if not type_dir.is_dir() or type_dir.name.startswith("."):
                continue

            # Get all report files sorted by date (newest first)
            report_files = sorted(
                type_dir.glob("*.md"),
                key=lambda p: p.stem,
                reverse=True,
            )[:limit]

            dates = [f.stem for f in report_files]

            # Get metadata from latest report if exists
            metadata = {}
            if report_files:
                try:
                    post = frontmatter.load(report_files[0])
                    metadata = {
                        "title": post.get("title", type_dir.name),
                        "description": post.get("description", ""),
                        "skill_name": post.get("skill_name", type_dir.name),
                    }
                except Exception:
                    metadata = {"title": type_dir.name}

            results.append({
                "type": type_dir.name,
                "dates": dates,
                "count": len(dates),
                "latest": dates[0] if dates else None,
                **metadata,
            })

        return {
            "success": True,
            "report_types": results,
            "total_types": len(results),
        }

    def get_report(
        self,
        report_type: str,
        report_date: str | None = None,
    ) -> dict[str, Any]:
        """Get a specific report.

        Args:
            report_type: Report type (directory name)
            report_date: Date string (YYYY-MM-DD). If None, returns latest.

        Returns:
            Dict with report content and metadata
        """
        type_dir = self.reports_dir / report_type

        if not type_dir.exists():
            return {
                "success": False,
                "error": f"Report type '{report_type}' not found",
            }

        # Find the report file
        if report_date:
            report_file = type_dir / f"{report_date}.md"
        else:
            # Get latest
            report_files = sorted(type_dir.glob("*.md"), reverse=True)
            if not report_files:
                return {
                    "success": False,
                    "error": f"No reports found for type '{report_type}'",
                }
            report_file = report_files[0]

        if not report_file.exists():
            return {
                "success": False,
                "error": f"Report not found: {report_type}/{report_date}",
            }

        try:
            post = frontmatter.load(report_file)
            return {
                "success": True,
                "type": report_type,
                "date": report_file.stem,
                "content": post.content,
                "metadata": dict(post.metadata),
                "path": str(report_file.relative_to(self.workspace)),
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read report: {e}",
            }

    def save_report(
        self,
        report_type: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        report_date: str | None = None,
    ) -> dict[str, Any]:
        """Save a report.

        Args:
            report_type: Report type (directory name)
            content: Markdown content
            metadata: Optional frontmatter metadata
            report_date: Optional date (defaults to today)

        Returns:
            Dict with save confirmation
        """
        type_dir = self.reports_dir / report_type
        type_dir.mkdir(parents=True, exist_ok=True)

        # Use provided date or today
        if report_date:
            file_date = report_date
        else:
            file_date = date.today().isoformat()

        report_file = type_dir / f"{file_date}.md"

        # Build frontmatter
        fm_metadata = metadata or {}
        if "title" not in fm_metadata:
            fm_metadata["title"] = report_type.replace("-", " ").title()
        if "skill_name" not in fm_metadata:
            fm_metadata["skill_name"] = report_type
        fm_metadata["generated_at"] = file_date

        # Create frontmatter post
        post = frontmatter.Post(content, **fm_metadata)

        try:
            with open(report_file, "w") as f:
                f.write(frontmatter.dumps(post))

            return {
                "success": True,
                "type": report_type,
                "date": file_date,
                "path": str(report_file.relative_to(self.workspace)),
                "message": f"Report saved to {report_file.relative_to(self.workspace)}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to save report: {e}",
            }

    def compare_reports(
        self,
        report_type: str,
        date1: str,
        date2: str,
    ) -> dict[str, Any]:
        """Compare two reports of the same type.

        Args:
            report_type: Report type
            date1: First date (YYYY-MM-DD)
            date2: Second date (YYYY-MM-DD)

        Returns:
            Dict with both report contents for comparison
        """
        report1 = self.get_report(report_type, date1)
        if not report1.get("success"):
            return report1

        report2 = self.get_report(report_type, date2)
        if not report2.get("success"):
            return report2

        return {
            "success": True,
            "type": report_type,
            "report1": {
                "date": date1,
                "content": report1["content"],
                "metadata": report1["metadata"],
            },
            "report2": {
                "date": date2,
                "content": report2["content"],
                "metadata": report2["metadata"],
            },
        }

    def get_recent_reports(
        self,
        report_type: str,
        count: int = 4,
    ) -> dict[str, Any]:
        """Get the N most recent reports of a type.

        Args:
            report_type: Report type
            count: Number of reports to return

        Returns:
            Dict with list of recent reports
        """
        type_dir = self.reports_dir / report_type

        if not type_dir.exists():
            return {
                "success": False,
                "error": f"Report type '{report_type}' not found",
            }

        report_files = sorted(type_dir.glob("*.md"), reverse=True)[:count]

        reports = []
        for report_file in report_files:
            try:
                post = frontmatter.load(report_file)
                reports.append({
                    "date": report_file.stem,
                    "content": post.content,
                    "metadata": dict(post.metadata),
                })
            except Exception as e:
                reports.append({
                    "date": report_file.stem,
                    "error": str(e),
                })

        return {
            "success": True,
            "type": report_type,
            "count": len(reports),
            "reports": reports,
        }
