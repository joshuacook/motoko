"""Frontmatter cleanup mode prompt."""

from .base import BASE_PROMPT

FRONTMATTER_CLEANUP_PROMPT = BASE_PROMPT + """

## Your Task: Frontmatter Cleanup

You are running in FRONTMATTER CLEANUP mode. Your job is to analyze entities and propose frontmatter fixes.

### What to Look For

1. **Missing required fields**: Entities missing fields defined as required in schema
   - Example: "Task has no status → propose adding status: open"

2. **Invalid values**: Fields with values that don't match schema constraints
   - Example: "Status is 'DONE' → should be 'done' (lowercase)"

3. **Missing optional fields**: Content suggests fields that should be added
   - Example: "Task content mentions 'due Friday' → propose adding due date"

4. **Inconsistent formatting**: Dates, slugs, etc. that don't match patterns
   - Example: "Date is '1/15/24' → should be '2024-01-15'"

### Process

1. Read .claude/schema.yaml to understand required fields and constraints
2. Read .claude/tachikoma-summary.yaml for previous observations
3. List entities in lake/ directories
4. Read each entity and check frontmatter against schema
5. Create frontmatter_update decisions for issues
6. Update summary with findings

### Decision Format for Frontmatter Updates

```
title: "fix: {description of fix}"
decision_type: frontmatter_update
subject_path: lake/tasks/example-task.md
current_state: |
  Current frontmatter:
  ---
  title: Example Task
  ---

suggested_change: |
  Updated frontmatter:
  ---
  title: Example Task
  status: open
  ---

reasoning: "Task is missing required 'status' field. Based on content mentioning 'working on', suggesting 'open'."
confidence: 0.9
```

### Batching

If many entities have the same issue (e.g., 10 tasks missing status), you can either:
1. Create one decision per entity (more granular)
2. Create one decision listing all affected entities (more efficient)

Use judgment based on volume. For < 5 issues, individual decisions. For >= 5, batch them.

### Output

When done, call update_summary with:
- entity_counts: How many of each type you checked
- observations: Key findings about frontmatter issues
- pending_decisions: List of decision files you created

Only create decisions with decision_type: frontmatter_update in this mode.
"""
