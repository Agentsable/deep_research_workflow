#!/usr/bin/env bash
set -euo pipefail

# ================================================
#  Deep Research Workflow — Plugin Installer
#  https://github.com/Yigal/deep_research_workflow
# ================================================

GITHUB_OWNER="Agentsable"
GITHUB_REPO="deep_research_workflow"
GITHUB_URL="https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}"
REPO_URL="${GITHUB_URL}.git"
PLUGIN_NAME="${GITHUB_REPO}"
INSTALL_DIR="${HOME}/.claude/plugins/${PLUGIN_NAME}"

# Detect OS
OS="$(uname -s)"
case "${OS}" in
  Linux*)  PLATFORM="linux";;
  Darwin*) PLATFORM="macos";;
  *)       echo "Error: Unsupported OS '${OS}'. This script supports macOS and Linux only."; exit 1;;
esac

echo "================================================"
echo "  Deep Research Workflow — Plugin Installer"
echo "  ${GITHUB_URL}"
echo "================================================"
echo ""
echo "Detected platform: ${PLATFORM}"
echo ""

# Check dependencies
if ! command -v git &>/dev/null; then
  echo "Error: git is not installed."
  if [ "${PLATFORM}" = "macos" ]; then
    echo "  Install with: xcode-select --install"
  else
    echo "  Install with: sudo apt-get install git  (or your distro's package manager)"
  fi
  exit 1
fi

if ! command -v claude &>/dev/null; then
  echo "Warning: claude CLI not found in PATH."
  echo "  Plugin will be installed but you'll need Claude Code to use it."
  echo "  Install Claude Code: https://docs.anthropic.com/en/docs/claude-code"
  echo ""
fi

# Create plugins directory if needed
mkdir -p "${HOME}/.claude/plugins"

# Install or update
if [ -d "${INSTALL_DIR}" ]; then
  echo "Updating existing installation..."
  git -C "${INSTALL_DIR}" pull --ff-only
else
  echo "Cloning plugin from ${GITHUB_URL}..."
  git clone "${REPO_URL}" "${INSTALL_DIR}"
fi

echo ""
echo "Installed to: ${INSTALL_DIR}"
echo ""
echo "Usage:"
echo "  claude --plugin-dir ${INSTALL_DIR}"
echo ""
echo "Or add this alias to your shell profile (~/.bashrc or ~/.zshrc):"
echo "  alias claude-research='claude --plugin-dir ${INSTALL_DIR}'"
echo ""
echo "Then run:"
echo "  /deep_research_workflow:deep-research \"your topic\""
echo ""
echo "GitHub: ${GITHUB_URL}"
echo "Issues: ${GITHUB_URL}/issues"
echo ""
echo "Done."
