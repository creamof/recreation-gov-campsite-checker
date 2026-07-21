"""Pluggable model backend: a local open model (Llama via Ollama) or Claude.

`generate()` is the single entry point every AI feature goes through, so the
choice of local vs. cloud is one setting, not scattered across the code.

- Local (default target): talks to Ollama at http://localhost:11434 using only
  the standard library — no extra pip install, nothing leaves the machine.
- Cloud: Anthropic's Claude, for best-quality analysis.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from . import config, settings

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_LOCAL_MODEL = "llama3.1"


def backend() -> str:
    """'ollama' (local) or 'claude' (cloud). Env overrides the saved setting."""
    return (os.environ.get("IMSG_BACKEND")
            or settings.load().get("backend") or "claude").lower()


def local_model() -> str:
    return (os.environ.get("IMSG_LOCAL_MODEL")
            or settings.load().get("local_model") or DEFAULT_LOCAL_MODEL)


def describe() -> str:
    return f"local ({local_model()} via Ollama)" if backend() == "ollama" else \
        f"cloud ({config.MODEL})"


def generate(system: str, prompt: str, *, max_tokens: int = 2000,
             schema: dict | None = None) -> str:
    """Return the model's text. If `schema` is given, the text is JSON matching
    it (caller does json.loads). Raises RuntimeError on backend problems."""
    if backend() == "ollama":
        return _ollama(system, prompt, max_tokens, schema)
    return _claude(system, prompt, max_tokens, schema)


# -- Claude ------------------------------------------------------------------
def _claude(system: str, prompt: str, max_tokens: int, schema: dict | None) -> str:
    from .insights import _client  # reuses key handling + friendly errors

    kwargs: dict = dict(
        model=config.MODEL, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    if schema:
        kwargs["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
    response = _client().messages.create(**kwargs)
    if response.stop_reason == "refusal":
        return ""
    return next((b.text for b in response.content if b.type == "text"), "")


# -- Ollama (local) ----------------------------------------------------------
def ollama_available() -> bool:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def _ollama(system: str, prompt: str, max_tokens: int, schema: dict | None) -> str:
    body: dict = {
        "model": local_model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": 0.7},
    }
    if schema:
        body["format"] = schema  # Ollama constrains output to the JSON schema
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        if e.code == 404:
            raise RuntimeError(
                f"Ollama doesn't have the model '{local_model()}'. "
                f"Run:  ollama pull {local_model()}"
            ) from e
        raise RuntimeError(f"Ollama error {e.code}: {detail}") from e
    except (urllib.error.URLError, OSError) as e:
        raise RuntimeError(
            f"Can't reach Ollama at {OLLAMA_URL}. Install it from ollama.com and "
            f"make sure it's running (the app, or `ollama serve`)."
        ) from e
    return data.get("message", {}).get("content", "")
