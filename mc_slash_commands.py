# ANSI colors used by slash commands
RED     = "\033[91m"
YELLOW  = "\033[93m"
GREEN   = "\033[92m"
CYAN    = "\033[96m"
MAGENTA = "\033[95m"
RESET   = "\033[0m"

# --- /hello ---

_H = ["##   ##", "##   ##", "#######", "##   ##", "##   ##"]
_E = ["######", "##    ", "####  ", "##    ", "######"]
_L = ["##    ", "##    ", "##    ", "##    ", "######"]
_O = [" ##### ", "##   ##", "##   ##", "##   ##", " ##### "]

_LETTERS = [_H, _E, _L, _L, _O]
_COLORS  = [RED, YELLOW, GREEN, CYAN, MAGENTA]
_GAP     = "  "


def cmd_hello():
    """Print a colorful block-letter HELLO."""
    print()
    for row in range(5):
        line = ""
        for col, (letter, color) in enumerate(zip(_LETTERS, _COLORS)):
            line += color + letter[row] + RESET
            if col < len(_LETTERS) - 1:
                line += _GAP
        print("  " + line)
    print()


# --- dispatcher ---

_COMMANDS = {
    "/hello": cmd_hello,
}


def handle_builtin_slash_command(user_input):
    """Run a built-in slash command if recognised.
    Returns True if handled (caller should skip the API), False otherwise."""
    cmd = user_input.strip().split()[0] if user_input.strip() else ""
    handler = _COMMANDS.get(cmd)
    if handler:
        handler()
        return True
    return False
