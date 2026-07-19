"""Configuration and shared constants."""

from __future__ import annotations

import os
from pathlib import Path

# Default location of the Messages database on macOS.
DEFAULT_DB_PATH = Path.home() / "Library" / "Messages" / "chat.db"

# AddressBook source databases, used to map phone/email handles to names.
ADDRESSBOOK_GLOB = (
    Path.home()
    / "Library"
    / "Application Support"
    / "AddressBook"
    / "Sources"
)

# Apple's "Mac absolute time" epoch (2001-01-01) offset from the Unix epoch.
APPLE_EPOCH_OFFSET = 978_307_200  # seconds

# --- Claude API settings (used only by summarize/digest) ---------------------
# Overridable via environment so you don't have to edit code.
MODEL = os.environ.get("IMSG_MODEL", "claude-opus-4-8")
# Effort trades quality vs. cost/latency: low | medium | high | xhigh | max.
EFFORT = os.environ.get("IMSG_EFFORT", "medium")

# Safety caps so a single huge thread can't blow up a request.
MAX_MESSAGES_PER_SUMMARY = int(os.environ.get("IMSG_MAX_MESSAGES", "300"))

# --- Reply reminders (followups / schedule) ---------------------------------
# Where briefs and logs are written.
OUTPUT_DIR = Path(
    os.environ.get("IMSG_OUTPUT_DIR", str(Path.home() / ".imessage-insights"))
)
BRIEF_PATH = OUTPUT_DIR / "followups.md"

# Optional name-overrides / people notes (display names, your own name, pronouns).
PEOPLE_PATH = OUTPUT_DIR / "people.json"

# launchd LaunchAgent identity and default reminder times.
LAUNCHD_LABEL = "com.imessage-insights.followups"
DEFAULT_REMINDER_TIMES = os.environ.get("IMSG_REMINDER_TIMES", "9:00,13:00,17:30")

# Most waiting threads to rank in a single reminder run.
MAX_FOLLOWUPS = int(os.environ.get("IMSG_MAX_FOLLOWUPS", "25"))
