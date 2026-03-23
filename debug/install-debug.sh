#!/usr/bin/env bash
#
# Install debug hooks for deep_research_workflow.
#
# Creates a new debug session and configures Claude Code hooks
# to capture every tool call with full input/output.
#
# Usage: bash debug/install-debug.sh [project_dir]
#   project_dir: the directory where you'll run /deep-research (defaults to cwd)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK_SCRIPT="$SCRIPT_DIR/debug-hook.py"
FINALIZE_SCRIPT="$SCRIPT_DIR/finalize-debug.py"

# Target project directory (where the user runs /deep-research)
PROJECT_DIR="${1:-$(pwd)}"
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"

# Create debug session
SESSION_ID="$(date +%Y%m%d-%H%M%S)"
DEBUG_DIR="$PROJECT_DIR/research/_debug"
SESSION_DIR="$DEBUG_DIR/sessions"
LOG_FILE="$SESSION_DIR/$SESSION_ID.jsonl"

mkdir -p "$SESSION_DIR"

# Write session start marker
python3 -c "
import json, time
from datetime import datetime, timezone
event = {
    'event_id': 'session-start',
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'epoch_ms': int(time.time() * 1000),
    'phase': 'session_start',
    'tool_name': '_session',
    'tool_input': {
        'session_id': '$SESSION_ID',
        'project_dir': '$PROJECT_DIR',
        'plugin_dir': '$SCRIPT_DIR/..',
    },
}
with open('$LOG_FILE', 'w') as f:
    f.write(json.dumps(event) + '\n')
"

# Create/update .claude/settings.local.json with debug hooks
CLAUDE_DIR="$PROJECT_DIR/.claude"
SETTINGS_FILE="$CLAUDE_DIR/settings.local.json"
mkdir -p "$CLAUDE_DIR"

# Build the hook commands with absolute paths
PRE_HOOK_CMD="python3 $HOOK_SCRIPT pre $LOG_FILE"
POST_HOOK_CMD="python3 $HOOK_SCRIPT post $LOG_FILE"

# Generate settings JSON
python3 << PYEOF
import json
import os

settings_file = "$SETTINGS_FILE"
existing = {}

if os.path.exists(settings_file):
    try:
        with open(settings_file) as f:
            existing = json.load(f)
    except:
        pass

# Preserve non-hook settings
hooks = existing.get("hooks", {})

# Add debug hooks (tagged so we can remove them later)
hooks["PreToolUse"] = [
    {
        "matcher": "",
        "hooks": [
            {
                "type": "command",
                "command": "$PRE_HOOK_CMD",
                "_debug_hook": True
            }
        ]
    }
]

hooks["PostToolUse"] = [
    {
        "matcher": "",
        "hooks": [
            {
                "type": "command",
                "command": "$POST_HOOK_CMD",
                "_debug_hook": True
            }
        ]
    }
]

existing["hooks"] = hooks
existing["_debug_session"] = {
    "session_id": "$SESSION_ID",
    "log_file": "$LOG_FILE",
    "finalize_command": "python3 $FINALIZE_SCRIPT $LOG_FILE"
}

with open(settings_file, "w") as f:
    json.dump(existing, f, indent=2)

PYEOF

# Create a convenience finalize script in the session dir
cat > "$DEBUG_DIR/finalize-latest.sh" << EOF
#!/usr/bin/env bash
python3 "$FINALIZE_SCRIPT" "$LOG_FILE"
EOF
chmod +x "$DEBUG_DIR/finalize-latest.sh"

echo ""
echo "=== Debug Mode Installed ==="
echo ""
echo "  Session ID:  $SESSION_ID"
echo "  Log file:    $LOG_FILE"
echo "  Project:     $PROJECT_DIR"
echo ""
echo "  Every tool call will be logged with:"
echo "    - Full input arguments"
echo "    - Full output / return values"
echo "    - Timestamps (ISO 8601 + epoch ms)"
echo "    - Process IDs (for parallel detection)"
echo "    - Tool-specific metadata"
echo ""
echo "  Now open a new Claude Code window in: $PROJECT_DIR"
echo "  and run your /deep-research command."
echo ""
echo "  When done, finalize the debug log:"
echo "    bash $DEBUG_DIR/finalize-latest.sh"
echo ""
echo "  Or uninstall debug hooks:"
echo "    bash $SCRIPT_DIR/uninstall-debug.sh $PROJECT_DIR"
echo ""
