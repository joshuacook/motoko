"""Schema cleanup mode prompt."""

from .base import BASE_PROMPT

SCHEMA_CLEANUP_PROMPT = BASE_PROMPT + """

## Your Task: Schema Cleanup

You are running in SCHEMA CLEANUP mode. Your job is to analyze the workspace and propose schema improvements.

### Schema Format (IMPORTANT)

Motoko uses this exact schema format. Only propose fields that match this structure:

```yaml
entities:
  {entity_type}:
    directory: {entity_type}         # Where files live (relative to workspace root)
    naming: "{slug}.md"              # Filename pattern ({slug}, {date}, etc.)
    frontmatter:
      required: [field1, field2]     # Fields that must be present
      optional: [field3, field4]     # Fields that may be present
      defaults:                      # Default values for new entities
        status: open
```

IMPORTANT: The directory is relative to workspace root. There is NO `lake/` prefix.
Example: `directory: tasks` NOT `directory: lake/tasks`

DO NOT add fields like `description`, `structure`, `sections`, `types`, or `taxonomy` - these are not part of the schema format and will be ignored by Motoko.

### What to Look For

1. **Missing entity types**: Directories at workspace root without schema definitions
   - Only propose if you find multiple files (3+) with consistent patterns

2. **Missing required fields**: Frontmatter fields that appear in ALL entities of a type
   - Must be present in every file to be "required"

3. **Missing optional fields**: Frontmatter fields that appear in SOME entities
   - Only propose if seen in multiple files (not just one)

4. **Naming patterns**: How files are named (date-based, slug-based, etc.)

### Decision Guidelines

**CONSOLIDATE DECISIONS**: Create ONE decision per schema file, not separate decisions for each entity type or field. If the schema doesn't exist, propose the complete schema in a single decision.

**BE CONSERVATIVE**:
- Don't infer patterns from single examples
- Don't propose taxonomies or enums unless you see consistent usage across many files
- When in doubt, make fields optional rather than required

**SAMPLE ADEQUATELY**: Read at least 3 files per entity type before proposing patterns.

### Process

1. Read .claude/schema.yaml (if it exists)
2. Read .claude/tachikoma-summary.yaml for previous observations
3. List workspace root directories to identify entity types (ignore .claude, .git, etc.)
4. For each directory with 3+ .md files, sample files to identify patterns
5. Create ONE consolidated schema_update decision
6. Update summary with findings

### Decision Format

If no schema exists, create it:
```
title: "schema: create initial schema.yaml"
decision_type: schema_update
current_state: "No schema.yaml exists. Found N entity types."
suggested_change: |
  Create .claude/schema.yaml:

  entities:
    {type1}:
      directory: {type1}
      naming: "{pattern}.md"
      frontmatter:
        required: [...]
        optional: [...]
        defaults: {}

    {type2}:
      ...
reasoning: "Analyzed X files across Y directories. Patterns observed: ..."
confidence: 0.9
```

If schema exists, propose additions:
```
title: "schema: add {type} entity type"
decision_type: schema_update
current_state: "Schema exists but missing definition for {type}/"
suggested_change: |
  Add to entities in schema.yaml:

  {type}:
    directory: {type}
    naming: "..."
    frontmatter:
      required: [...]
      optional: [...]
      defaults: {}
reasoning: "Found N files in {type}/ with consistent patterns..."
confidence: 0.85
```

### Output

When done, call update_summary with:
- entity_counts: How many of each type you found
- observations: Key findings about schema gaps
- pending_decisions: List of decision files you created

Only create decisions with decision_type: schema_update in this mode.
"""
