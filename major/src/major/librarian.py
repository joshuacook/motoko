"""Library indexing and knowledge organization.

Implements the librarian system for analyzing and indexing library documents.
Provides multi-level summaries, topic extraction, and document search.

Storage layout:
  .library/
    index/
      documents.json    # Document index
      topics.json       # Topic/ontology index
    files/              # Raw files (managed by library.py)
"""

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal

# Anthropic for Haiku analysis
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


@dataclass
class DocumentSummaries:
    """Multi-level summaries for a document."""
    brief: str = ""       # 1-2 sentences - what is this?
    standard: str = ""    # 1 paragraph - scope and significance
    detailed: str = ""    # Section-by-section breakdown


@dataclass
class DocumentMetadata:
    """Metadata for an indexed document."""
    created: str = ""
    modified: str = ""
    word_count: int = 0
    source_filename: str = ""


@dataclass
class IndexedDocument:
    """A document in the library index."""
    id: str
    source_path: str
    title: str
    doc_type: str  # transcript, blog_post, article, interview, etc.
    summaries: DocumentSummaries = field(default_factory=DocumentSummaries)
    topics: list[str] = field(default_factory=list)  # Topic IDs
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "source_path": self.source_path,
            "title": self.title,
            "doc_type": self.doc_type,
            "summaries": asdict(self.summaries),
            "topics": self.topics,
            "metadata": asdict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IndexedDocument":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            source_path=data["source_path"],
            title=data["title"],
            doc_type=data["doc_type"],
            summaries=DocumentSummaries(**data.get("summaries", {})),
            topics=data.get("topics", []),
            metadata=DocumentMetadata(**data.get("metadata", {})),
        )


@dataclass
class Topic:
    """A topic/concept in the library ontology."""
    id: str
    name: str
    aliases: list[str] = field(default_factory=list)
    description: str = ""
    documents: list[str] = field(default_factory=list)  # Document IDs
    document_count: int = 0
    # Future: parent, children, related for hierarchical ontology

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Topic":
        """Create from dictionary."""
        return cls(**data)


SummaryLevel = Literal["brief", "standard", "detailed"]


class LibraryIndex:
    """Manages the library document and topic index."""

    def __init__(self, workspace_path: str | Path):
        self.workspace = Path(workspace_path)
        self.index_dir = self.workspace / ".library" / "index"
        self.documents_path = self.index_dir / "documents.json"
        self.topics_path = self.index_dir / "topics.json"

        # Ensure directory exists
        self.index_dir.mkdir(parents=True, exist_ok=True)

    def _load_documents(self) -> dict[str, IndexedDocument]:
        """Load the document index."""
        if not self.documents_path.exists():
            return {}
        try:
            data = json.loads(self.documents_path.read_text())
            return {k: IndexedDocument.from_dict(v) for k, v in data.items()}
        except (json.JSONDecodeError, KeyError):
            return {}

    def _save_documents(self, documents: dict[str, IndexedDocument]):
        """Save the document index."""
        data = {k: v.to_dict() for k, v in documents.items()}
        self.documents_path.write_text(json.dumps(data, indent=2))

    def _load_topics(self) -> dict[str, Topic]:
        """Load the topic index."""
        if not self.topics_path.exists():
            return {}
        try:
            data = json.loads(self.topics_path.read_text())
            return {k: Topic.from_dict(v) for k, v in data.items()}
        except (json.JSONDecodeError, KeyError):
            return {}

    def _save_topics(self, topics: dict[str, Topic]):
        """Save the topic index."""
        data = {k: v.to_dict() for k, v in topics.items()}
        self.topics_path.write_text(json.dumps(data, indent=2))

    # Document operations

    def get_document(self, doc_id: str) -> IndexedDocument | None:
        """Get a document by ID."""
        documents = self._load_documents()
        return documents.get(doc_id)

    def list_documents(
        self,
        topic_filter: list[str] | None = None,
        doc_type_filter: list[str] | None = None,
    ) -> list[IndexedDocument]:
        """List documents with optional filters."""
        documents = self._load_documents()
        result = list(documents.values())

        if topic_filter:
            result = [d for d in result if any(t in d.topics for t in topic_filter)]

        if doc_type_filter:
            result = [d for d in result if d.doc_type in doc_type_filter]

        return result

    def add_document(self, document: IndexedDocument):
        """Add or update a document in the index."""
        documents = self._load_documents()
        documents[document.id] = document
        self._save_documents(documents)

        # Update topic document counts
        self._update_topic_counts()

    def remove_document(self, doc_id: str) -> bool:
        """Remove a document from the index."""
        documents = self._load_documents()
        if doc_id not in documents:
            return False

        del documents[doc_id]
        self._save_documents(documents)
        self._update_topic_counts()
        return True

    # Topic operations

    def get_topic(self, topic_id: str) -> Topic | None:
        """Get a topic by ID."""
        topics = self._load_topics()
        return topics.get(topic_id)

    def list_topics(self, include_counts: bool = True) -> list[Topic]:
        """List all topics."""
        topics = self._load_topics()
        result = list(topics.values())

        if include_counts:
            # Ensure counts are up to date
            self._update_topic_counts()
            topics = self._load_topics()
            result = list(topics.values())

        return sorted(result, key=lambda t: t.document_count, reverse=True)

    def add_topic(self, topic: Topic):
        """Add or update a topic."""
        topics = self._load_topics()
        topics[topic.id] = topic
        self._save_topics(topics)

    def find_or_create_topic(self, name: str) -> Topic:
        """Find a topic by name (case-insensitive) or create it."""
        topics = self._load_topics()
        name_lower = name.lower()

        # Check existing topics by name or alias
        for topic in topics.values():
            if topic.name.lower() == name_lower:
                return topic
            if any(alias.lower() == name_lower for alias in topic.aliases):
                return topic

        # Create new topic
        import re
        topic_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

        # Ensure unique ID
        base_id = topic_id
        counter = 1
        while topic_id in topics:
            topic_id = f"{base_id}-{counter}"
            counter += 1

        topic = Topic(id=topic_id, name=name)
        topics[topic_id] = topic
        self._save_topics(topics)
        return topic

    def _update_topic_counts(self):
        """Update document counts for all topics."""
        documents = self._load_documents()
        topics = self._load_topics()

        # Reset counts and document lists
        for topic in topics.values():
            topic.documents = []
            topic.document_count = 0

        # Count documents per topic
        for doc in documents.values():
            for topic_id in doc.topics:
                if topic_id in topics:
                    topics[topic_id].documents.append(doc.id)
                    topics[topic_id].document_count += 1

        self._save_topics(topics)

    # Search operations

    def find_documents(
        self,
        query: str,
        topic_filter: list[str] | None = None,
        doc_type_filter: list[str] | None = None,
        summary_level: SummaryLevel = "standard",
        max_results: int = 10,
    ) -> list[dict]:
        """Find documents matching a query.

        Returns documents with summaries at the requested level.
        For MVP, this does simple text matching. Future: semantic search.

        Args:
            query: Search query (matches title, summaries, topics)
            topic_filter: Limit to specific topics
            doc_type_filter: Limit to specific document types
            summary_level: Which summary level to return
            max_results: Maximum number of results

        Returns:
            List of dicts with id, title, doc_type, topics, summary
        """
        documents = self.list_documents(topic_filter, doc_type_filter)
        query_lower = query.lower()
        results = []

        for doc in documents:
            # Simple relevance scoring
            score = 0

            # Title match
            if query_lower in doc.title.lower():
                score += 10

            # Summary matches
            if query_lower in doc.summaries.brief.lower():
                score += 5
            if query_lower in doc.summaries.standard.lower():
                score += 3
            if query_lower in doc.summaries.detailed.lower():
                score += 1

            # Topic name matches
            topics = self._load_topics()
            for topic_id in doc.topics:
                if topic_id in topics:
                    topic = topics[topic_id]
                    if query_lower in topic.name.lower():
                        score += 5
                    if any(query_lower in alias.lower() for alias in topic.aliases):
                        score += 3

            if score > 0:
                # Get the appropriate summary
                if summary_level == "brief":
                    summary = doc.summaries.brief
                elif summary_level == "detailed":
                    summary = doc.summaries.detailed
                else:
                    summary = doc.summaries.standard

                results.append({
                    "id": doc.id,
                    "title": doc.title,
                    "doc_type": doc.doc_type,
                    "topics": doc.topics,
                    "summary": summary,
                    "_score": score,
                })

        # Sort by score and limit
        results.sort(key=lambda x: x["_score"], reverse=True)
        for r in results:
            del r["_score"]

        return results[:max_results]

    def get_document_content(self, doc_id: str) -> str | None:
        """Get the full extracted content of a document.

        Reads from the library file storage, not the index.

        Args:
            doc_id: Document ID

        Returns:
            Full document content, or None if not found
        """
        # Content is stored in .library/files/{id}/extracted.txt
        content_path = self.workspace / ".library" / "files" / doc_id / "extracted.txt"
        if content_path.exists():
            return content_path.read_text()
        return None


class DocumentAnalyzer:
    """Analyzes documents using Haiku to generate summaries and extract topics.

    Uses a single API call per document for cost optimization.
    """

    # Haiku model for cost-effective analysis
    MODEL = "claude-haiku-4-5-20251001"

    def __init__(self):
        if not HAS_ANTHROPIC:
            raise ValueError("anthropic package not installed")
        self.client = anthropic.Anthropic()

    def analyze(
        self,
        content: str,
        filename: str,
    ) -> dict:
        """Analyze a document and generate summaries + extract topics.

        Args:
            content: The extracted text content of the document
            filename: Original filename (helps with classification)

        Returns:
            Dict with keys: title, doc_type, summaries, topics
        """
        # Truncate content for API limits (Haiku context is 200k but keep it reasonable)
        max_content = 50000
        truncated = content[:max_content] if len(content) > max_content else content
        word_count = len(content.split())

        prompt = f"""Analyze this document and return a JSON object with the following structure:

{{
  "title": "A clear, descriptive title for this document",
  "doc_type": "one of: transcript, blog_post, article, interview, report, notes, presentation, other",
  "summaries": {{
    "brief": "1-2 sentences describing what this document is",
    "standard": "A paragraph covering the scope, key points, and significance",
    "detailed": "A section-by-section or point-by-point breakdown of the content"
  }},
  "topics": ["list", "of", "key", "topics", "and", "concepts"]
}}

Guidelines:
- For doc_type, choose the most appropriate category based on the content style
- Topics should be specific concepts, names, technologies, or themes discussed (5-15 topics)
- The detailed summary should help someone navigate the document without reading it
- Be concise but comprehensive

Filename: {filename}
Word count: {word_count}

Document content:
{truncated}

Return ONLY valid JSON, no other text."""

        response = self.client.messages.create(
            model=self.MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse JSON from response
        text = response.content[0].text

        # Extract JSON (handle potential markdown code blocks)
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end]
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end]

        # Find JSON object
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON found in response")

        data = json.loads(text[start:end], strict=False)

        # Validate and normalize
        return {
            "title": data.get("title", filename),
            "doc_type": data.get("doc_type", "other"),
            "summaries": {
                "brief": data.get("summaries", {}).get("brief", ""),
                "standard": data.get("summaries", {}).get("standard", ""),
                "detailed": data.get("summaries", {}).get("detailed", ""),
            },
            "topics": data.get("topics", []),
            "word_count": word_count,
        }

    def analyze_and_index(
        self,
        file_id: str,
        content: str,
        filename: str,
        index: "LibraryIndex",
    ) -> IndexedDocument:
        """Analyze a document and add it to the index.

        Args:
            file_id: Library file ID
            content: Extracted text content
            filename: Original filename
            index: LibraryIndex to add the document to

        Returns:
            The indexed document
        """
        # Run analysis
        analysis = self.analyze(content, filename)

        # Create/find topics and get their IDs
        topic_ids = []
        for topic_name in analysis["topics"]:
            topic = index.find_or_create_topic(topic_name)
            topic_ids.append(topic.id)

        # Create indexed document
        doc = IndexedDocument(
            id=file_id,
            source_path=f".library/files/{file_id}/extracted.txt",
            title=analysis["title"],
            doc_type=analysis["doc_type"],
            summaries=DocumentSummaries(
                brief=analysis["summaries"]["brief"],
                standard=analysis["summaries"]["standard"],
                detailed=analysis["summaries"]["detailed"],
            ),
            topics=topic_ids,
            metadata=DocumentMetadata(
                created=datetime.utcnow().isoformat(),
                modified=datetime.utcnow().isoformat(),
                word_count=analysis["word_count"],
                source_filename=filename,
            ),
        )

        # Add to index
        index.add_document(doc)

        return doc
