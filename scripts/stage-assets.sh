#!/usr/bin/env bash
# Stage deployable static assets into ./dist (the directory Pulumi uploads).
# Single source of truth for "what ships". Run before `pulumi up`.
# Copies the working tree minus dev-only paths, so it works the same locally
# and in CI (where the checkout is the pushed commit).
set -euo pipefail
cd "$(dirname "$0")/.."

rsync -a --delete \
  --exclude='.git/' \
  --exclude='dist/' \
  --exclude='infra/' \
  --exclude='scripts/' \
  --exclude='tests/' \
  --exclude='docs/' \
  --exclude='.github/' \
  --exclude='.claude/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='*.md' \
  --exclude='*.zip' \
  --exclude='.gitignore' \
  ./ dist/

echo "Staged $(find dist -type f | wc -l) files into dist/:"
find dist -type f | sort
