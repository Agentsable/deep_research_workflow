#!/usr/bin/env python3
"""
Debug hook handler for deep_research_workflow plugin.

Called by Claude Code PreToolUse / PostToolUse hooks.
Captures every tool call with full input/output, timestamps, and process context.
Writes JSONL to the debug session log file.

Usage: python3 debug-hook.py <phase> <log_file>
  phase:    "pre" or "post"
  log_file: absolute path to the JSONL session log
"""

import sys
import json
import os
import time
import fcntl
from datetime import datetime, timezone


def main():
    if len(sys.argv) < 3:
        # Not enough args — approve and exit silently
        print(json.dumps({"decision": "approve"}))
        return

    phase = sys.argv[1]       # "pre" or "post"
    log_file = sys.argv[2]    # absolute path to JSONL

    # Read hook payload from stdin
    try:
        raw = sys.stdin.read()
        hook_data = json.loads(raw) if raw.strip() else {}
    except Exception:
        hook_data = {"_raw_stdin": raw if 'raw' in dir() else ""}

    now = datetime.now(timezone.utc)

    tool_name = hook_data.get("tool_name", "unknown")
    tool_input = hook_data.get("tool_input", {})

    event = {
        "event_id": f"{phase}-{int(time.time() * 1000000)}",
        "timestamp": now.isoformat(),
        "epoch_ms": int(time.time() * 1000),
        "phase": phase,
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "tool_name": tool_name,
        "tool_input": tool_input,
    }

    # Post-phase includes the full tool output
    if phase == "post":
        tool_output = hook_data.get("tool_output", None)
        event["tool_output"] = tool_output

        # Calculate output size for summary stats
        if tool_output is not None:
            if isinstance(tool_output, str):
                event["output_size_bytes"] = len(tool_output.encode("utf-8"))
            else:
                event["output_size_bytes"] = len(json.dumps(tool_output).encode("utf-8"))

    # For Agent tool calls, extract agent metadata for easier analysis
    if tool_name == "Agent":
        event["agent_metadata"] = {
            "subagent_type": tool_input.get("subagent_type", "general-purpose"),
            "description": tool_input.get("description", ""),
            "model": tool_input.get("model", None),
            "run_in_background": tool_input.get("run_in_background", False),
            "prompt_length": len(tool_input.get("prompt", "")),
            "prompt_full": tool_input.get("prompt", ""),
        }

    # For WebSearch, capture query
    if tool_name == "WebSearch":
        event["search_query"] = tool_input.get("query", tool_input.get("search_query", ""))

    # For WebFetch, capture URL
    if tool_name == "WebFetch":
        event["fetch_url"] = tool_input.get("url", "")

    # For Write, capture file path and content size
    if tool_name == "Write":
        event["write_metadata"] = {
            "file_path": tool_input.get("file_path", ""),
            "content_length": len(tool_input.get("content", "")),
        }

    # For Read, capture file path
    if tool_name == "Read":
        event["read_metadata"] = {
            "file_path": tool_input.get("file_path", ""),
        }

    # For Bash, capture command
    if tool_name == "Bash":
        event["bash_metadata"] = {
            "command": tool_input.get("command", ""),
            "description": tool_input.get("description", ""),
        }

    # For Edit, capture file and old/new strings
    if tool_name == "Edit":
        event["edit_metadata"] = {
            "file_path": tool_input.get("file_path", ""),
            "old_string_length": len(tool_input.get("old_string", "")),
            "new_string_length": len(tool_input.get("new_string", "")),
        }

    # For Glob/Grep, capture pattern
    if tool_name in ("Glob", "Grep"):
        event["search_metadata"] = {
            "pattern": tool_input.get("pattern", ""),
            "path": tool_input.get("path", ""),
        }

    # For Skill, capture skill name
    if tool_name == "Skill":
        event["skill_metadata"] = {
            "skill": tool_input.get("skill", ""),
            "args": tool_input.get("args", ""),
        }

    # For AskUserQuestion, capture the question
    if tool_name == "AskUserQuestion":
        event["question_metadata"] = {
            "question": tool_input.get("question", ""),
            "options": tool_input.get("options", []),
        }

    # Append to JSONL with file locking for concurrent writes
    try:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(event, default=str) + "\n")
            f.flush()
            fcntl.flock(f, fcntl.LOCK_UN)
    except Exception as e:
        # Never block execution due to logging failure
        sys.stderr.write(f"debug-hook: failed to write log: {e}\n")

    # Always approve — debug mode is passive observation
    print(json.dumps({"decision": "approve"}))


if __name__ == "__main__":
    main()
