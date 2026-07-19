#!/bin/bash
# One-time setup: install dependencies and create a double-clickable launcher.
#
# Usage:  cd ~/Developer/imessage-insights && bash install.sh

set -e
REPO="$(cd "$(dirname "$0")" && pwd)"

echo "Installing the Claude library (into your user folder)…"
python3 -m pip install --user --break-system-packages anthropic >/dev/null 2>&1 \
  || python3 -m pip install --user anthropic >/dev/null 2>&1 \
  || { echo "Couldn't install 'anthropic'. Run this and paste the error:"; \
       echo "  python3 -m pip install --user --break-system-packages anthropic"; }

LAUNCHER="$HOME/Desktop/iMessage Insights.command"
cat > "$LAUNCHER" <<EOF
#!/bin/bash
cd "$REPO"
python3 -m imessage_insights
EOF
chmod +x "$LAUNCHER"

echo
echo "Done!"
echo "  • Double-click 'iMessage Insights' on your Desktop to open the menu."
echo "  • First run: pick '6) Settings' to paste your Anthropic API key,"
echo "    or run:  python3 -m imessage_insights setup"
echo
echo "If you haven't yet: System Settings → Privacy & Security → Full Disk"
echo "Access → enable Terminal, so it can read your Messages."
