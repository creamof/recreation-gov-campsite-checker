#!/bin/bash
# Pull the latest imessage-insights code and commit it into this repo.
#
# Why this exists: development happens on a branch of a different repo that this
# machine can reach, but the automated pusher can't write to this standalone
# repo directly. This script bridges that: it fetches the latest code and copies
# it in, so updating is one command instead of a manual clone-and-copy.
#
# Usage:  cd ~/Developer/imessage-insights && bash update.sh

set -euo pipefail

BRANCH="claude/mac-messaging-agent-voice-bgh3ek"
SRC="https://github.com/creamof/recreation-gov-campsite-checker.git"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Fetching the latest code…"
git clone -q -b "$BRANCH" "$SRC" "$TMP"

echo "Applying updates…"
cp -R "$TMP/imessage_insights/." ./

if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -q -m "Sync latest features from dev branch"
  if git push -q 2>/dev/null; then
    echo "Updated, committed, and pushed."
  else
    echo "Updated and committed locally (push skipped — run 'git push' to sync GitHub)."
  fi
else
  echo "Already up to date."
fi

echo "Done. Try:  python3 -m imessage_insights --help"
