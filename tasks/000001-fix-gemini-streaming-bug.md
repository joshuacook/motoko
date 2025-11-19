# Fix Gemini Streaming Bug

## Description

Gemini was returning parts with both `text` and `function_call` attributes, but our code used `elif` which caused text content to be skipped when function_call had an empty name.

## Execution

1. Changed `if ... elif ...` to two separate `if` statements in `gemini.py`
2. Check for text first, then also check for function_call
3. This allows parts to have both attributes and handles them independently

## Result

Fixed! Gemini now responds properly to casual conversation.
