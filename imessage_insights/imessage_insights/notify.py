"""Native macOS notifications via ``osascript``.

No-ops (returns False) on non-macOS platforms so the rest of the tool still runs
during development on other systems.
"""

from __future__ import annotations

import platform
import subprocess


def _quote(value: str) -> str:
    """Quote a string for embedding in an AppleScript literal."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def send(
    message: str,
    title: str = "Reply reminders",
    subtitle: str | None = None,
    sound: str | None = "Glass",
) -> bool:
    """Show a notification banner. Returns True if the banner was dispatched."""
    if platform.system() != "Darwin":
        return False

    # Notifications render a single line; keep it short.
    message = message.replace("\n", " ").strip()[:240]
    script = f"display notification {_quote(message)} with title {_quote(title)}"
    if subtitle:
        script += f" subtitle {_quote(subtitle)}"
    if sound:
        script += f" sound name {_quote(sound)}"

    try:
        subprocess.run(["osascript", "-e", script], check=False, timeout=10)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
