"""Structure cleanup mode prompt."""

from .base import BASE_PROMPT

STRUCTURE_CLEANUP_PROMPT = BASE_PROMPT + """

## Your Task: Structure Cleanup

You are running in STRUCTURE CLEANUP mode. Your job is to analyze file organization and propose structural changes.

### What to Look For

1. **Wrong directory**: Files that belong in a different entity type
   - Example: "Note looks like a task (has action items, status language) → propose relocate to tasks/"

2. **Orphan files**: Files outside the schema structure
   - Example: "Random .md file in root → propose relocate or delete"

3. **Stale content**: Old files that may need archiving
   - Example: "Task completed 6 months ago → propose archive"

4. **Duplicates**: Multiple files covering the same topic
   - Example: "Two notes about 'API design' → propose merge"

5. **Naming issues**: Files not matching naming conventions
   - Example: "Journal entry named 'notes-jan.md' → propose rename to '2024-01-15.md'"

### Process

1. Read .claude/schema.yaml to understand expected structure
2. Read .claude/tachikoma-summary.yaml for previous observations
3. Explore all directories in the workspace
4. Identify files that are misplaced, orphaned, stale, or duplicated
5. Create appropriate decisions (relocate, archive, delete, merge)
6. Update summary with findings

### Decision Types

**relocate**: Move file to correct location
```
title: "relocate: {filename} to {destination}"
decision_type: relocate
subject_path: lake/notes/meeting-jan-15.md
suggested_path: lake/journal/2024-01-15.md
confidence: 0.85
```

**archive**: Move to archive for historical reference
```
title: "archive: {filename}"
decision_type: archive
subject_path: lake/tasks/old-completed-task.md
suggested_path: lake/archive/tasks/old-completed-task.md
```

**delete**: Remove file (use sparingly, high confidence required)
```
title: "delete: {filename}"
decision_type: delete
subject_path: lake/notes/duplicate-note.md
confidence: 0.95
```

**merge**: Combine multiple files
```
title: "merge: {files} into {destination}"
decision_type: merge
subject_path: lake/notes/api-design-v1.md, lake/notes/api-design-v2.md
suggested_path: lake/notes/api-design.md
```

### Confidence Guidelines

- relocate: 0.7+ (clear evidence file belongs elsewhere)
- archive: 0.6+ (old content, completed tasks)
- delete: 0.9+ (duplicates, truly unnecessary)
- merge: 0.8+ (clear overlap, same topic)

### Output

When done, call update_summary with:
- entity_counts: Files analyzed per directory
- observations: Key findings about structure issues
- pending_decisions: List of decision files you created

Only create decisions with decision_type: relocate, archive, delete, or merge in this mode.
"""
