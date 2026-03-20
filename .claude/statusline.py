#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
# ]
# ///
"""
Status Line - 3-line display
Line 1  — model | git branch | context window bar (1 dot=10%) | % used | ~tokens left | ♻ session elapsed | $cost
Line 2  — session: tokens used in last 5 hours across all projects, as % of CLAUDE_SESSION_LIMIT env var
           (approximates the "Current session" shown by /usage — set CLAUDE_SESSION_LIMIT to match your plan)
Line 3  — weekly:  token usage this Mon–Sun week (summed from ~/.claude/stats-cache.json dailyModelTokens)
           as % of CLAUDE_WEEKLY_LIMIT (env var, default 10 000 000) | ♻ resets next Mon
Example output:
  Sonnet 4.6 | main | ●●○○○○○○○○ 22.5% ~155k left ♻ 3hr 10min | $0.0042
  session  ●●●○○○○○○○  25%  ♻ 3h 45m
  weekly   ●●●●●○○○○○   3%  ♻ Mon
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(Path.home() / ".claude" / ".env")  # global Claude config
    load_dotenv()  # project-level .env (can override global)
except ImportError:
    pass
# ANSI color codes
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
DIM = "\033[90m"
RESET = "\033[0m"
RECYCLE = "\u267b"
SESSION_TIMES_FILE = Path.home() / ".claude" / "session_times.json"
STATS_FILE = Path.home() / ".claude" / "stats-cache.json"
PROJECTS_DIR = Path.home() / ".claude" / "projects"
SESSION_HOURS = 5
# Limits — override via env vars
DEFAULT_SESSION_LIMIT = int(os.environ.get("CLAUDE_SESSION_LIMIT", "40000000"))
DEFAULT_WEEKLY_LIMIT = int(os.environ.get("CLAUDE_WEEKLY_LIMIT", "10000000"))
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_session_start_time(session_id):
    SESSION_TIMES_FILE.parent.mkdir(parents=True, exist_ok=True)
    session_times = {}
    if SESSION_TIMES_FILE.exists():
        try:
            with open(SESSION_TIMES_FILE) as f:
                session_times = json.load(f)
        except (json.JSONDecodeError, ValueError):
            session_times = {}
    if session_id in session_times:
        return datetime.fromisoformat(session_times[session_id])
    start_time = datetime.now()
    session_times[session_id] = start_time.isoformat()
    if len(session_times) > 50:
        sorted_s = sorted(session_times.items(), key=lambda x: x[1], reverse=True)
        session_times = dict(sorted_s[:50])
    try:
        with open(SESSION_TIMES_FILE, "w") as f:
            json.dump(session_times, f, indent=2)
    except Exception:
        pass
    return start_time
def format_elapsed(start_time):
    total_s = int((datetime.now() - start_time).total_seconds())
    if total_s < 60:
        return f"{total_s}s"
    elif total_s < 3600:
        return f"{total_s // 60}m {total_s % 60}s"
    else:
        return f"{total_s // 3600}h {(total_s % 3600) // 60}m"
def duration_color(start_time):
    mins = (datetime.now() - start_time).total_seconds() / 60
    if mins < 30:
        return GREEN
    if mins < 60:
        return YELLOW
    if mins < 120:
        return MAGENTA
    return RED
def fmt_tokens(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)
def pct_color(pct):
    if pct < 50:
        return GREEN
    if pct < 80:
        return YELLOW
    return RED
def make_dot_bar(filled, total=10):
    filled = max(0, min(total, int(filled)))
    try:
        bar = "●" * filled + "○" * (total - filled)
        bar.encode(sys.stdout.encoding or "utf-8")
        return bar
    except (UnicodeEncodeError, LookupError):
        return "#" * filled + "-" * (total - filled)
def get_git_branch():
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return None
def get_cost(input_data):
    u = input_data.get("usage", {})
    cost = u.get("cost_usd", u.get("costUSD", None))
    if cost is None:
        try:
            with open(STATS_FILE) as f:
                stats = json.load(f)
            cost = sum(
                m.get("costUSD", 0) for m in stats.get("modelUsage", {}).values()
            )
        except Exception:
            pass
    return cost
# ---------------------------------------------------------------------------
# Session window token counting (last 5 hours from project JSONL files)
# ---------------------------------------------------------------------------
def _tail_tokens_from_file(filepath: Path, cutoff_ts: str) -> int:
    tokens = 0
    chunk_size = 65536
    try:
        with open(filepath, "rb") as f:
            f.seek(0, 2)
            pos = f.tell()
            remainder = b""
            done = False
            while pos > 0 and not done:
                read_size = min(chunk_size, pos)
                pos -= read_size
                f.seek(pos)
                chunk = f.read(read_size) + remainder
                parts = chunk.split(b"\n")
                remainder = parts[0]
                lines = parts[1:]
                for raw in reversed(lines):
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        entry = json.loads(raw)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    ts = entry.get("timestamp", "")
                    if ts and ts < cutoff_ts:
                        done = True
                        break
                    msg = entry.get("message")
                    if isinstance(msg, dict):
                        usage = msg.get("usage")
                        if isinstance(usage, dict):
                            tokens += usage.get("input_tokens", 0)
                            tokens += usage.get("output_tokens", 0)
                            tokens += usage.get("cache_creation_input_tokens", 0)
                            tokens += usage.get("cache_read_input_tokens", 0)
            if not done and remainder.strip():
                try:
                    entry = json.loads(remainder)
                    ts = entry.get("timestamp", "")
                    if not ts or ts >= cutoff_ts:
                        msg = entry.get("message")
                        if isinstance(msg, dict):
                            usage = msg.get("usage")
                            if isinstance(usage, dict):
                                tokens += usage.get("input_tokens", 0)
                                tokens += usage.get("output_tokens", 0)
                                tokens += usage.get("cache_creation_input_tokens", 0)
                                tokens += usage.get("cache_read_input_tokens", 0)
                except (json.JSONDecodeError, ValueError):
                    pass
    except Exception:
        pass
    return tokens
def get_session_stats():
    now = datetime.now()
    cutoff = now - timedelta(hours=SESSION_HOURS)
    cutoff_ts = cutoff.isoformat(timespec="milliseconds")
    total_tokens = 0
    try:
        for jsonl_file in PROJECTS_DIR.rglob("*.jsonl"):
            try:
                mtime = datetime.fromtimestamp(jsonl_file.stat().st_mtime)
                if mtime < cutoff:
                    continue
            except Exception:
                continue
            total_tokens += _tail_tokens_from_file(jsonl_file, cutoff_ts)
    except Exception:
        pass
    limit = DEFAULT_SESSION_LIMIT
    pct = min(100.0, total_tokens / limit * 100) if limit > 0 else 0.0
    hour_utc = now.utctimetuple().tm_hour
    block_start_h = (hour_utc // SESSION_HOURS) * SESSION_HOURS
    block_end = now.replace(
        hour=block_start_h, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
    ).replace(tzinfo=None) + timedelta(hours=SESSION_HOURS)
    utc_offset_s = -datetime.now(timezone.utc).utcoffset().total_seconds() * -1
    block_end_local = block_end + timedelta(seconds=utc_offset_s)
    remaining_s = (block_end_local - now).total_seconds()
    if remaining_s < 0:
        remaining_s += SESSION_HOURS * 3600
    remaining_m = int(remaining_s / 60)
    if remaining_m >= 60:
        time_str = f"~{remaining_m // 60}h {remaining_m % 60}m"
    else:
        time_str = f"~{remaining_m}m"
    return pct, total_tokens, limit, time_str
# ---------------------------------------------------------------------------
# Weekly stats (from stats-cache.json)
# ---------------------------------------------------------------------------
def get_weekly_stats():
    now = datetime.now()
    today = now.date()
    week_start_date = today - timedelta(days=today.weekday())  # Monday
    week_start_dt = datetime.combine(week_start_date, datetime.min.time())
    cutoff_ts = week_start_dt.isoformat(timespec="milliseconds")
    weekly_tokens = 0
    try:
        for jsonl_file in PROJECTS_DIR.rglob("*.jsonl"):
            try:
                mtime = datetime.fromtimestamp(jsonl_file.stat().st_mtime)
                if mtime < week_start_dt:
                    continue
            except Exception:
                continue
            weekly_tokens += _tail_tokens_from_file(jsonl_file, cutoff_ts)
    except Exception:
        pass
    limit = DEFAULT_WEEKLY_LIMIT
    pct = min(100.0, weekly_tokens / limit * 100) if limit > 0 else 0.0
    days_to_monday = (7 - today.weekday()) % 7 or 7
    next_monday = datetime.combine(today + timedelta(days=days_to_monday), datetime.min.time())
    remaining_s = (next_monday - now).total_seconds()
    remaining_h = int(remaining_s // 3600)
    remaining_d = remaining_h // 24
    remaining_h_part = remaining_h % 24
    if remaining_d > 0:
        reset = f"{remaining_d}d {remaining_h_part}h"
    else:
        reset = f"{remaining_h_part}h"
    return pct, weekly_tokens, limit, reset
def get_last_prompt(session_id: str, max_len: int = 80) -> str:
    try:
        prompt_file = Path.home() / ".claude" / f"last_prompt_{session_id}.txt"
        if not prompt_file.exists():
            return ""
        text = prompt_file.read_text(encoding="utf-8").replace("\r\n", " ").replace("\n", " ").strip()
        if not text:
            return ""
        return text[:max_len - 1] + "…" if len(text) > max_len else text
    except Exception:
        return ""
def usage_row(label, dot_bar, pct, col, recycle_label):
    return (
        f"{DIM}{label:<8}{RESET}"
        f"{DIM}{dot_bar}{RESET}  "
        f"{col}{pct:.0f}%{RESET}  "
        f"{DIM}{RECYCLE}{RESET} {recycle_label}"
    )
# ---------------------------------------------------------------------------
# Main status generator
# ---------------------------------------------------------------------------
def generate_status_line(input_data):
    model_name = input_data.get("model", {}).get("display_name", "Claude")
    session_id = input_data.get("session_id", "default")
    ctx_pct = None
    remaining = None
    cw = input_data.get("context_window", {})
    if cw:
        raw_pct = cw.get("used_percentage", 0) or 0
        ctx_size = cw.get("context_window_size", 200000) or 200000
        if raw_pct:
            ctx_pct = raw_pct
            remaining = int(ctx_size * (100 - raw_pct) / 100)
    start_time = get_session_start_time(session_id)
    elapsed_str = format_elapsed(start_time)
    dur_col = duration_color(start_time)
    sess_pct, sess_tok, sess_limit, sess_reset = get_session_stats()
    weekly_pct, weekly_tok, weekly_limit, week_reset = get_weekly_stats()
    branch = get_git_branch()
    cost = get_cost(input_data)
    last_prompt = get_last_prompt(session_id)
    # ── Line 1 ──────────────────────────────────────────────────────────────
    if ctx_pct is not None:
        dots1 = ctx_pct // 10
        col1 = pct_color(ctx_pct)
        pct_part = f" {col1}{ctx_pct:.1f}%{RESET}"
        left_part = f" {BLUE}~{fmt_tokens(remaining)} left{RESET}" if remaining else ""
    else:
        elapsed_mins = (datetime.now() - start_time).total_seconds() / 60
        dots1 = min(10, int(elapsed_mins / 6))
        pct_part = ""
        left_part = ""
    line1_parts = [f"{CYAN}{model_name}{RESET}"]
    if branch:
        line1_parts.append(f"{BLUE}{branch}{RESET}")
    line1_parts.append(
        f"{DIM}ctx {make_dot_bar(dots1)}{RESET}"
        f"{pct_part}{left_part}"
        f" {DIM}{RECYCLE}{RESET} {dur_col}{elapsed_str}{RESET}"
    )
    if cost and cost > 0:
        line1_parts.append(f"{GREEN}${cost:.4f}{RESET}")
    line1 = " | ".join(line1_parts)
    # ── Line 2: session window ───────────────────────────────────────────────
    sess_col = pct_color(sess_pct)
    line2 = usage_row(
        "session",
        make_dot_bar(sess_pct // 10),
        sess_pct,
        sess_col,
        f"Time left: {sess_col}{sess_reset}{RESET}  Used: {DIM}{fmt_tokens(sess_tok)}/{fmt_tokens(sess_limit)}{RESET}",
    )
    # ── Line 3: weekly ──────────────────────────────────────────────────────
    weekly_col = pct_color(weekly_pct)
    line3 = usage_row(
        "weekly",
        make_dot_bar(weekly_pct // 10),
        weekly_pct,
        weekly_col,
        f"Time left: {weekly_col}{week_reset}{RESET}  {DIM}{fmt_tokens(weekly_tok)}/{fmt_tokens(weekly_limit)}{RESET}",
    )
    lines = [f"{MAGENTA}▶{RESET} {DIM}{last_prompt}{RESET}", line1, line2, line3] if last_prompt else [line1, line2, line3]
    return "\n".join(lines)
# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8")
        input_data = json.loads(sys.stdin.read())
        status_line = generate_status_line(input_data)
        print(status_line)
        sys.exit(0)
    except json.JSONDecodeError:
        print(f"{RED}[Claude] Error: Invalid JSON{RESET}")
        sys.exit(0)
    except Exception as e:
        print(f"{RED}[Claude] Error: {e}{RESET}")
        sys.exit(0)
if __name__ == "__main__":
    main()
