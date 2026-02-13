"""Podcast audio generation from library sources.

Generates two-host dialogue scripts from source content using Claude,
then synthesizes audio using OpenAI TTS, concatenating MP3 segments.

Storage layout:
  .library/audio/
    generations.json              # Index of all podcast generations
    {generation_id}/
      meta.json                   # Status, source_ids, duration, created_at
      script.json                 # [{speaker: "A", text: "..."}, ...]
      podcast.mp3                 # Final concatenated audio
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

import anthropic
import openai


@dataclass
class PodcastGeneration:
    """A podcast generation record."""
    id: str
    title: str
    status: str  # pending, generating_script, generating_audio, stitching, complete, failed
    source_ids: list[str] = field(default_factory=list)
    duration: float | None = None  # seconds
    audio_path: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    segment_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PodcastGeneration":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class PodcastManager:
    """Manages podcast generation from library sources."""

    SCRIPT_MODEL = "claude-sonnet-4-20250514"
    HOST_A_VOICE = "alloy"
    HOST_B_VOICE = "nova"
    TTS_MODEL = "tts-1"

    def __init__(self, workspace_path: str | Path):
        self.workspace = Path(workspace_path)
        self.audio_dir = self.workspace / ".library" / "audio"
        self.index_path = self.audio_dir / "generations.json"
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> dict[str, PodcastGeneration]:
        if not self.index_path.exists():
            return {}
        try:
            data = json.loads(self.index_path.read_text())
            return {k: PodcastGeneration.from_dict(v) for k, v in data.items()}
        except (json.JSONDecodeError, KeyError):
            return {}

    def _save_index(self, index: dict[str, PodcastGeneration]):
        data = {k: v.to_dict() for k, v in index.items()}
        self.index_path.write_text(json.dumps(data, indent=2))

    def list_generations(self) -> list[PodcastGeneration]:
        index = self._load_index()
        return sorted(index.values(), key=lambda g: g.created_at, reverse=True)

    def get_generation(self, gen_id: str) -> PodcastGeneration | None:
        index = self._load_index()
        return index.get(gen_id)

    def delete_generation(self, gen_id: str) -> bool:
        index = self._load_index()
        if gen_id not in index:
            return False

        # Delete files
        gen_dir = self.audio_dir / gen_id
        if gen_dir.exists():
            import shutil
            shutil.rmtree(gen_dir)

        del index[gen_id]
        self._save_index(index)
        return True

    def get_audio_path(self, gen_id: str) -> Path | None:
        gen = self.get_generation(gen_id)
        if not gen or gen.status != "complete":
            return None
        audio_path = self.audio_dir / gen_id / "podcast.mp3"
        if audio_path.exists():
            return audio_path
        return None

    def _gather_source_content(self, source_ids: list[str]) -> str:
        """Gather content from source IDs (topics, docs, entities, or '*' for everything)."""
        from .librarian import LibraryIndex

        index = LibraryIndex(self.workspace)
        content_parts = []

        if "*" in source_ids:
            # Everything
            docs = index.list_documents()
        else:
            # Filter by provided IDs (could be topic IDs or document IDs)
            topics = index._load_topics()
            doc_ids = set()

            for sid in source_ids:
                if sid in topics:
                    # It's a topic - get all its documents
                    for doc_id in topics[sid].documents:
                        doc_ids.add(doc_id)
                else:
                    # It's a document ID
                    doc_ids.add(sid)

            docs = [d for d in index.list_documents() if d.id in doc_ids]

        for doc in docs:
            content = index.get_document_content(doc.id)
            if content:
                # Truncate individual docs to keep total manageable
                truncated = content[:10000] if len(content) > 10000 else content
                content_parts.append(f"## {doc.title}\n\n{truncated}")

        return "\n\n---\n\n".join(content_parts)

    async def _generate_script(self, content: str, title: str | None = None) -> list[dict]:
        """Generate a two-host dialogue script from content."""
        client = anthropic.Anthropic()

        topic_hint = f' about "{title}"' if title else ""
        prompt = f"""You are writing a script for a two-host podcast{topic_hint}. The hosts are having a natural, engaging conversation about the following source material.

Host A is the main presenter who guides the discussion. Host B asks clarifying questions, adds insights, and reacts naturally.

Write a dialogue script as a JSON array. Each entry has "speaker" (either "A" or "B") and "text" (what they say).

Guidelines:
- Make it conversational and natural, like two smart friends discussing interesting material
- Include natural reactions ("That's fascinating", "Right, and what's interesting is...")
- Host A should explain key concepts; Host B should ask the questions a curious listener would ask
- Keep individual lines short (1-3 sentences each) for natural pacing
- Aim for 15-25 exchanges total (about 3-5 minutes of audio)
- Start with a brief intro, cover the key points, and end with a takeaway
- Do NOT use sound effects, music cues, or stage directions

Source material:
{content[:50000]}

Return ONLY the JSON array, no other text."""

        response = client.messages.create(
            model=self.SCRIPT_MODEL,
            max_tokens=4096,
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
            raise ValueError("No JSON array found in script response")

        script = json.loads(text[start:end])

        # Validate structure
        for entry in script:
            if "speaker" not in entry or "text" not in entry:
                raise ValueError("Invalid script entry: missing speaker or text")
            if entry["speaker"] not in ("A", "B"):
                raise ValueError(f"Invalid speaker: {entry['speaker']}")

        return script

    async def _generate_audio_segment(self, text: str, voice: str) -> bytes:
        """Generate TTS audio for a single line."""
        client = openai.OpenAI()

        response = client.audio.speech.create(
            model=self.TTS_MODEL,
            voice=voice,
            input=text,
            response_format="mp3",
        )

        return response.content

    def _concatenate_mp3(self, segments: list[bytes]) -> bytes:
        """Concatenate MP3 segments via raw bytes (MP3 frames are independent)."""
        return b"".join(segments)

    async def generate(
        self,
        source_ids: list[str],
        title: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Generate a podcast from sources, yielding SSE events.

        Event types:
          started, script_generating, script_complete,
          audio_progress (per segment), stitching, complete, error
        """
        gen_id = uuid.uuid4().hex[:12]
        gen_dir = self.audio_dir / gen_id
        gen_dir.mkdir(parents=True, exist_ok=True)

        generation = PodcastGeneration(
            id=gen_id,
            title=title or "Podcast",
            status="pending",
            source_ids=source_ids,
        )

        # Save to index
        index = self._load_index()
        index[gen_id] = generation
        self._save_index(index)

        yield {"type": "started", "id": gen_id, "title": generation.title}

        try:
            # 1. Gather source content
            content = self._gather_source_content(source_ids)
            if not content.strip():
                raise ValueError("No content found for the selected sources")

            # 2. Generate script
            generation.status = "generating_script"
            index[gen_id] = generation
            self._save_index(index)
            yield {"type": "script_generating"}

            script = await self._generate_script(content, title)

            # Save script
            (gen_dir / "script.json").write_text(json.dumps(script, indent=2))
            generation.segment_count = len(script)
            index[gen_id] = generation
            self._save_index(index)
            yield {"type": "script_complete", "segment_count": len(script)}

            # 3. Generate audio for each segment
            generation.status = "generating_audio"
            index[gen_id] = generation
            self._save_index(index)

            segments = []
            for i, entry in enumerate(script):
                voice = self.HOST_A_VOICE if entry["speaker"] == "A" else self.HOST_B_VOICE
                audio_bytes = await self._generate_audio_segment(entry["text"], voice)
                segments.append(audio_bytes)

                yield {
                    "type": "audio_progress",
                    "segment": i + 1,
                    "total": len(script),
                    "speaker": entry["speaker"],
                }

            # 4. Concatenate
            generation.status = "stitching"
            index[gen_id] = generation
            self._save_index(index)
            yield {"type": "stitching"}

            final_audio = self._concatenate_mp3(segments)
            audio_path = gen_dir / "podcast.mp3"
            audio_path.write_bytes(final_audio)

            # Estimate duration (~150 words/min, ~1 byte per 10ms is rough)
            total_words = sum(len(entry["text"].split()) for entry in script)
            estimated_duration = (total_words / 150) * 60  # seconds

            # 5. Complete
            generation.status = "complete"
            generation.audio_path = str(audio_path)
            generation.duration = round(estimated_duration, 1)
            index[gen_id] = generation
            self._save_index(index)

            # Save meta
            (gen_dir / "meta.json").write_text(json.dumps(generation.to_dict(), indent=2))

            yield {
                "type": "complete",
                "id": gen_id,
                "duration": generation.duration,
                "segment_count": len(script),
            }

        except Exception as e:
            generation.status = "failed"
            generation.error = str(e)
            index[gen_id] = generation
            self._save_index(index)
            yield {"type": "error", "error": str(e)}
