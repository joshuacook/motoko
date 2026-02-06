"""Library tools for querying the document index."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Add parent path to find major module
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "major" / "src"))

from major.librarian import LibraryIndex


class LibraryTools:
    """Tools for querying the library document index."""

    def __init__(self, workspace_path: str):
        self.workspace = Path(workspace_path)
        self.index = LibraryIndex(workspace_path)

    def browse_topics(
        self,
        topic_id: str | None = None,
        include_counts: bool = True,
    ) -> dict[str, Any]:
        """Browse library topics.

        Args:
            topic_id: Optional topic ID to get details for
            include_counts: Whether to include document counts

        Returns:
            List of topics or single topic details
        """
        if topic_id:
            topic = self.index.get_topic(topic_id)
            if not topic:
                return {"success": False, "error": f"Topic not found: {topic_id}"}
            return {
                "success": True,
                "topic": {
                    "id": topic.id,
                    "name": topic.name,
                    "aliases": topic.aliases,
                    "description": topic.description,
                    "document_count": topic.document_count if include_counts else None,
                    "documents": topic.documents if include_counts else None,
                },
            }

        topics = self.index.list_topics(include_counts=include_counts)
        return {
            "success": True,
            "topics": [
                {
                    "id": t.id,
                    "name": t.name,
                    "document_count": t.document_count if include_counts else None,
                }
                for t in topics
            ],
        }

    def find_documents(
        self,
        query: str,
        topic_filter: list[str] | None = None,
        doc_type_filter: list[str] | None = None,
        summary_level: str = "standard",
        max_results: int = 10,
    ) -> dict[str, Any]:
        """Search for documents in the library.

        Args:
            query: Search query
            topic_filter: List of topic IDs to filter by
            doc_type_filter: List of document types to filter by
            summary_level: Summary level (brief, standard, detailed)
            max_results: Maximum number of results

        Returns:
            Matching documents with summaries
        """
        results = self.index.find_documents(
            query=query,
            topic_filter=topic_filter,
            doc_type_filter=doc_type_filter,
            summary_level=summary_level,
            max_results=max_results,
        )

        return {
            "success": True,
            "count": len(results),
            "documents": results,
        }

    def get_document(
        self,
        document_id: str,
        include_summary: bool = True,
        include_content: bool = False,
    ) -> dict[str, Any]:
        """Get a specific document from the library.

        Args:
            document_id: Document ID
            include_summary: Include summaries
            include_content: Include full content

        Returns:
            Document details with optional summary and content
        """
        doc = self.index.get_document(document_id)
        if not doc:
            return {"success": False, "error": f"Document not found: {document_id}"}

        result = {
            "success": True,
            "document": {
                "id": doc.id,
                "title": doc.title,
                "doc_type": doc.doc_type,
                "topics": doc.topics,
                "metadata": {
                    "created": doc.metadata.created,
                    "modified": doc.metadata.modified,
                    "word_count": doc.metadata.word_count,
                    "source_filename": doc.metadata.source_filename,
                },
            },
        }

        if include_summary:
            result["document"]["summaries"] = {
                "brief": doc.summaries.brief,
                "standard": doc.summaries.standard,
                "detailed": doc.summaries.detailed,
            }

        if include_content:
            content = self.index.get_document_content(document_id)
            result["document"]["content"] = content

        return result

    def list_documents(
        self,
        topic_filter: list[str] | None = None,
        doc_type_filter: list[str] | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List all documents in the library.

        Args:
            topic_filter: Filter by topics
            doc_type_filter: Filter by document types
            limit: Maximum results

        Returns:
            List of documents
        """
        docs = self.index.list_documents(
            topic_filter=topic_filter,
            doc_type_filter=doc_type_filter,
        )[:limit]

        return {
            "success": True,
            "count": len(docs),
            "documents": [
                {
                    "id": d.id,
                    "title": d.title,
                    "doc_type": d.doc_type,
                    "topics": d.topics,
                    "brief_summary": d.summaries.brief,
                }
                for d in docs
            ],
        }
