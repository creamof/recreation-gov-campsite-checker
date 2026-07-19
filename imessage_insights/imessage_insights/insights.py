"""LLM-backed group-thread insights via the Claude API.

Only this module sends message text off-device (to Anthropic's API). The
explore/stats commands never call it.
"""

from __future__ import annotations

from datetime import datetime

from . import config
from .chatdb import Message
from .contacts import me_label, resolve

_SYSTEM = """You are an assistant that reads a group text-message thread and \
produces a concise, useful briefing for the user (referred to as "Me" in the \
transcript). Be specific and factual — do not invent details. Focus on what a \
busy person needs to catch up and act.

Structure your answer as markdown with these sections, omitting any that don't \
apply:
- **TL;DR** — 1-2 sentences on what this thread is currently about.
- **Key points** — the important updates or decisions (bullets).
- **Waiting on me** — anything that appears to need a reply or action from Me. \
If nothing, say "Nothing pending."
- **Open questions** — unresolved questions in the thread.
- **Vibe** — one short line on tone/sentiment if notable."""


def _render_transcript(
    messages: list[Message], contacts: dict[str, str]
) -> str:
    lines = []
    for m in messages:
        who = me_label() if m.is_from_me else resolve(m.handle, contacts)
        stamp = m.date.strftime("%Y-%m-%d %H:%M")
        body = m.text
        if m.has_attachment and not body:
            body = "[attachment]"
        lines.append(f"[{stamp}] {who}: {body}")
    return "\n".join(lines)


def _client():
    # Imported lazily so the explore/stats commands work without `anthropic`.
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError(
            "The Claude API client isn't installed. Run "
            "`pip install anthropic` to use summarize/digest."
        ) from e
    return anthropic.Anthropic()


def summarize_thread(
    title: str,
    messages: list[Message],
    contacts: dict[str, str],
) -> str:
    """Summarize a single thread. Returns markdown text."""
    if not messages:
        return "_No messages to summarize._"

    messages = messages[-config.MAX_MESSAGES_PER_SUMMARY :]
    transcript = _render_transcript(messages, contacts)
    prompt = (
        f"Thread: {title}\n"
        f"Messages: {len(messages)} "
        f"(from {messages[0].date:%Y-%m-%d} to {messages[-1].date:%Y-%m-%d})\n\n"
        f"Transcript:\n{transcript}"
    )

    with _client().messages.stream(
        model=config.MODEL,
        max_tokens=6000,
        system=_SYSTEM,
        thinking={"type": "adaptive"},
        output_config={"effort": config.EFFORT},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = stream.get_final_message()

    return "".join(b.text for b in message.content if b.type == "text").strip()


def digest(
    threads: list[tuple[str, list[Message]]],
    contacts: dict[str, str],
) -> str:
    """Summarize several active threads into one briefing."""
    parts = [f"# Group message digest — {datetime.now():%Y-%m-%d %H:%M}\n"]
    for title, messages in threads:
        parts.append(f"\n## {title}\n")
        parts.append(summarize_thread(title, messages, contacts))
    return "\n".join(parts)
