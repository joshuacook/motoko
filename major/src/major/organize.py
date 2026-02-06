"""Workspace organization via schema inference and batch entity creation.

Analyzes uploaded library files, proposes a workspace schema with entity types
and fields, and batch-creates structured entities.
"""

import json
from pathlib import Path
from typing import AsyncGenerator

import anthropic
import yaml


class WorkspaceOrganizer:
    """Analyzes files and organizes workspace with inferred schema."""

    def __init__(self, workspace_path: Path):
        self.workspace = workspace_path
        self.client = anthropic.Anthropic()

    def _gather_extracted_content(self, library_manager) -> list[dict]:
        """Gather content from all complete library files."""
        files = library_manager.list_files()
        extracted = []

        for f in files:
            if f.status != "complete":
                continue

            # Read extracted content from library storage
            content = library_manager.get_extracted_content(f.id)
            if content:
                extracted.append({
                    "file_id": f.id,
                    "filename": f.filename,
                    "file_type": f.entity_type,  # document, audio, image
                    "content": content[:8000],  # Truncate for API limits
                })

        return extracted

    def _build_inference_prompt(self, extracted: list[dict]) -> str:
        """Build prompt for Claude to infer schema."""
        files_text = "\n\n".join([
            f"=== {e['filename']} ===\n{e['content']}"
            for e in extracted
        ])

        return f"""Analyze these documents and propose a workspace schema.

Documents:
{files_text}

Return a JSON object with this structure:
{{
  "entities": {{
    "entity_type_name": {{
      "description": "What this type represents",
      "directory": "entity_type_name",
      "fields": [
        {{"name": "title", "type": "string", "required": true}},
        {{"name": "date", "type": "date", "required": false}},
        ...
      ]
    }}
  }},
  "file_assignments": [
    {{"file_id": "...", "entity_type": "...", "proposed_title": "..."}}
  ],
  "analysis_summary": "Brief description of what you found"
}}

Field types: string, text, number, date, enum, list
Use lowercase snake_case for type names and field names.
Group similar documents into the same entity type.
Only output valid JSON, no other text."""

    def _parse_inference_response(self, response, extracted: list[dict]) -> dict:
        """Parse Claude's response into structured proposal."""
        text = response.content[0].text

        # Extract JSON from response
        start = text.find('{')
        end = text.rfind('}') + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON found in response")

        data = json.loads(text[start:end])

        # Add filenames to assignments
        file_map = {e["file_id"]: e["filename"] for e in extracted}
        for a in data.get("file_assignments", []):
            a["filename"] = file_map.get(a["file_id"], "")

        return data

    def infer_schema(self, library_manager) -> dict:
        """Analyze all files and propose a workspace schema."""
        extracted = self._gather_extracted_content(library_manager)

        if not extracted:
            raise ValueError("No completed files to analyze")

        prompt = self._build_inference_prompt(extracted)

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        return self._parse_inference_response(response, extracted)

    async def organize(
        self,
        schema: dict,
        file_assignments: list[dict],
        library_manager,
    ) -> AsyncGenerator[dict, None]:
        """Apply schema and create structured entities."""
        yield {"type": "started", "total_files": len(file_assignments)}

        # Write schema to workspace
        schema_path = self.workspace / ".claude" / "schema.yaml"
        schema_path.parent.mkdir(parents=True, exist_ok=True)
        schema_content = {"entities": schema.get("entities", {})}
        schema_path.write_text(yaml.dump(schema_content, default_flow_style=False))
        yield {"type": "schema_written"}

        # Process each file
        created_count = 0
        for idx, assignment in enumerate(file_assignments):
            file_id = assignment["file_id"]
            entity_type = assignment["entity_type"]

            yield {
                "type": "progress",
                "file_id": file_id,
                "status": "processing",
                "index": idx + 1,
            }

            try:
                entity_id = self._create_structured_entity(
                    file_id, entity_type, schema, library_manager
                )
                created_count += 1
                yield {
                    "type": "entity_created",
                    "file_id": file_id,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                }
            except Exception as e:
                yield {"type": "error", "file_id": file_id, "error": str(e)}

        yield {"type": "complete", "created_count": created_count}

    def _create_structured_entity(
        self,
        file_id: str,
        entity_type: str,
        schema: dict,
        library_manager,
    ) -> str:
        """Extract fields and create structured entity in workspace."""
        # Get library file and its extracted content
        lib_file = library_manager.get_file(file_id)
        if not lib_file:
            raise ValueError(f"File not found: {file_id}")

        extracted_content = library_manager.get_extracted_content(file_id)
        if not extracted_content:
            raise ValueError(f"No extracted content for file: {file_id}")

        # Get schema fields for this type
        type_schema = schema.get("entities", {}).get(entity_type, {})
        fields = type_schema.get("fields", [])

        # Ask Claude to extract fields
        field_names = [f["name"] for f in fields if f["name"] != "title"]

        if field_names:
            prompt = f"""Extract structured data from this document.

Document:
{extracted_content[:6000]}

Extract these fields: {', '.join(field_names)}

Return JSON with these fields. Use null for fields you cannot extract:
{{
  "title": "A good title for this document",
  {', '.join([f'"{f}": ...' for f in field_names])}
}}

Only output valid JSON, no other text."""

            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse extracted fields
            text = response.content[0].text
            start = text.find('{')
            end = text.rfind('}') + 1
            extracted = json.loads(text[start:end])
        else:
            # No fields to extract, just use filename as title
            extracted = {"title": Path(lib_file.filename).stem}

        # Build extra metadata from extracted fields + any library extras (like duration)
        extra_metadata = {k: v for k, v in extracted.items() if k != "title" and v is not None}
        lib_extra = library_manager.get_extra_metadata(file_id)
        if lib_extra:
            extra_metadata.update(lib_extra)

        # Create entity in workspace
        entity_id = library_manager._create_entity(
            entity_type=entity_type,
            title=extracted.get("title", Path(lib_file.filename).stem),
            content=extracted_content,
            source_file=file_id,
            source_filename=lib_file.filename,
            extra_metadata=extra_metadata if extra_metadata else None,
        )

        # Update library file to reference the created entity
        library_manager._update_file_entity(file_id, entity_type, entity_id)

        return entity_id
