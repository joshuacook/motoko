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
import os
import re
import uuid as _uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml

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


@dataclass
class InsightItem:
    """A cross-document observation generated during reindex."""
    id: str                    # uuid hex
    type: str                  # "contradiction" | "connection" | "gap" | "consolidation"
    title: str                 # Short summary
    description: str           # Detailed observation
    source_ids: list[str]      # Document IDs involved
    source_titles: list[str]   # Human-readable titles
    status: str                # "new" | "dismissed" | "saved" | "actioned"
    created_at: str            # ISO timestamp

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "InsightItem":
        return cls(**data)


@dataclass
class Notebook:
    """A curated collection of sources with chat, audio, and summary capabilities."""
    id: str                    # uuid hex
    title: str
    source_ids: list[str]      # topic IDs, doc IDs, entity:* IDs
    source_labels: list[str]   # human-readable names
    chat_session_id: str | None = None
    audio_generation_ids: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Notebook":
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

    # Insight operations

    def _load_insights(self) -> list[InsightItem]:
        """Load insights from JSON file."""
        insights_path = self.index_dir / "insights.json"
        if not insights_path.exists():
            return []
        try:
            data = json.loads(insights_path.read_text())
            return [InsightItem.from_dict(item) for item in data]
        except (json.JSONDecodeError, KeyError):
            return []

    def _save_insights(self, items: list[InsightItem]):
        """Save insights to JSON file."""
        insights_path = self.index_dir / "insights.json"
        data = [item.to_dict() for item in items]
        insights_path.write_text(json.dumps(data, indent=2))

    def add_insights(self, items: list[InsightItem]):
        """Append insights, deduplicating by title."""
        existing = self._load_insights()
        existing_titles = {item.title for item in existing}
        for item in items:
            if item.title not in existing_titles:
                existing.append(item)
                existing_titles.add(item.title)
        self._save_insights(existing)

    def list_insights(self, status_filter: str | None = None) -> list[InsightItem]:
        """List insights with optional status filter."""
        items = self._load_insights()
        if status_filter:
            items = [i for i in items if i.status == status_filter]
        return items

    def get_insight_count(self, status: str = "new") -> int:
        """Get count of insights with given status."""
        return len([i for i in self._load_insights() if i.status == status])

    def update_insight(self, insight_id: str, status: str) -> InsightItem | None:
        """Update an insight's status. Returns updated item or None."""
        items = self._load_insights()
        for item in items:
            if item.id == insight_id:
                item.status = status
                self._save_insights(items)
                return item
        return None

    # Notebook operations

    def _load_notebooks(self) -> dict[str, Notebook]:
        """Load notebooks from JSON file."""
        notebooks_path = self.index_dir / "notebooks.json"
        if not notebooks_path.exists():
            return {}
        try:
            data = json.loads(notebooks_path.read_text())
            return {k: Notebook.from_dict(v) for k, v in data.items()}
        except (json.JSONDecodeError, KeyError):
            return {}

    def _save_notebooks(self, notebooks: dict[str, Notebook]):
        """Save notebooks to JSON file."""
        data = {k: v.to_dict() for k, v in notebooks.items()}
        notebooks_path = self.index_dir / "notebooks.json"
        notebooks_path.write_text(json.dumps(data, indent=2))

    def list_notebooks(self) -> list[Notebook]:
        """List all notebooks, sorted by updated_at descending."""
        notebooks = self._load_notebooks()
        result = list(notebooks.values())
        result.sort(key=lambda n: n.updated_at, reverse=True)
        return result

    def get_notebook(self, notebook_id: str) -> Notebook | None:
        """Get a notebook by ID."""
        notebooks = self._load_notebooks()
        return notebooks.get(notebook_id)

    def create_notebook(self, title: str, source_ids: list[str], source_labels: list[str]) -> Notebook:
        """Create a new notebook."""
        now = datetime.utcnow().isoformat()
        notebook = Notebook(
            id=_uuid.uuid4().hex,
            title=title,
            source_ids=source_ids,
            source_labels=source_labels,
            created_at=now,
            updated_at=now,
        )
        notebooks = self._load_notebooks()
        notebooks[notebook.id] = notebook
        self._save_notebooks(notebooks)
        return notebook

    def update_notebook(self, notebook_id: str, **kwargs) -> Notebook | None:
        """Update a notebook's fields. Returns updated notebook or None."""
        notebooks = self._load_notebooks()
        notebook = notebooks.get(notebook_id)
        if not notebook:
            return None
        for key, value in kwargs.items():
            if hasattr(notebook, key):
                setattr(notebook, key, value)
        notebook.updated_at = datetime.utcnow().isoformat()
        self._save_notebooks(notebooks)
        return notebook

    def delete_notebook(self, notebook_id: str) -> bool:
        """Delete a notebook. Returns True if deleted."""
        notebooks = self._load_notebooks()
        if notebook_id not in notebooks:
            return False
        del notebooks[notebook_id]
        self._save_notebooks(notebooks)
        return True

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

    # Entity indexing

    def _load_entity_meta(self) -> dict:
        """Load entity index metadata (timestamps for incremental indexing)."""
        meta_path = self.index_dir / "entity_index_meta.json"
        if not meta_path.exists():
            return {}
        try:
            return json.loads(meta_path.read_text())
        except (json.JSONDecodeError, KeyError):
            return {}

    def _save_entity_meta(self, meta: dict):
        """Save entity index metadata."""
        meta_path = self.index_dir / "entity_index_meta.json"
        meta_path.write_text(json.dumps(meta, indent=2))

    def index_entities(self, analyzer: "DocumentAnalyzer") -> dict:
        """Scan workspace entities and index new/changed ones.

        Reads entity types from .claude/schema.yaml, walks each type's
        directory for .md files, and runs AI analysis on new/changed entities.

        Args:
            analyzer: DocumentAnalyzer instance for AI analysis

        Returns:
            Dict with keys: indexed, skipped, failed, errors
        """
        results = {"indexed": 0, "skipped": 0, "failed": 0, "errors": []}

        # Read schema to get entity types
        schema_path = self.workspace / ".claude" / "schema.yaml"
        if not schema_path.exists():
            return results

        try:
            schema = yaml.safe_load(schema_path.read_text()) or {}
        except yaml.YAMLError:
            return results

        entities_config = schema.get("entities", {})
        if not entities_config:
            return results

        # Load mtime tracking metadata
        meta = self._load_entity_meta()
        entity_mtimes = meta.get("entity_mtimes", {})

        documents = self._load_documents()
        seen_entity_ids = set()

        for entity_type, config in entities_config.items():
            directory = config.get("directory", entity_type)
            type_dir = self.workspace / directory

            if not type_dir.is_dir():
                continue

            for md_file in type_dir.glob("*.md"):
                entity_id = md_file.stem
                doc_id = f"entity:{directory}/{entity_id}"
                seen_entity_ids.add(doc_id)

                # Check mtime for incremental indexing
                file_mtime = os.path.getmtime(md_file)
                last_mtime = entity_mtimes.get(doc_id, 0)

                if doc_id in documents and file_mtime <= last_mtime:
                    results["skipped"] += 1
                    continue

                try:
                    # Read and parse entity file
                    text = md_file.read_text()
                    body = text
                    if text.startswith("---"):
                        end = text.find("---", 3)
                        if end != -1:
                            body = text[end + 3:].lstrip("\n")

                    if not body.strip():
                        results["skipped"] += 1
                        continue

                    # Run AI analysis
                    analysis = analyzer.analyze(body, md_file.name)

                    # Create/find topics
                    topic_ids = []
                    for topic_name in analysis["topics"]:
                        topic = self.find_or_create_topic(topic_name)
                        topic_ids.append(topic.id)

                    # Create indexed document
                    doc = IndexedDocument(
                        id=doc_id,
                        source_path=f"{directory}/{entity_id}.md",
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
                            source_filename=md_file.name,
                        ),
                    )

                    documents[doc_id] = doc
                    entity_mtimes[doc_id] = file_mtime
                    results["indexed"] += 1

                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append({
                        "file_id": doc_id,
                        "filename": md_file.name,
                        "error": str(e),
                    })

        # Clean up stale entries for deleted entities
        stale_ids = [
            did for did in documents
            if did.startswith("entity:") and did not in seen_entity_ids
        ]
        for stale_id in stale_ids:
            del documents[stale_id]
            entity_mtimes.pop(stale_id, None)

        # Save all at once
        self._save_documents(documents)
        self._update_topic_counts()
        self._save_entity_meta({"entity_mtimes": entity_mtimes})

        return results

    # Topic summaries

    def get_topic_summary(self, topic_id: str) -> dict | None:
        """Get a cached collection summary for a topic, generating on miss.

        Returns:
            Dict with keys: overview, themes, key_findings, connections
            or None if topic not found
        """
        topic = self.get_topic(topic_id)
        if not topic:
            return None

        # Check cache
        summaries_path = self.index_dir / "topic_summaries.json"
        cache = {}
        if summaries_path.exists():
            try:
                cache = json.loads(summaries_path.read_text())
            except (json.JSONDecodeError, KeyError):
                cache = {}

        if topic_id in cache:
            return cache[topic_id]

        # Generate on miss
        docs = self.list_documents(topic_filter=[topic_id])
        if not docs:
            return None

        # Gather document summaries for input
        doc_summaries = []
        for doc in docs:
            doc_summaries.append({
                "title": doc.title,
                "summary": doc.summaries.standard,
            })

        try:
            analyzer = DocumentAnalyzer()
            summary = analyzer.summarize_collection(doc_summaries, topic.name)

            # Cache result
            cache[topic_id] = summary
            summaries_path.write_text(json.dumps(cache, indent=2))

            return summary
        except Exception:
            return None

    def regenerate_topic_summary(self, topic_id: str) -> dict | None:
        """Force regenerate a topic summary (invalidates cache)."""
        summaries_path = self.index_dir / "topic_summaries.json"
        cache = {}
        if summaries_path.exists():
            try:
                cache = json.loads(summaries_path.read_text())
            except (json.JSONDecodeError, KeyError):
                cache = {}

        # Remove cached entry
        cache.pop(topic_id, None)
        summaries_path.write_text(json.dumps(cache, indent=2))

        # Regenerate
        return self.get_topic_summary(topic_id)

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

        For library files, reads from .library/files/{id}/extracted.txt.
        For entities (id starts with 'entity:'), reads from {type}/{id}.md
        and strips frontmatter.

        Args:
            doc_id: Document ID

        Returns:
            Full document content, or None if not found
        """
        if doc_id.startswith("entity:"):
            # Entity content: read from {type}/{id}.md
            entity_path = doc_id[len("entity:"):]  # e.g. "notes/my-note"
            content_path = self.workspace / f"{entity_path}.md"
            if content_path.exists():
                text = content_path.read_text()
                # Strip YAML frontmatter
                if text.startswith("---"):
                    end = text.find("---", 3)
                    if end != -1:
                        text = text[end + 3:].lstrip("\n")
                return text
            return None

        # Library file content: stored in .library/files/{id}/extracted.txt
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

    def summarize_collection(
        self,
        doc_summaries: list[dict],
        collection_name: str,
    ) -> dict:
        """Synthesize a collection-level summary across multiple documents.

        Args:
            doc_summaries: List of dicts with 'title' and 'summary' keys
            collection_name: Name of the topic/collection

        Returns:
            Dict with keys: overview, themes, key_findings, connections
        """
        docs_text = "\n\n".join(
            f"**{d['title']}**: {d['summary']}" for d in doc_summaries
        )

        prompt = f"""Analyze these documents that are grouped under the topic "{collection_name}" and return a JSON object synthesizing them:

{{
  "overview": "2-3 sentence overview of what this collection covers",
  "themes": ["list", "of", "common", "themes"],
  "key_findings": ["Key finding or insight 1", "Key finding or insight 2", "..."],
  "connections": "1-2 sentences about how these documents relate to each other"
}}

Documents:
{docs_text}

Return ONLY valid JSON, no other text."""

        response = self.client.messages.create(
            model=self.MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text

        # Extract JSON
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end]
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end]

        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON found in collection summary response")

        data = json.loads(text[start:end], strict=False)

        return {
            "overview": data.get("overview", ""),
            "themes": data.get("themes", []),
            "key_findings": data.get("key_findings", []),
            "connections": data.get("connections", ""),
        }

    def generate_insights(self, documents: list[dict]) -> list[dict]:
        """Generate cross-document insights from document briefs.

        Args:
            documents: List of dicts with 'id', 'title', and 'brief' keys

        Returns:
            List of insight dicts with type, title, description, source_ids, source_titles
        """
        if not documents or len(documents) < 2:
            return []

        # Build document briefs text, truncated to stay within context
        docs_text = "\n".join(
            f"- [{d['id']}] \"{d['title']}\": {d['brief']}"
            for d in documents
        )[:30000]

        prompt = f"""You are analyzing a library of {len(documents)} documents. Identify cross-document observations.

Return a JSON array of insight objects. Each insight should be one of these types:
- "contradiction": Two or more sources disagree on a factual claim or recommendation
- "connection": A surprising or non-obvious link between documents on different topics
- "gap": An important question or area that the documents raise but don't answer
- "consolidation": Multiple documents cover overlapping ground and could be merged or summarized together

For each insight:
{{
  "type": "contradiction|connection|gap|consolidation",
  "title": "Short summary (under 80 chars)",
  "description": "2-3 sentence detailed observation",
  "source_ids": ["id1", "id2"],
  "source_titles": ["Title 1", "Title 2"]
}}

Generate 3-8 insights. Focus on the most interesting and actionable observations. Only use document IDs and titles from the list below.

Documents:
{docs_text}

Return ONLY a valid JSON array, no other text."""

        response = self.client.messages.create(
            model=self.MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text

        # Extract JSON array
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end]
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end]

        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end == 0:
            return []

        data = json.loads(text[start:end], strict=False)
        return data if isinstance(data, list) else []

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
