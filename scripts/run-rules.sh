#!/usr/bin/env bash
#
# run-rules.sh — wrapper around tools/check_rules.py for cron / launchd.
#
# Why a wrapper?
#   cron runs with a minimal PATH, no shell rc files, and no current directory.
#   This script sets up a sane environment, finds python3, cd's into the
#   framework, runs the rules engine, and appends every line of output to
#   brands/<brand>/.state/cron.log so you can debug missed runs.
#
# Usage (in your crontab):
#   0 * * * * /full/path/to/media-buyer-claude-framework/scripts/run-rules.sh <brand>
#
# Example crontab entries (every hour, every 12 hours, weekdays only):
#   0 * * * *  /.../scripts/run-rules.sh sneakers-matrix
#   0 */12 * * *  /.../scripts/run-rules.sh sneakers-matrix
#   0 9 * * 1-5  /.../scripts/run-rules.sh sneakers-matrix

set -uo pipefail

# Resolve the framework root regardless of how this script was invoked.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

BRAND="${1:-}"
if [ -z "$BRAND" ]; then
  echo "Usage: $0 <brand-folder-name>" >&2
  exit 2
fi

LOG_DIR="$FRAMEWORK_DIR/brands/$BRAND/.state"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/cron.log"

# Common paths where python3 lives on macOS, in order of preference.
PYTHON=""
for candidate in \
  "/opt/homebrew/bin/python3" \
  "/usr/local/bin/python3" \
  "$(/usr/bin/which python3 2>/dev/null || true)" \
  "/usr/bin/python3"; do
  if [ -x "$candidate" ]; then
    PYTHON="$candidate"
    break
  fi
done

if [ -z "$PYTHON" ]; then
  echo "[$(date -u +%FT%TZ)] ERROR: no python3 found on PATH" >> "$LOG_FILE"
  exit 1
fi

cd "$FRAMEWORK_DIR"

{
  echo ""
  echo "===== $(date -u +%FT%TZ)  brand=$BRAND  python=$PYTHON ====="
  "$PYTHON" tools/check_rules.py "$BRAND"
} >> "$LOG_FILE" 2>&1
