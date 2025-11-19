# Add Task Management System

## Description

Build a lightweight task management system for motoko that:
- Stores tasks in `tasks/` directory as numbered markdown files
- Uses format: `000001-task-name.md` → `000001-COMPLETED-task-name.md`
- Loads top 10 open tasks on session start
- Enables natural language interaction (no special commands)
- Agent can create, read, update, and complete tasks

## Execution

1. Create `TaskManager` class with CRUD operations
2. Integrate into Agent class
3. Update CLI to load tasks on session start
4. Update system prompt to teach agent about tasks
5. Test with sample tasks

## Status

Currently in progress...
