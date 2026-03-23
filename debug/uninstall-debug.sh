#!/usr/bin/env bash
#
# Remove debug hooks from Claude Code settings.
# Optionally auto-finalizes the last debug session.
#
# Usage: bash debug/uninstall-debug.sh [project_dir]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FINALIZE_SCRIPT="$SCRIPT_DIR/finalize-debug.py"

PROJECT_DIR="${1:-$(pwd)}"
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"

SETTINGS_FILE="$PROJECT_DIR/.claude/settings.local.json"

if [ ! -f "$SETTINGS_FILE" ]; then
    echo "No settings file found at $SETTINGS_FILE"
    exit 0
fi

# Extract session info and remove hooks
python3 << PYEOF
import json
import os
import subprocess

settings_file = "$SETTINGS_FILE"
finalize_script = "$FINALIZE_SCRIPT"

with open(settings_file) as f:
    settings = json.load(f)

# Get session info before removing
debug_session = settings.pop("_debug_session", None)

# Remove debug hooks
hooks = settings.get("hooks", {})

for hook_type in ["PreToolUse", "PostToolUse"]:
    if hook_type in hooks:
        # Filter out debug hooks
        hooks[hook_type] = [
            entry for entry in hooks[hook_type]
            if not any(
                h.get("_debug_hook") for h in entry.get("hooks", [])
            )
        ]
        # Remove empty arrays
        if not hooks[hook_type]:
            del hooks[hook_type]

if not hooks:
    del settings["hooks"]

# Write back
with open(settings_file, "w") as f:
    json.dump(settings, f, indent=2)

# Auto-finalize if session exists
if debug_session:
    log_file = debug_session.get("log_file", "")
    if log_file and os.path.exists(log_file):
        print(f"Auto-finalizing session: {debug_session['session_id']}")
        subprocess.run(["python3", finalize_script, log_file])
    else:
        print(f"Session log not found: {log_file}")
else:
    print("No active debug session found.")

PYEOF

echo ""
echo "=== Debug hooks removed ==="
echo "  Settings: $SETTINGS_FILE"
echo ""
