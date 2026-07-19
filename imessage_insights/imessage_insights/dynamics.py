"""Group-chat social dynamics: objective per-person stats (local) plus a
Claude-written read on tone, humor, engagement, and who's stirring the pot.

The stats are computed entirely on-device. The qualitative analysis sends a
capped transcript + the stats to the Claude API; if that's unavailable, the
command still prints the stats.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from . import config
from .chatdb import Message
from .contacts import resolve

# Gap that marks a message as "starting" a fresh burst of conversation.
_INITIATION_GAP_HOURS = 4.0
_LAUGH = re.compile(r"(ha){2,}|l+o+l+|lmao|lmfao|rofl|😂|🤣|😹", re.IGNORECASE)
_EMOJI = re.compile(
    "[\U0001f300-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff]"
)


@dataclass
class PersonStats:
    name: str
    messages: int
    share: float          # fraction of all messages in the window
    avg_words: float
    questions_pct: float  # % of their messages containing '?'
    laughter_pct: float   # % containing laughter markers
    emoji_pct: float
    initiations: int      # conversations they kicked off after a lull
    reactions_given: int  # tapbacks they sent
    last_active: datetime


def _speaker(m: Message, contacts: dict[str, str]) -> str:
    return "Me" if m.is_from_me else resolve(m.handle, contacts)


def compute_stats(
    messages: list[Message],
    reactions: dict[str, int],
    contacts: dict[str, str],
) -> list[PersonStats]:
    """Aggregate objective per-person stats over the given messages."""
    total = len(messages)
    buckets: dict[str, dict] = {}

    prev_date: datetime | None = None
    for m in messages:
        who = _speaker(m, contacts)
        b = buckets.setdefault(
            who,
            {"n": 0, "words": 0, "q": 0, "laugh": 0, "emoji": 0, "init": 0,
             "last": m.date},
        )
        b["n"] += 1
        b["words"] += len(m.text.split())
        if "?" in m.text:
            b["q"] += 1
        if _LAUGH.search(m.text):
            b["laugh"] += 1
        if _EMOJI.search(m.text):
            b["emoji"] += 1
        if prev_date is not None and (
            (m.date - prev_date).total_seconds() / 3600 >= _INITIATION_GAP_HOURS
        ):
            b["init"] += 1
        b["last"] = m.date
        prev_date = m.date

    # Map reaction handles to display names.
    react_by_name: dict[str, int] = {}
    for handle, count in reactions.items():
        name = "Me" if handle == "me" else resolve(handle, contacts)
        react_by_name[name] = react_by_name.get(name, 0) + count

    stats = []
    for who, b in buckets.items():
        n = b["n"]
        stats.append(
            PersonStats(
                name=who,
                messages=n,
                share=n / total if total else 0.0,
                avg_words=b["words"] / n if n else 0.0,
                questions_pct=100 * b["q"] / n if n else 0.0,
                laughter_pct=100 * b["laugh"] / n if n else 0.0,
                emoji_pct=100 * b["emoji"] / n if n else 0.0,
                initiations=b["init"],
                reactions_given=react_by_name.get(who, 0),
                last_active=b["last"],
            )
        )
    stats.sort(key=lambda s: s.messages, reverse=True)
    return stats


def render_stats_table(stats: list[PersonStats]) -> str:
    """A compact markdown table of the objective stats."""
    lines = [
        "| Person | Msgs | Share | Avg words | Questions | Laughs | Emoji | Starts | Reacts |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for s in stats:
        lines.append(
            f"| {s.name} | {s.messages} | {s.share*100:.0f}% | "
            f"{s.avg_words:.0f} | {s.questions_pct:.0f}% | {s.laughter_pct:.0f}% | "
            f"{s.emoji_pct:.0f}% | {s.initiations} | {s.reactions_given} |"
        )
    return "\n".join(lines)


_SYSTEM = """You analyze the social dynamics of a group text thread for its own \
member (labeled "Me"). You're given a stats table and a transcript. Read the \
people, not just the numbers.

Ground every claim in the transcript — quote a short real example whenever you \
characterize someone. Be perceptive and candid but fair and good-natured: this \
is the user's own friend/family group, so observations should be the kind you'd \
share with a wink, not to wound. Note that you're inferring from text.

Write markdown with these sections:
- **The vibe** — the group's overall tone, energy, and what it's mostly for.
- **The cast** — one short paragraph per active person: their role/archetype \
(e.g. the ringleader, the ghost, the comedian, the peacemaker), style, and \
engagement level. Use the stats to back it up.
- **Funniest** — who brings the humor, with a quoted bit.
- **Checked out** — who barely engages or lurks.
- **Stirring the pot** — who provokes, needles, or creates friction (with \
examples). If nobody really does, say so plainly.
- **Group texture** — running jokes, alliances, recurring tensions, who talks \
to whom."""


def analyze(
    title: str,
    stats: list[PersonStats],
    messages: list[Message],
    contacts: dict[str, str],
) -> str:
    """Return a markdown dynamics report from Claude. Raises on API problems."""
    from .insights import _client  # reuse the shared client + friendly errors

    sample = messages[-config.MAX_MESSAGES_PER_SUMMARY :]
    transcript = "\n".join(
        f"[{m.date:%Y-%m-%d %H:%M}] {_speaker(m, contacts)}: {m.text}"
        for m in sample
    )
    prompt = (
        f"Group: {title}\n"
        f"Window: {len(messages)} messages "
        f"({messages[0].date:%Y-%m-%d} to {messages[-1].date:%Y-%m-%d}); "
        f"transcript below shows the most recent {len(sample)}.\n\n"
        f"Per-person stats:\n{render_stats_table(stats)}\n\n"
        f"Transcript:\n{transcript}"
    )

    with _client().messages.stream(
        model=config.MODEL,
        max_tokens=3000,
        system=_SYSTEM,
        thinking={"type": "adaptive"},
        output_config={"effort": config.EFFORT},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "refusal":
        return "_The model declined to analyze this thread._"
    return "".join(b.text for b in message.content if b.type == "text").strip()
