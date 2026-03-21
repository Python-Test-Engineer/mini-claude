# How mini_claude.py Works
### A teaching guide for students building coding agents

---

## What Are We Building?

A **coding agent** is a program that lets an AI model do things in the real world — read files, write code, run commands — not just chat. Instead of the AI returning words, it returns *actions*, and your program carries them out.

This project is a minimal version of Claude Code: a terminal app where you type requests, and the AI autonomously reads, edits, and runs code to complete them.

---

## The Big Picture

```
┌─────────────────────────────────────────────────────────────────┐
│                        mini_claude.py                           │
│                                                                 │
│  ┌──────────┐    ┌─────────────────┐    ┌────────────────────┐  │
│  │  You     │───▶│  Agentic Loop   │───▶│  Anthropic API     │  │
│  │ (terminal│◀───│  (the brain)    │◀───│  (Claude model)    │  │
│  │  input)  │    └────────┬────────┘    └────────────────────┘  │
│  └──────────┘             │                                     │
│                           │ calls                               │
│                    ┌──────▼──────┐                              │
│                    │    Tools    │                              │
│                    │  read_file  │                              │
│                    │  write_file │                              │
│                    │  edit_file  │                              │
│                    │  bash       │                              │
│                    │  list_files │                              │
│                    └─────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
```

**Key insight:** The AI never touches your filesystem directly. It *asks* your program to do things via tools, and your program decides whether to execute them. You are in control.

---

## Step 1 — Defining Tools

Before the AI can do anything, you must tell it what tools exist. This is done as a list of JSON schemas:

```python
TOOLS = [
    {
        "name": "read_file",
        "description": "Read the full contents of a file from the filesystem.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file."}
            },
            "required": ["path"]
        }
    },
    # ... more tools
]
```

Think of this like a **menu** handed to the AI. Each tool has:

| Field          | Purpose                                              |
|----------------|------------------------------------------------------|
| `name`         | The identifier the AI uses to invoke the tool        |
| `description`  | Plain English so the AI knows *when* to use it       |
| `input_schema` | A JSON Schema defining what arguments it takes       |

The AI reads the descriptions and decides which tool fits the task — it doesn't run any code itself.

---

## Step 2 — Tool Implementations

Each tool is a plain Python function:

```
Tool Schema (what AI sees)          Tool Function (what actually runs)
┌──────────────────────────┐        ┌──────────────────────────────────┐
│  name: "read_file"       │        │  def tool_read_file(path):       │
│  description: "Read..."  │  ───▶  │      with open(path) as f:       │
│  inputs: { path: str }   │        │          return f.read()         │
└──────────────────────────┘        └──────────────────────────────────┘
```

A dispatcher function (`execute_tool`) routes the AI's request to the right function:

```python
def execute_tool(name, inputs):
    if name == "read_file":   return tool_read_file(inputs["path"])
    if name == "write_file":  return tool_write_file(inputs["path"], inputs["content"])
    if name == "edit_file":   return tool_edit_file(inputs["path"], inputs["old_str"], inputs["new_str"])
    if name == "bash":        return tool_bash(inputs["command"], inputs.get("timeout", 30))
    if name == "list_files":  return tool_list_files(inputs.get("path", "."))
```

This pattern — schema + implementation + dispatcher — is the foundation of every tool-using AI agent.

---

## Step 3 — The Agentic Loop

This is the core of the whole program. There are **two nested loops**:

```
┌─────────────────────────────────────────────────────────┐
│  OUTER LOOP  (one iteration = one conversation turn)    │
│                                                         │
│   Wait for user input                                   │
│           │                                             │
│           ▼                                             │
│   ┌───────────────────────────────────────────────┐     │
│   │  INNER LOOP  (runs until AI is done)          │     │
│   │                                               │     │
│   │   Send history to API  ──────────────────┐    │     │
│   │          ▲                               │    │     │
│   │          │                               ▼    │     │
│   │   Append tool results          Get response   │     │
│   │   to history                        │         │     │
│   │          ▲                          │         │     │
│   │          │                  stop_reason?      │     │
│   │          │                     /      \       │     │
│   │          │              tool_use      end_turn│     │
│   │          │                 │               │  │     │
│   │   Execute tools ◀──────────┘          BREAK  │     │
│   └───────────────────────────────────────────────┘     │
│                                                         │
│   Go back, wait for next user input                     │
└─────────────────────────────────────────────────────────┘
```

### Why two loops?

A single user message like *"add error handling to utils.py"* might require the AI to:

1. Call `list_files` to find the file
2. Call `read_file` to read it
3. Call `edit_file` to make changes
4. Call `bash` to run the tests

Each of those is a separate API call. The inner loop keeps calling the API until the AI signals `"end_turn"` — meaning it's satisfied and has nothing more to do.

---

## Step 4 — Conversation History

The AI has no memory between API calls. You must send the *entire conversation* every time. The `history` list grows with each turn:

```
history = [
    {"role": "user",      "content": "Fix the bug in main.py"},
    {"role": "assistant", "content": [
        {"type": "text",     "text": "Let me read the file first."},
        {"type": "tool_use", "name": "read_file", "input": {"path": "main.py"}}
    ]},
    {"role": "user",      "content": [
        {"type": "tool_result", "tool_use_id": "...", "content": "def main():\n..."}
    ]},
    {"role": "assistant", "content": [
        {"type": "tool_use", "name": "edit_file", "input": {...}}
    ]},
    ...
]
```

Notice that **tool results are sent back as a user message**. This is how the API protocol works: the AI asks for a tool, you run it, and you reply with the result as if you were the user speaking.

```
You ──▶ API: "Fix the bug"
        API ──▶ You: [tool_use: read_file]
You ──▶ API: [tool_result: "def main():..."]
        API ──▶ You: [tool_use: edit_file]
You ──▶ API: [tool_result: "Successfully edited"]
        API ──▶ You: "Done! I fixed the off-by-one error."
```

---

## Step 5 — The System Prompt

The system prompt is a set of instructions given to the AI at the start of every API call. It shapes the AI's *personality and behaviour*:

```python
SYSTEM_PROMPT = """\
You are mini-claude, a terminal-based coding assistant.
You have five tools: read_file, write_file, edit_file, bash, list_files.

- Explore with list_files and read_file before making changes.
- Prefer edit_file over write_file when modifying existing files.
- Always read_file before edit_file to confirm exact text to replace.
...
"""
```

Think of the system prompt as the **job description** you hand to a new employee. Without it, the AI doesn't know what it's supposed to do or how to behave.

---

## Step 6 — The Terminal UI

The UI is built entirely with **ANSI escape codes** — special character sequences that terminals interpret as colour and cursor movement instructions.

```
\033[92m  ←  start green text
\033[96m  ←  start cyan text
\033[93m  ←  start yellow text
\033[0m   ←  reset to default
```

The input prompt draws a framed box around the cursor:

```
────────────────────────── mini-claude-terminal-agent ─
> your input here
────────────────────────────────────────────────────────
```

This is done by printing the top border, moving the cursor *up* with `\033[5A`, taking input, then moving the cursor *down* again. It's a neat trick to make a bordered prompt with only `print()` and `input()`.

---

## Step 7 — Slash Commands

There are now **two tiers** of slash commands, checked in order:

```
User types: /something args
                │
                ▼
    ┌───────────────────────────┐
    │  handle_builtin_slash_    │   mc_slash_commands.py
    │  command()                │   (Python-coded, instant)
    │  e.g. /hello              │
    └───────────┬───────────────┘
                │ not found?
                ▼
    ┌───────────────────────────┐
    │  resolve_slash_command()  │   slash_commands/*.md
    │                           │   (prompt templates)
    │  slash_commands/foo.md    │
    │  exists?                  │
    └──────┬──────────┬─────────┘
          yes         no
           │           │
           ▼           ▼
  Load .md file,   Print error,
  replace           skip API call
  $ARGUMENTS,
  send to API
```

**Built-in commands** live in `mc_slash_commands.py` and run Python code directly — no API call needed. `/hello` is the example: it prints a colourful block-letter greeting and returns immediately.

**File-based commands** live in `slash_commands/*.md`. The file's contents become the user's message to the API, with `$ARGUMENTS` replaced by anything typed after the command name. This lets you save long, reusable prompts as files — exactly how Claude Code's `/commit`, `/review`, etc. work under the hood.

---

## Step 8 — History Saving

Every session's conversation is saved to disk automatically when you exit. The `save_history()` function serialises the full `history` list plus metadata (timestamp, turn counts, model) into `output/history_<timestamp>.json`:

```python
payload = {
    "metadata": {
        "session_end":     "2026-03-21T14:00:00+00:00",
        "total_messages":  12,
        "user_turns":      4,
        "assistant_turns": 4,
        "model":           "claude-sonnet-4-6",
    },
    "messages": history,   # full conversation, tool calls and all
}
```

The `/show-history` command is a file-based slash command that sends a prompt asking Claude to produce a structured history listing. It pairs with the auto-save: the saved JSON is the machine-readable record, the `/show-history` output is a human-readable summary generated by the AI.

---

## Putting It All Together

Here is the full data flow for a single request:

```
  User types: "add a docstring to utils.py"
                         │
                         ▼
            resolve_slash_command()
            (passthrough — not a slash command)
                         │
                         ▼
            Append to history as user message
                         │
                ┌────────▼────────┐
                │   INNER LOOP    │
                │                 │
                │  API call  ◀────┤◀─────────────────┐
                │     │           │                   │
                │     ▼           │                   │
                │  tool_use?      │          Append tool results
                │  read_file      │          to history
                │     │           │                   │
                │     ▼           │                   │
                │  execute_tool() │                   │
                │  → reads file   │                   │
                │  → returns text ├───────────────────┘
                │                 │
                │  API call again │
                │     │           │
                │     ▼           │
                │  tool_use?      │
                │  edit_file      │
                │     │           │
                │     ▼           │
                │  execute_tool() │
                │  → edits file   ├───────────────────┐
                │                 │                   │
                │  API call again │          Append tool results
                │     │           │                   │
                │     ▼           │◀──────────────────┘
                │  end_turn ✓     │
                └────────┬────────┘
                         │
                         ▼
          Print Claude's reply in cyan
          Wait for next user input
```

---

## Step 9 — Project Folders

The project uses two folders as a sandbox for the agent to work in:

```
mini-claude/
├── mini_claude.py          ← the agent itself
├── mc_slash_commands.py    ← built-in slash command implementations
├── slash_commands/         ← file-based prompt templates
│   ├── hello.md
│   └── show-history.md
├── prompts/                ← design prompts used to build this project
├── data/                   ← input data the agent can read and analyse
│   ├── sales.csv           ← example dataset
│   ├── analyze_sales.py    ← script the agent wrote
│   └── sales_report.md     ← report the agent produced
└── output/                 ← files the agent writes as final deliverables
    ├── history_<timestamp>.json  ← auto-saved session history on exit
    └── ...
```

### `data/` — inputs and working files

The `data/` folder holds source material you give the agent to work with — CSVs, raw text files, datasets. The agent can use `read_file` and `list_files` to explore it, and `write_file` or `bash` to generate derived files (scripts, reports) alongside the originals.

Think of it as the agent's **in-tray**.

### `output/` — final deliverables

The `output/` folder is where the agent places finished artefacts — generated scripts, summaries, exports. Keeping outputs separate from inputs means you can always tell what the agent produced versus what you provided.

Think of it as the agent's **out-tray**.

### Why this separation matters

```
┌─────────────────────────────────────────────────────┐
│                  Agent workflow                     │
│                                                     │
│   data/sales.csv                                    │
│         │                                           │
│         │  read_file                                │
│         ▼                                           │
│   [ Agent analyses, writes code, runs it ]          │
│         │                                           │
│         │  write_file / bash                        │
│         ▼                                           │
│   data/analyze_sales.py   ← intermediate working   │
│   data/sales_report.md    ← intermediate working   │
│   output/summary.txt      ← final deliverable      │
└─────────────────────────────────────────────────────┘
```

This pattern mirrors how real coding agents are used: give them source material, let them reason and iterate, collect the outputs. It also makes it easy to reset — clear `output/` and re-run without touching your source data.

---

## Key Concepts Summary

| Concept              | What it means                                                        |
|----------------------|----------------------------------------------------------------------|
| **Tool schema**      | A JSON description of a capability you give the AI                  |
| **Tool execution**   | Your Python code that actually does the work                        |
| **Agentic loop**     | The cycle of: call API → execute tools → call API again             |
| **stop_reason**      | How the API tells you whether it wants a tool result or is finished |
| **History**          | The full conversation, resent every API call — AI has no memory     |
| **System prompt**    | Standing instructions that shape the AI's behaviour                 |
| **Built-in commands**| Python-coded slash commands in `mc_slash_commands.py` (no API call)|
| **Slash commands**   | Reusable prompt templates loaded from `slash_commands/*.md` files   |
| **History saving**   | Full conversation + metadata auto-saved to `output/` on exit        |

---

## Things to Try / Extend

Once you understand the structure, here are natural next steps:

1. **Add a new tool** — e.g. `search_files` that greps for a pattern. Add the schema to `TOOLS`, write the Python function, add a line to `execute_tool`.

2. **Add a new slash command** — create `slash_commands/explain.md` with a prompt template. No code changes needed.

3. **Add a `/resume` command** — load a `history_<timestamp>.json` from `output/` back into memory so the agent can continue a previous session.

4. **Add a confirmation step** — before executing `bash` commands, print the command and ask the user to approve it.

5. **Stream the response** — use `client.messages.stream()` instead of `client.messages.create()` to print the AI's reply word-by-word as it arrives.

Each of these is a small, isolated change — which is exactly what makes this single-file architecture a great learning base.
