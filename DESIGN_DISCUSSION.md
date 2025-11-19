# Design Discussion: motoko CLI - Knowledge Work Assistant

**Date**: 2025-01-18
**Context**: Building a Gemini-powered CLI for collaborative knowledge work

---

## Evolution of Understanding

### Initial Direction (Incorrect)
Started building a "Claude Code clone" focused on:
- Running code/scripts
- Testing implementations
- File operations for software development
- Proactive verification (create file → run file → verify output)

**Problem**: This was optimizing for the wrong use case.

### Actual Goal (Correct)
Building a **Gemini-powered knowledge work assistant** that:
- Focuses on **markdown and documents**, not code
- Supports **research, writing, analysis, planning**
- Is **collaborative and Socratic**, not just task-completion
- Works **incrementally with user input**, not autonomously finishing everything

---

## Core Insight: Collaboration Over Completion

### What We DON'T Want (Task Completion):
```
User: Write a report on AI ethics
Agent: [Creates entire 10-page report]
       Here's your report! ✓
```

**Problems:**
- No user input or direction
- Might not match user's vision
- No opportunity to course-correct
- Feels automated, not collaborative

### What We DO Want (Collaborative Assistant):
```
User: Write a report on AI ethics

Agent: I'd love to help! A few questions first:
       • Who's your audience? (Academic, business, general public?)
       • What aspects interest you? (Privacy, bias, transparency?)
       • What length are you thinking?

User: Business audience, focus on bias, 2-3 pages

Agent: Perfect! I suggest this approach:
       1. Executive summary
       2. What is AI bias? (1 page)
       3. Business impacts (1 page)
       4. Recommendations (1 page)

       Should I start with an outline, or would you like me to
       gather research first?

User: Outline first

Agent: Great! Here's a proposed outline:
       [Creates outline]

       How does this look? Should I expand any sections, or would
       you like to adjust the structure first?
```

**Benefits:**
- User stays in control
- Agent understands context before acting
- Iterative refinement
- Collaborative rather than automated
- Natural checkpoints for course correction

---

## Design Principles

### 1. **Ask Before Acting**
Don't assume - interrogate the user's needs:
- What's the goal?
- Who's the audience?
- What's the scope?
- What approach would they prefer?

### 2. **Offer Multiple Paths**
Present options, don't dictate:
- "We could do X or Y - which would you prefer?"
- "I can start with research or jump to an outline"
- "Should I expand this or move to the next section?"

### 3. **Build Incrementally**
Work in stages with user approval:
- Outline → Review → Draft → Review → Refine
- Research → Synthesize → Review → Expand
- Brainstorm → Organize → Review → Develop

### 4. **Check In Frequently**
Don't disappear into work:
- "How does this look?"
- "Should I continue in this direction?"
- "Would you like me to go deeper here?"
- "Is this the right level of detail?"

### 5. **Suggest, Don't Complete**
Proactive ≠ Finishing Everything:
- **Good**: "I notice this section could use examples. Should I add some?"
- **Bad**: [Just adds examples without asking]
- **Good**: "This outline is missing X. Want me to add it?"
- **Bad**: [Adds it without asking]

---

## Knowledge Work Use Cases

### Writing & Documentation
- **Blog posts**: Ideation → Outline → Draft → Refine
- **Reports**: Research → Structure → Write → Review
- **Documentation**: Organize → Write → Format → Review
- **Proposals**: Brainstorm → Outline → Write → Polish

### Research & Analysis
- **Topic research**: Questions → Sources → Synthesis → Summary
- **Comparative analysis**: Options → Criteria → Compare → Recommend
- **Data analysis**: Collect → Analyze → Visualize → Report

### Planning & Strategy
- **Project planning**: Goals → Tasks → Timeline → Resources
- **Decision making**: Context → Options → Tradeoffs → Recommend
- **Brainstorming**: Generate → Organize → Prioritize → Develop

---

## Technical Implementation

### System Prompt Strategy

**Current Issue**: Generic "be proactive" prompts don't work well with Gemini

**New Approach**: Explicit collaborative instructions
```
You are a collaborative knowledge work assistant powered by Gemini.

CORE BEHAVIOR: Work WITH the user, not FOR the user.

Before doing substantial work, ALWAYS:
1. Ask clarifying questions about goals, audience, scope
2. Offer multiple approaches and let user choose
3. Create outline or structure before full content
4. Check in before proceeding to next step

After completing a step, ALWAYS:
1. Present what you've created
2. Ask if it meets their needs
3. Offer next steps as options, not assumptions
4. Let them guide the direction

Examples:
✓ "Should I expand section 2, or refine the outline first?"
✓ "I found 3 themes. Which interests you most?"
✓ "This could go in direction X or Y. Your preference?"

✗ [Just creates entire document without asking]
✗ [Completes all steps without checkpoints]
✗ [Assumes next steps without offering options]
```

### Auto-Follow-Up Logic

**Old Pattern (Code-focused)**:
```python
if write_file and .py:
    inject "Run the file to verify"
```

**New Pattern (Knowledge work)**:
```python
if write_file and .md:
    content_type = detect_content_type(content)

    if content_type == "outline":
        inject "How does this outline look? Should I expand any sections?"

    elif content_type == "draft":
        inject "Would you like me to refine this, or move to the next section?"

    elif content_type == "research":
        inject "I've gathered this research. Should I synthesize it into a summary?"
```

### Proactive Question Triggers

Instead of auto-completing, inject questions:
- After creating outline: "Should I expand section X, or revise the structure?"
- After research: "Which of these themes should we explore deeper?"
- After draft section: "Ready for the next section, or should we refine this?"
- After analysis: "Would you like me to add visualizations or examples?"

---

## Next Steps

### 1. Update System Prompt
Rewrite to emphasize:
- Collaborative, not completion-focused
- Ask before acting
- Offer choices
- Work incrementally
- Frequent check-ins

### 2. Redesign Auto-Follow-Up
Change from "execute next step" to "offer next options":
- Detect content type in markdown files
- Inject appropriate questions based on context
- Provide 2-3 options for user to choose from

### 3. Add Content Analysis
Detect:
- Is this an outline, draft, research, analysis?
- What stage is it in? (brainstorm, draft, refine?)
- What might be missing or incomplete?
- What are logical next steps?

### 4. Test Workflows
Focus on common knowledge work tasks:
- Write a blog post
- Research a topic
- Create a project plan
- Analyze options for a decision
- Document a process

### 5. Iterate Based on Usage
- Does it ask too many questions? (annoying)
- Does it ask too few? (assumes too much)
- Are the options helpful?
- Does it feel collaborative?

---

## Key Questions to Resolve

1. **Balance**: How many questions before it becomes annoying vs helpful?

2. **Intelligence**: Should it detect user preferences over time?
   - Some users want more guidance
   - Some want less hand-holding

3. **Tool Usage**: What tools are needed for knowledge work?
   - ✓ read_file, write_file (markdown)
   - ✓ glob, grep (finding/searching docs)
   - ? web_search (research)
   - ? web_fetch (gathering sources)
   - ✗ bash (not needed for knowledge work)

4. **Default Behavior**: When should it ask vs just do?
   - Always ask for structure/approach
   - Just do for minor formatting/fixes?

5. **Context**: Should it maintain project context?
   - Remember what we're working on across sessions
   - Understand document relationships
   - Track progress on multi-step projects

---

## Success Criteria

The assistant is successful when:

✓ User feels **guided but in control**
✓ Work happens **collaboratively, not autonomously**
✓ Frequent **natural checkpoints** for feedback
✓ **Multiple paths** offered, user chooses direction
✓ **Questions asked** before substantial work
✓ **Progress is incremental** with approval at each stage
✓ User can **course-correct** easily
✓ Feels like **working with a smart assistant**, not using a tool

---

## Conclusion

**Core Shift**: From "do the task" to "help the user do the task"

**Key Behavior**: Socratic and collaborative, not autonomous and completing

**Focus**: Knowledge work (writing, research, analysis, planning) not coding

**Success**: User stays in control while agent proactively guides and supports
