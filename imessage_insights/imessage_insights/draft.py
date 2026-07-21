"""Voice-matched draft replies.

Learns your writing style from your own past messages and proposes reply options
for a thread — draft-only. Nothing is ever sent; you review, then send yourself.
"""

from __future__ import annotations

from . import config
from .chatdb import Message
from .contacts import me_label, resolve

_SYSTEM = """You draft text-message replies in one specific person's voice — the \
user. You're given (a) real samples of how the user writes, and (b) a \
conversation thread. Produce distinct reply options the user could send as their \
next message.

Rules:
- Match their voice precisely: typical length, punctuation, capitalization, \
emoji habits, warmth, and humor. If they write short lowercase texts, so do you.
- Keep replies the length they'd actually send — usually short. Don't be more \
formal or more effusive than their samples.
- Just the reply text — no quotes, labels, or explanation.
- Never invent facts, plans, or commitments the user hasn't made. If a natural \
reply would need info you don't have, keep it light and non-committal.
- These are DRAFTS the user will review and send themselves."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "drafts": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["drafts"],
    "additionalProperties": False,
}


def draft_replies(
    thread: list[Message],
    voice: list[str],
    contacts: dict[str, str],
    n: int = 3,
    about: str | None = None,
) -> list[str]:
    """Return `n` reply-option strings in the user's voice."""
    from . import model

    me = me_label()
    voice_block = "\n".join(f"- {t}" for t in voice[:250])
    convo = "\n".join(
        f"{me if m.is_from_me else resolve(m.handle, contacts)}: {m.text}"
        for m in thread[-30:]
    )
    steer = f"\nThe user wants this reply to get across: {about}\n" if about else ""
    prompt = (
        f"How {me} writes (real samples):\n{voice_block}\n\n"
        f"Conversation so far:\n{convo}\n{steer}\n"
        f"Write {n} distinct reply options {me} could send next."
    )

    text = model.generate(_SYSTEM, prompt, max_tokens=1500, schema=_SCHEMA)
    if not text:
        return []
    import json

    try:
        return [d.strip() for d in json.loads(text).get("drafts", []) if d.strip()]
    except json.JSONDecodeError:
        return []
