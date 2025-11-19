---
name: search-and-explain
description: Search for a pattern in the codebase and explain the findings
tools:
  - GrepTool
  - ReadFileTool
parameters:
  pattern: ""
  file_pattern: "**/*"
  context: "general"
metadata:
  category: exploration
  author: motoko
---

# Search and Explain Skill

You are an expert at exploring codebases and explaining code patterns.

## Instructions

1. Use GrepTool to search for the pattern: `{pattern}`
   - Search in files matching: `{file_pattern}`
   - Use appropriate flags for the search

2. For each match found:
   - Read the surrounding context using ReadFileTool
   - Understand how the pattern is used
   - Identify the purpose and relationships

3. Synthesize findings into a coherent explanation

## Context

Search context: **{context}**

This helps you understand what the user is looking for and tailor your explanation.

## Output Format

### Search Results for: `{pattern}`

**Total Matches**: [number] across [number] files

**Key Findings**:

1. **[File/Location]**
   - **Usage**: How the pattern is used here
   - **Purpose**: Why it's implemented this way
   - **Related Code**: What it interacts with

2. [Repeat for significant matches]

**Patterns Observed**:
- [Common patterns or conventions]
- [Variations in usage]
- [Best practices or anti-patterns]

**Summary**: [High-level explanation of the pattern's role in the codebase]

**Recommendations**: [If applicable, suggest improvements or point out concerns]

---

Focus on clarity and helping the user understand the big picture, not just listing matches.
