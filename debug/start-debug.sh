#!/usr/bin/env bash
#
# One-command debug mode: install hooks + launch Claude Code with /deep-research.
#
# Usage:
#   bash debug/start-debug.sh [project_dir] [research_topic]
#
# Examples:
#   bash debug/start-debug.sh                          # current dir, no topic (will prompt)
#   bash debug/start-debug.sh ~/my-project             # specific project, no topic
#   bash debug/start-debug.sh ~/my-project "AI agents" # specific project + topic
#   bash debug/start-debug.sh . "AI agents"            # current dir + topic

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
INSTALL_SCRIPT="$SCRIPT_DIR/install-debug.sh"

PROJECT_DIR="${1:-.}"
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"
TOPIC="${2:-}"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Deep Research — Full Debug Mode        ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Step 1: Install debug hooks ──
echo "[1/3] Installing debug hooks..."
echo ""
bash "$INSTALL_SCRIPT" "$PROJECT_DIR"

# Read back the session info
SETTINGS_FILE="$PROJECT_DIR/.claude/settings.local.json"
SESSION_ID=$(python3 -c "
import json
with open('$SETTINGS_FILE') as f:
    d = json.load(f)
print(d.get('_debug_session', {}).get('session_id', 'unknown'))
")
LOG_FILE=$(python3 -c "
import json
with open('$SETTINGS_FILE') as f:
    d = json.load(f)
print(d.get('_debug_session', {}).get('log_file', ''))
")

# ── Step 2: Build the Claude command ──
echo "[2/3] Preparing Claude Code launch..."
echo ""

if [ -n "$TOPIC" ]; then
    CLAUDE_PROMPT="/deep-research $TOPIC"
else
    CLAUDE_PROMPT="/deep-research"
fi

echo "  Project:   $PROJECT_DIR"
echo "  Session:   $SESSION_ID"
echo "  Log file:  $LOG_FILE"
echo "  Command:   claude --prompt \"$CLAUDE_PROMPT\""
echo ""

# ── Step 3: Launch Claude Code ──
echo "[3/3] Launching Claude Code in debug mode..."
echo ""
echo "  ┌─────────────────────────────────────────────────┐"
echo "  │  All tool calls are being captured.              │"
echo "  │  When research completes, press Ctrl+C or exit.  │"
echo "  │                                                  │"
echo "  │  Then finalize with:                             │"
echo "  │    bash $PROJECT_DIR/research/_debug/finalize-latest.sh"
echo "  │                                                  │"
echo "  │  Or auto-finalize + cleanup:                     │"
echo "  │    bash $SCRIPT_DIR/uninstall-debug.sh $PROJECT_DIR"
echo "  └─────────────────────────────────────────────────┘"
echo ""

cd "$PROJECT_DIR"

# Launch Claude Code with the research prompt.
# --dangerously-skip-permissions avoids permission popups for every hooked tool call.
# Remove that flag if you want to approve each action manually.
if command -v claude &> /dev/null; then
    claude --prompt "$CLAUDE_PROMPT"
else
    echo "ERROR: 'claude' command not found in PATH."
    echo ""
    echo "Install Claude Code first:  npm install -g @anthropic-ai/claude-code"
    echo ""
    echo "Or launch manually in another terminal:"
    echo "  cd $PROJECT_DIR"
    echo "  claude"
    echo "  Then type: $CLAUDE_PROMPT"
    exit 1
fi

# ── Post-session: auto-finalize ──
echo ""
echo "Session ended. Finalizing debug log..."
echo ""

FINALIZE_SCRIPT="$PROJECT_DIR/research/_debug/finalize-latest.sh"
if [ -f "$FINALIZE_SCRIPT" ]; then
    bash "$FINALIZE_SCRIPT"
else
    echo "Finalize script not found at $FINALIZE_SCRIPT"
    echo "Run manually: python3 $SCRIPT_DIR/finalize-debug.py $LOG_FILE"
fi

echo ""
echo "To remove debug hooks:"
echo "  bash $SCRIPT_DIR/uninstall-debug.sh $PROJECT_DIR"
echo ""
