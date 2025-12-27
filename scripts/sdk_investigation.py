#!/usr/bin/env python3
"""
SDK Investigation Script

Investigate Claude Agent SDK event types and behavior.
Specifically looking at:
1. All event types emitted
2. Session management (session_id in init)
3. AskUserQuestion behavior via canUseTool callback
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from claude_agent_sdk import query, ClaudeAgentOptions


# Store all events for analysis
events_log = []


def log_event(event_type: str, data: dict):
    """Log an event with timestamp."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "type": event_type,
        "data": data
    }
    events_log.append(entry)
    print(f"\n{'='*60}")
    print(f"EVENT: {event_type}")
    print(f"{'='*60}")
    print(json.dumps(data, indent=2, default=str))


async def can_use_tool_handler(tool_name: str, tool_input: dict) -> dict:
    """Handle tool permission requests, including AskUserQuestion."""
    print(f"\n*** canUseTool CALLED: {tool_name} ***")
    print(f"Input: {json.dumps(tool_input, indent=2, default=str)}")

    if tool_name == "AskUserQuestion":
        print("\n!!! AskUserQuestion DETECTED !!!")
        questions = tool_input.get("questions", [])

        # Auto-answer with first option for testing
        answers = {}
        for q in questions:
            question_text = q.get("question", "")
            options = q.get("options", [])
            if options:
                # Pick first option
                first_option = options[0].get("label", "Option 1")
                answers[question_text] = first_option
                print(f"  Q: {question_text}")
                print(f"  A: {first_option} (auto-selected)")

        return {
            "behavior": "allow",
            "updatedInput": {
                "questions": questions,
                "answers": answers
            }
        }

    # Allow all other tools
    return {"behavior": "allow", "updatedInput": tool_input}


async def streaming_prompt(text: str):
    """Convert string prompt to AsyncIterable for streaming mode."""
    yield text


async def investigate_ask_user_question():
    """Test: Trigger AskUserQuestion with canUseTool callback."""
    print("\n" + "="*80)
    print("TEST: AskUserQuestion with canUseTool callback")
    print("="*80)

    options = ClaudeAgentOptions(
        model="claude-sonnet-4-20250514",
        max_turns=5,
        can_use_tool=can_use_tool_handler,
    )

    # Prompt that should trigger AskUserQuestion
    prompt_text = """I need to set up a new project. Before you do anything,
    use the AskUserQuestion tool to ask me:
    1. What programming language should we use?
    2. Should we include testing setup?

    Present these as structured questions with options."""

    async for message in query(
        prompt=streaming_prompt(prompt_text),
        options=options
    ):
        msg_type = type(message).__name__
        data = {}

        if hasattr(message, '__dict__'):
            data = {k: v for k, v in message.__dict__.items() if not k.startswith('_')}
        if hasattr(message, 'content'):
            content = message.content
            if isinstance(content, list):
                data['content_blocks'] = [
                    {
                        'type': type(block).__name__,
                        'block': str(block)[:300]
                    }
                    for block in content
                ]
            else:
                data['content'] = str(content)[:500]

        log_event(msg_type, data)


async def investigate_partial_messages():
    """Test: Capture streaming partial messages."""
    print("\n" + "="*80)
    print("TEST: Partial Messages (Streaming)")
    print("="*80)

    options = ClaudeAgentOptions(
        model="claude-sonnet-4-20250514",
        max_turns=2,
        include_partial_messages=True,  # Enable streaming events
    )

    async for message in query(
        prompt="Count from 1 to 5, one number per line.",
        options=options
    ):
        msg_type = type(message).__name__
        data = {}

        if hasattr(message, '__dict__'):
            data = {k: v for k, v in message.__dict__.items() if not k.startswith('_')}
        if hasattr(message, 'content'):
            data['content'] = str(message.content)[:200]

        log_event(msg_type, data)


async def investigate_session_persistence():
    """Test: Check session_id and resume."""
    print("\n" + "="*80)
    print("TEST: Session ID and Resume")
    print("="*80)

    session_id = None

    options = ClaudeAgentOptions(
        model="claude-sonnet-4-20250514",
        max_turns=2,
    )

    async for message in query(
        prompt="Remember the number 42. Just acknowledge briefly.",
        options=options
    ):
        msg_type = type(message).__name__
        data = {}

        if hasattr(message, '__dict__'):
            data = {k: v for k, v in message.__dict__.items() if not k.startswith('_')}

        if hasattr(message, 'subtype') and message.subtype == 'init':
            if hasattr(message, 'data') and message.data:
                session_id = message.data.get('session_id')
                print(f"\n*** SESSION ID: {session_id} ***\n")

        log_event(msg_type, data)

    if session_id:
        print("\n" + "-"*40)
        print("Testing session resume...")
        print("-"*40)

        async for message in query(
            prompt="What number did I ask you to remember?",
            options=ClaudeAgentOptions(
                resume=session_id,
                model="claude-sonnet-4-20250514",
                max_turns=2,
            )
        ):
            msg_type = type(message).__name__
            data = {}
            if hasattr(message, '__dict__'):
                data = {k: v for k, v in message.__dict__.items() if not k.startswith('_')}
            if hasattr(message, 'content'):
                data['content'] = str(message.content)[:500]
            log_event(f"RESUMED_{msg_type}", data)

        print(f"\n*** SESSION RESUME SUCCESSFUL - Same session_id: {session_id} ***")


async def main():
    """Run investigations."""
    print("\n" + "#"*80)
    print("# CLAUDE AGENT SDK INVESTIGATION")
    print("# " + datetime.now().isoformat())
    print("#"*80)

    try:
        await investigate_partial_messages()
    except Exception as e:
        print(f"Partial messages test failed: {e}")
        import traceback
        traceback.print_exc()

    try:
        await investigate_ask_user_question()
    except Exception as e:
        print(f"AskUserQuestion test failed: {e}")
        import traceback
        traceback.print_exc()

    try:
        await investigate_session_persistence()
    except Exception as e:
        print(f"Session test failed: {e}")
        import traceback
        traceback.print_exc()

    # Summary
    print("\n" + "#"*80)
    print("# SUMMARY: Event Types Observed")
    print("#"*80)

    event_types = set(e['type'] for e in events_log)
    for et in sorted(event_types):
        count = sum(1 for e in events_log if e['type'] == et)
        print(f"  {et}: {count} occurrences")

    # Save full log
    log_file = Path("/tmp/sdk_investigation_log.json")
    with open(log_file, 'w') as f:
        json.dump(events_log, f, indent=2, default=str)
    print(f"\nFull log saved to: {log_file}")


if __name__ == "__main__":
    asyncio.run(main())
