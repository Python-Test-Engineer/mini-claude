import os
import sys
import subprocess
import shutil
import anthropic
from dotenv import load_dotenv

# ANSI color constants
GREEN  = "\033[92m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
LABEL  = " mini-claude-terminal-agent "

SYSTEM_PROMPT = """\
You are mini-claude, a terminal-based coding assistant.
You have five tools: read_file, write_file, edit_file, bash, list_files.

- Explore with list_files and read_file before making changes.
- Prefer edit_file over write_file when modifying existing files.
- Always read_file before edit_file to confirm exact text to replace.
- When using bash on Windows, use cmd.exe syntax or prefix with 'bash -c' for POSIX.
- After changes, run relevant tests or linter via bash to verify.
- Explain what you are doing, then summarize after.
- Be concise. If a task is ambiguous, ask one clarifying question first.\
"""

TOOLS = [
    {
        "name": "read_file",
        "description": "Read the full contents of a file from the filesystem.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read."}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file, creating or overwriting it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "edit_file",
        "description": (
            "Replace old_str with new_str in a file (first occurrence only). "
            "Always use read_file first to confirm the exact text."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_str": {"type": "string"},
                "new_str": {"type": "string"}
            },
            "required": ["path", "old_str", "new_str"]
        }
    },
    {
        "name": "bash",
        "description": "Execute a shell command and return stdout + stderr.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "default": 30}
            },
            "required": ["command"]
        }
    },
    {
        "name": "list_files",
        "description": "List files and directories at a path (defaults to '.').",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "default": "."}
            },
            "required": []
        }
    }
]


def tool_read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception as e:
        return f"Error reading file: {e}"


def tool_write_file(path, content):
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote {len(content)} characters to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def tool_edit_file(path, old_str, new_str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if old_str not in content:
            return f"Error: old_str not found in {path}. Use read_file to check exact content."
        with open(path, "w", encoding="utf-8") as f:
            f.write(content.replace(old_str, new_str, 1))
        return f"Successfully edited {path}"
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error editing file: {e}"


def tool_bash(command, timeout=30):
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True,
            text=True, timeout=timeout, errors="replace"
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        return output.strip() or f"(exit code {result.returncode})"
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout}s"
    except Exception as e:
        return f"Error: {e}"


def tool_list_files(path="."):
    try:
        entries = os.listdir(path)
        if not entries:
            return "(empty directory)"
        dirs  = sorted(e + "/" for e in entries if os.path.isdir(os.path.join(path, e)))
        files = sorted(e for e in entries if not os.path.isdir(os.path.join(path, e)))
        return "\n".join(dirs + files)
    except Exception as e:
        return f"Error: {e}"


def execute_tool(name, inputs):
    if name == "read_file":   return tool_read_file(inputs["path"])
    if name == "write_file":  return tool_write_file(inputs["path"], inputs["content"])
    if name == "edit_file":   return tool_edit_file(inputs["path"], inputs["old_str"], inputs["new_str"])
    if name == "bash":        return tool_bash(inputs["command"], inputs.get("timeout", 30))
    if name == "list_files":  return tool_list_files(inputs.get("path", "."))
    return f"Unknown tool: {name}"


def get_user_input():
    width = shutil.get_terminal_size((80, 24)).columns
    top    = CYAN + "─" * (width - len(LABEL) - 1) + LABEL + "─" + RESET
    bottom = CYAN + "─" * width + RESET
    print(top)
    print()          # placeholder line where input will appear
    print(bottom)
    for _ in range(3):
        print()      # 3 blank lines below the frame
    # Move cursor back up to the input placeholder line (5 lines up)
    sys.stdout.write("\033[5A\r")
    sys.stdout.flush()
    user_input = input(f"{CYAN}>{RESET} ")
    # After Enter, cursor is on the bottom line; move down past the 3 blank lines
    sys.stdout.write("\033[4B\r")
    sys.stdout.flush()
    return user_input.strip()


SLASH_COMMANDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "slash_commands")

# Extra ANSI colors for /hello
RED     = "\033[91m"
MAGENTA = "\033[95m"
BLUE    = "\033[94m"

HELLO_ART = [
    # Each tuple: (color, line)
    # H
    ("RED",     "##   ##  ######  ##      ##      #####  "),
    ("YELLOW",  "##   ##  ##      ##      ##     ##   ## "),
    ("GREEN",   "#######  ####    ##      ##     ##   ## "),
    ("CYAN",    "##   ##  ##      ##      ##     ##   ## "),
    ("MAGENTA", "##   ##  ######  ######  ######  #####  "),
]

# Letter-by-letter rows so each letter gets its own color
_H = [
    "##   ##",
    "##   ##",
    "#######",
    "##   ##",
    "##   ##",
]
_E = [
    "######",
    "##    ",
    "####  ",
    "##    ",
    "######",
]
_L = [
    "##    ",
    "##    ",
    "##    ",
    "##    ",
    "######",
]
_O = [
    " ##### ",
    "##   ##",
    "##   ##",
    "##   ##",
    " ##### ",
]

_LETTERS   = [_H, _E, _L, _L, _O]
_COLORS    = [RED, YELLOW, GREEN, CYAN, MAGENTA]
_GAP       = "  "


def print_hello_art():
    """Print a colorful block-letter HELLO using ANSI colors."""
    print()
    for row in range(5):
        line = ""
        for col, (letter, color) in enumerate(zip(_LETTERS, _COLORS)):
            line += color + letter[row] + RESET
            if col < len(_LETTERS) - 1:
                line += _GAP
        print("  " + line)
    print()


def handle_builtin_slash_command(user_input):
    """Handle built-in slash commands that produce direct output.
    Returns True if the command was handled (skip API call), False otherwise."""
    if user_input.strip() == "/hello":
        print_hello_art()
        return True
    return False


def resolve_slash_command(user_input):
    """If input starts with /command, load slash_commands/command.md and return its contents.
    Returns the original input unchanged if not a slash command or file not found."""
    if not user_input.startswith("/"):
        return user_input
    parts = user_input.split(None, 1)
    name = parts[0][1:]  # strip leading /
    args = parts[1] if len(parts) > 1 else ""
    path = os.path.join(SLASH_COMMANDS_DIR, f"{name}.md")
    if not os.path.isfile(path):
        print(f"{YELLOW}[slash]{RESET} No command found: {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        template = f.read()
    print(f"{YELLOW}[slash /{name}]{RESET}")
    # Allow $ARGUMENTS placeholder substitution like Claude Code
    return template.replace("$ARGUMENTS", args).strip()


def run_agent_loop(client):
    history = []
    while True:
        user_input = get_user_input()
        if user_input.lower() in ("exit", "quit", ""):
            print("Goodbye.")
            break

        if handle_builtin_slash_command(user_input):
            continue

        user_input = resolve_slash_command(user_input)
        if user_input is None:
            continue

        history.append({"role": "user", "content": user_input})

        while True:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=history,
            )

            # Store assistant turn (serialize pydantic → dict)
            history.append({
                "role": "assistant",
                "content": [b.model_dump() for b in response.content]
            })

            # Print text blocks
            for block in response.content:
                if block.type == "text":
                    print(f"\n{CYAN}Mini Claude:{RESET} {block.text}\n")

            if response.stop_reason == "end_turn":
                break

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        print(f"{YELLOW}[tool: {block.name}]{RESET} {str(block.input)[:120]}")
                        result = execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })
                history.append({"role": "user", "content": tool_results})
            else:
                print(f"[Stopped: {response.stop_reason}]")
                break


def main():
    load_dotenv()
    if os.name == "nt":
        os.system("")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY is not set.")
        print("  Windows: set ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)
    client = anthropic.Anthropic()
    print(f"\n{GREEN}mini-claude{RESET}  —  type 'exit' to quit\n")
    run_agent_loop(client)


if __name__ == "__main__":
    main()
