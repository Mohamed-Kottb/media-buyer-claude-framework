#!/usr/bin/env bash
# init-git.sh
# Initialize git, do the first commit, and push to a fresh GitHub repo.
#
# Usage:
#   1. Create the repo on GitHub (empty — no README, no .gitignore).
#   2. cd into this framework folder.
#   3. ./scripts/init-git.sh <github-user> <repo-name>
#
# Example:
#   ./scripts/init-git.sh Mohamed-Kottb media-buyer-claude-framework

set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <github-user> <repo-name>"
  exit 1
fi

GH_USER="$1"
REPO_NAME="$2"
REMOTE_URL="https://github.com/${GH_USER}/${REPO_NAME}.git"

# Safety: refuse if any *.local.json or .env file is present
if find . -type f \( -name "*.local.json" -o -name "*.env" -o -name "*-tokens.json" \) | grep -q .; then
  echo "❌ Found a secrets file in the tree. Aborting before init."
  echo "   These files should never exist at the framework root:"
  find . -type f \( -name "*.local.json" -o -name "*.env" -o -name "*-tokens.json" \)
  exit 1
fi

# Init
git init
git add .

# Confirm what's about to be committed
echo ""
echo "About to commit the following files:"
git diff --cached --name-only
echo ""
read -p "Continue? [y/N] " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 1
fi

git commit -m "Initial framework: README, CLAUDE.md, setup guides, brand templates"
git branch -M main
git remote add origin "$REMOTE_URL"
git push -u origin main

echo ""
echo "✅ Pushed to $REMOTE_URL"
echo "Next: enable GitHub Pages — Settings → Pages → branch: main, folder: /docs (or /(root))."
