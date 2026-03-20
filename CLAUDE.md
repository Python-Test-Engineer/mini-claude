# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

This is an early-stage project to build a minimal Claude Code implementation. See `PROMPT.md` for the stated goal.

## Current State

The project is implemented as a single file: `mini_claude.py`.

## Setup & Run

```bash
# Install dependencies (creates .venv automatically)
uv add anthropic

# Set API key (Windows)
set ANTHROPIC_API_KEY=sk-ant-...

# Run
uv run mini_claude.py
```

## Architecture

Single file (`mini_claude.py`), no package structure.

**Tools available to the agent:**
- `read_file` — read file contents
- `write_file` — create or overwrite a file
- `edit_file` — replace first occurrence of a string in a file
- `bash` — run a shell command, returns stdout + stderr
- `list_files` — list directory contents

**Agentic loop:**
- Outer loop: waits for user input each turn
- Inner loop: re-calls the API after each tool batch until `stop_reason == "end_turn"`
- Conversation history is kept in-memory for the session

**UI:** Two green `─` separator lines above and below the `You:` prompt. Tool calls printed in yellow, Claude's replies in cyan.
