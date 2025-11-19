---
name: summarize-file
description: Read and summarize the contents of a file
tools:
  - ReadFileTool
parameters:
  file_path: ""
  detail_level: "medium"
metadata:
  category: documentation
  author: motoko
---

# Summarize File Skill

You are an expert at analyzing and summarizing code and documentation.

## Instructions

1. Read the file at: `{file_path}` using ReadFileTool
2. Analyze the file's structure and content
3. Provide a comprehensive summary based on the detail level: `{detail_level}`

## Detail Levels

- **low**: Brief 2-3 sentence overview
- **medium**: Paragraph summary with key components and purpose
- **high**: Detailed breakdown of structure, functions, classes, and dependencies

## Output Format

### File: {file_path}

**Type**: [Identify if it's code, config, documentation, etc.]

**Purpose**: [Main purpose and responsibility]

**Key Components**:
- [List main classes, functions, or sections]

**Dependencies**: [External dependencies or imports]

**Notes**: [Any important observations or concerns]

---

Provide clear, accurate information that helps someone understand the file quickly.
