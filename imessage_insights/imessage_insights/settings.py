"""User settings stored in ~/.imessage-insights/config.json.

Currently holds the Anthropic API key so it works across all commands and the
scheduled reminders without needing to export it in your shell each time.
"""

from __future__ import annotations

import json
import os

from . import config

CONFIG_PATH = config.OUTPUT_DIR / "config.json"


def load() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.chmod(CONFIG_PATH, 0o600)  # contains your API key — keep it private


def get_api_key() -> str | None:
    """Return the API key from the environment first, then the config file."""
    return os.environ.get("ANTHROPIC_API_KEY") or load().get("anthropic_api_key")


def set_api_key(key: str) -> None:
    update(anthropic_api_key=key.strip())


def update(**kw) -> None:
    """Merge keys into the config file (e.g. backend='ollama')."""
    data = load()
    data.update(kw)
    save(data)
