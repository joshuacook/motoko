"""Library file management for Major.

Handles file upload, storage, and text extraction for PDF, Markdown, plain text,
audio (via OpenAI Whisper), and image files (via Claude Vision).
Files are stored in /workspace/.library/files/{file_id}/ and extracted content is
written to workspace entities.
"""

import base64
import json
import os
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal

# pypdf for PDF extraction
try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

# openai for Whisper transcription
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# anthropic for Claude Vision
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


FileStatus = Literal["pending", "processing", "complete", "failed"]


@dataclass
class LibraryFile:
    """Metadata for an uploaded file."""
    id: str
    filename: str
    content_type: str
    size_bytes: int
    status: FileStatus = "pending"
    error_message: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    processed_at: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "LibraryFile":
        """Create from dictionary."""
        return cls(**data)


class LibraryManager:
    """Manages library file storage and processing."""

    def __init__(self, workspace_path: str | Path):
        self.workspace = Path(workspace_path)
        self.library_dir = self.workspace / ".library"
        self.files_dir = self.library_dir / "files"
        self.index_path = self.library_dir / "index.json"

        # Ensure directories exist
        self.files_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> dict[str, LibraryFile]:
        """Load the file index."""
        if not self.index_path.exists():
            return {}
        try:
            data = json.loads(self.index_path.read_text())
            return {k: LibraryFile.from_dict(v) for k, v in data.items()}
        except (json.JSONDecodeError, KeyError):
            return {}

    def _save_index(self, index: dict[str, LibraryFile]):
        """Save the file index."""
        data = {k: v.to_dict() for k, v in index.items()}
        self.index_path.write_text(json.dumps(data, indent=2))

    def list_files(self) -> list[LibraryFile]:
        """List all library files."""
        index = self._load_index()
        return sorted(index.values(), key=lambda f: f.created_at, reverse=True)

    def get_file(self, file_id: str) -> LibraryFile | None:
        """Get a specific file by ID."""
        index = self._load_index()
        return index.get(file_id)

    def save_uploaded_file(
        self,
        file_id: str,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> LibraryFile:
        """Save an uploaded file and create index entry.

        Args:
            file_id: Unique ID for the file
            filename: Original filename
            content: File content bytes
            content_type: MIME type

        Returns:
            LibraryFile metadata
        """
        # Create file directory
        file_dir = self.files_dir / file_id
        file_dir.mkdir(parents=True, exist_ok=True)

        # Determine extension from filename
        ext = Path(filename).suffix or self._extension_from_content_type(content_type)

        # Save original file
        original_path = file_dir / f"original{ext}"
        original_path.write_bytes(content)

        # Create metadata
        library_file = LibraryFile(
            id=file_id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(content),
            status="pending",
        )

        # Save metadata
        meta_path = file_dir / "meta.json"
        meta_path.write_text(json.dumps(library_file.to_dict(), indent=2))

        # Update index
        index = self._load_index()
        index[file_id] = library_file
        self._save_index(index)

        return library_file

    def _extension_from_content_type(self, content_type: str) -> str:
        """Get file extension from content type."""
        mapping = {
            # Documents
            "application/pdf": ".pdf",
            "text/markdown": ".md",
            "text/plain": ".txt",
            "text/x-markdown": ".md",
            # Audio
            "audio/mpeg": ".mp3",
            "audio/mp4": ".m4a",
            "audio/wav": ".wav",
            "audio/webm": ".webm",
            "audio/ogg": ".ogg",
            # Images
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }
        return mapping.get(content_type, "")

    def process_file(self, file_id: str) -> LibraryFile:
        """Process an uploaded file and extract content to an entity.

        Args:
            file_id: ID of the file to process

        Returns:
            Updated LibraryFile metadata
        """
        index = self._load_index()
        library_file = index.get(file_id)

        if not library_file:
            raise ValueError(f"File not found: {file_id}")

        # Update status to processing
        library_file.status = "processing"
        index[file_id] = library_file
        self._save_index(index)

        try:
            # Get the original file
            file_dir = self.files_dir / file_id
            original_files = list(file_dir.glob("original.*"))
            if not original_files:
                raise ValueError("Original file not found")

            original_path = original_files[0]
            ext = original_path.suffix.lower()

            # Extract content based on file type
            extra_metadata = {}
            if ext == ".pdf":
                extracted_text = self._extract_pdf(original_path)
                entity_type = "documents"
            elif ext in (".md", ".markdown"):
                extracted_text = self._extract_markdown(original_path)
                entity_type = "documents"
            elif ext in (".txt", ".text"):
                extracted_text = self._extract_text(original_path)
                entity_type = "documents"
            elif ext in (".mp3", ".m4a", ".wav", ".webm", ".ogg"):
                extracted_text, duration_seconds = self._extract_audio(original_path)
                entity_type = "transcripts"
                if duration_seconds is not None:
                    extra_metadata["duration_seconds"] = duration_seconds
            elif ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
                extracted_text = self._extract_image(original_path)
                entity_type = "images"
            else:
                raise ValueError(f"Unsupported file type: {ext}")
            entity_id = self._create_entity(
                entity_type=entity_type,
                title=Path(library_file.filename).stem,
                content=extracted_text,
                source_file=file_id,
                source_filename=library_file.filename,
                extra_metadata=extra_metadata,
            )

            # Update metadata
            library_file.status = "complete"
            library_file.entity_type = entity_type
            library_file.entity_id = entity_id
            library_file.processed_at = datetime.utcnow().isoformat()
            library_file.error_message = None

        except Exception as e:
            library_file.status = "failed"
            library_file.error_message = str(e)

        # Save updated metadata
        index[file_id] = library_file
        self._save_index(index)

        meta_path = file_dir / "meta.json"
        meta_path.write_text(json.dumps(library_file.to_dict(), indent=2))

        return library_file

    def _extract_pdf(self, path: Path) -> str:
        """Extract text from a PDF file."""
        if not HAS_PYPDF:
            raise ValueError("pypdf not installed - cannot extract PDF content")

        reader = PdfReader(path)
        pages = []

        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if text and text.strip():
                pages.append(f"## Page {i}\n\n{text.strip()}")

        if not pages:
            raise ValueError("Could not extract any text from PDF")

        return "\n\n".join(pages)

    def _extract_markdown(self, path: Path) -> str:
        """Extract content from a Markdown file (direct copy)."""
        return path.read_text(encoding="utf-8")

    def _extract_text(self, path: Path) -> str:
        """Extract content from a plain text file."""
        return path.read_text(encoding="utf-8")

    def _extract_audio(self, path: Path) -> tuple[str, float | None]:
        """Transcribe audio via OpenAI Whisper.

        Args:
            path: Path to the audio file

        Returns:
            Tuple of (formatted transcript, duration in seconds)
        """
        if not HAS_OPENAI:
            raise ValueError("openai not installed - cannot transcribe audio")

        client = OpenAI()  # Uses OPENAI_API_KEY env var

        with open(path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json",  # Includes timestamps
            )

        # Format as markdown with timestamps
        lines = ["# Transcript\n"]
        duration_seconds = getattr(transcript, "duration", None)

        # verbose_json returns segments with timestamps
        segments = getattr(transcript, "segments", None)
        if segments:
            for segment in segments:
                # Segments can be objects or dicts depending on openai version
                if hasattr(segment, "start"):
                    start = segment.start
                    text = getattr(segment, "text", "").strip()
                else:
                    start = segment.get("start", 0)
                    text = segment.get("text", "").strip()
                if text:
                    # Format timestamp as [MM:SS]
                    minutes = int(start // 60)
                    seconds = int(start % 60)
                    lines.append(f"[{minutes:02d}:{seconds:02d}] {text}")
        else:
            # Fallback to plain text if no segments
            lines.append(transcript.text)

        return "\n".join(lines), duration_seconds

    def _extract_image(self, path: Path) -> str:
        """Describe image via Claude Vision.

        Args:
            path: Path to the image file

        Returns:
            Image description as markdown
        """
        if not HAS_ANTHROPIC:
            raise ValueError("anthropic not installed - cannot describe image")

        client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var

        # Read and encode image
        image_data = base64.b64encode(path.read_bytes()).decode()
        media_type = self._get_image_media_type(path)

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Describe this image in detail. If there is text visible, extract it.",
                    },
                ],
            }],
        )

        description = response.content[0].text

        # Format as markdown
        lines = ["# Image Description\n", description]
        return "\n".join(lines)

    def _get_image_media_type(self, path: Path) -> str:
        """Get the MIME type for an image file."""
        ext = path.suffix.lower()
        mapping = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        return mapping.get(ext, "image/png")

    def _create_entity(
        self,
        entity_type: str,
        title: str,
        content: str,
        source_file: str,
        source_filename: str,
        extra_metadata: dict | None = None,
    ) -> str:
        """Create a workspace entity from extracted content.

        Args:
            entity_type: Type directory (e.g., "documents", "transcripts", "images")
            title: Entity title
            content: Extracted content
            source_file: Library file ID
            source_filename: Original filename
            extra_metadata: Additional frontmatter fields (e.g., duration_seconds)

        Returns:
            Entity ID (filename without .md)
        """
        import yaml

        # Ensure entity type directory exists
        type_dir = self.workspace / entity_type
        type_dir.mkdir(parents=True, exist_ok=True)

        # Generate entity ID from title
        entity_id = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")

        # Avoid overwriting
        entity_path = type_dir / f"{entity_id}.md"
        if entity_path.exists():
            counter = 1
            while (type_dir / f"{entity_id}-{counter}.md").exists():
                counter += 1
            entity_id = f"{entity_id}-{counter}"
            entity_path = type_dir / f"{entity_id}.md"

        # Build frontmatter
        frontmatter = {
            "title": title,
            "source_file": source_file,
            "source_filename": source_filename,
            "extracted_at": datetime.utcnow().isoformat(),
        }

        # Add extra metadata if provided
        if extra_metadata:
            frontmatter.update(extra_metadata)

        yaml_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
        entity_content = f"---\n{yaml_str}---\n\n{content}"

        entity_path.write_text(entity_content)

        return entity_id

    def delete_file(self, file_id: str) -> bool:
        """Delete a library file and optionally its entity.

        Args:
            file_id: ID of the file to delete

        Returns:
            True if deleted, False if not found
        """
        index = self._load_index()
        library_file = index.get(file_id)

        if not library_file:
            return False

        # Delete the entity if it exists
        if library_file.entity_type and library_file.entity_id:
            entity_path = self.workspace / library_file.entity_type / f"{library_file.entity_id}.md"
            if entity_path.exists():
                entity_path.unlink()

        # Delete file directory
        file_dir = self.files_dir / file_id
        if file_dir.exists():
            import shutil
            shutil.rmtree(file_dir)

        # Update index
        del index[file_id]
        self._save_index(index)

        return True

    def retry_processing(self, file_id: str) -> LibraryFile:
        """Retry processing a failed file.

        Args:
            file_id: ID of the file to retry

        Returns:
            Updated LibraryFile metadata
        """
        index = self._load_index()
        library_file = index.get(file_id)

        if not library_file:
            raise ValueError(f"File not found: {file_id}")

        if library_file.status not in ("failed", "pending"):
            raise ValueError(f"Cannot retry file with status: {library_file.status}")

        # Reset status and reprocess
        library_file.status = "pending"
        library_file.error_message = None
        index[file_id] = library_file
        self._save_index(index)

        return self.process_file(file_id)


def get_content_type(filename: str) -> str:
    """Determine content type from filename."""
    ext = Path(filename).suffix.lower()
    mapping = {
        # Documents
        ".pdf": "application/pdf",
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".txt": "text/plain",
        ".text": "text/plain",
        # Audio
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".wav": "audio/wav",
        ".webm": "audio/webm",
        ".ogg": "audio/ogg",
        # Images
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    return mapping.get(ext, "application/octet-stream")


def is_supported_file(filename: str) -> bool:
    """Check if a file type is supported."""
    ext = Path(filename).suffix.lower()
    return ext in (
        # Documents
        ".pdf", ".md", ".markdown", ".txt", ".text",
        # Audio
        ".mp3", ".m4a", ".wav", ".webm", ".ogg",
        # Images
        ".png", ".jpg", ".jpeg", ".webp", ".gif",
    )
