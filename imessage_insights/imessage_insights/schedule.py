"""Install/remove a macOS launchd LaunchAgent that runs reply reminders.

The agent runs ``followups --notify`` at the configured times each day, so you
get a native notification without remembering to run anything.
"""

from __future__ import annotations

import os
import platform
import plistlib
import subprocess
import sys
from pathlib import Path

from . import config


def _plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{config.LAUNCHD_LABEL}.plist"


def parse_times(spec: str) -> list[tuple[int, int]]:
    """Parse "9:00,13:30" into [(9, 0), (13, 30)]."""
    times = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        hour, _, minute = chunk.partition(":")
        times.append((int(hour), int(minute or 0)))
    if not times:
        raise ValueError(f"No valid times in {spec!r}")
    return times


def _program_args(db: Path | None) -> list[str]:
    args = [sys.executable, "-m", "imessage_insights"]
    if db:
        args += ["--db", str(db)]
    args += ["followups", "--notify", "--quiet"]
    return args


def install(times: str, db: Path | None = None) -> Path:
    """Write the LaunchAgent plist and load it (macOS only)."""
    parsed = parse_times(times)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin")}
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        env["ANTHROPIC_API_KEY"] = key
    for var in ("IMSG_MODEL", "IMSG_EFFORT", "IMSG_OUTPUT_DIR"):
        if var in os.environ:
            env[var] = os.environ[var]

    data = {
        "Label": config.LAUNCHD_LABEL,
        "ProgramArguments": _program_args(db),
        "StartCalendarInterval": [{"Hour": h, "Minute": m} for h, m in parsed],
        "EnvironmentVariables": env,
        "RunAtLoad": False,
        "StandardOutPath": str(config.OUTPUT_DIR / "followups.out.log"),
        "StandardErrorPath": str(config.OUTPUT_DIR / "followups.err.log"),
    }

    path = _plist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(plistlib.dumps(data))
    # The plist may hold your API key — keep it readable only by you.
    os.chmod(path, 0o600)

    if platform.system() == "Darwin":
        subprocess.run(["launchctl", "unload", str(path)], check=False,
                       capture_output=True)
        subprocess.run(["launchctl", "load", str(path)], check=False)
    return path


def uninstall() -> bool:
    """Unload and remove the LaunchAgent. Returns True if it existed."""
    path = _plist_path()
    if platform.system() == "Darwin" and path.exists():
        subprocess.run(["launchctl", "unload", str(path)], check=False,
                       capture_output=True)
    if path.exists():
        path.unlink()
        return True
    return False


def status() -> dict:
    """Return {installed, loaded, path, times}."""
    path = _plist_path()
    info = {"installed": path.exists(), "loaded": False, "path": str(path),
            "times": []}
    if path.exists():
        try:
            data = plistlib.loads(path.read_bytes())
            info["times"] = [
                f"{e.get('Hour', 0):02d}:{e.get('Minute', 0):02d}"
                for e in data.get("StartCalendarInterval", [])
            ]
        except (plistlib.InvalidFileException, OSError):
            pass
    if platform.system() == "Darwin":
        result = subprocess.run(["launchctl", "list"], capture_output=True,
                                text=True, check=False)
        info["loaded"] = config.LAUNCHD_LABEL in result.stdout
    return info
