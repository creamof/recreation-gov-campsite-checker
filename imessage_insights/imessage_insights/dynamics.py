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
from .contacts import me_label, notes, resolve

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
    return me_label() if m.is_from_me else resolve(m.handle, contacts)


def _people_context() -> str:
    """Authoritative participant notes for the model (identity, pronouns)."""
    lines = [
        f'In the transcript, the account owner (the user) is labeled "{me_label()}".'
    ]
    for name, note in notes().items():
        lines.append(f"- {name}: {note}")
    if len(lines) > 1:
        lines.insert(1, "Use the correct name and pronouns for each person below:")
    return "\n".join(lines)


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


# Optional lenses that sharpen the analysis toward one dimension.
FOCUS_PROMPTS = {
    "balanced": "",
    "tension": "\n\nSHARPEN THE FOCUS on friction and pot-stirring. Name who "
    "provokes, needles, baits, or escalates, and who's passive-aggressive. Map "
    "any factions or alliances and who sides with whom. Call out recurring "
    "flashpoints and what sets them off, and who tends to defuse. Quote the "
    "moments. Distinguish playful ribbing from genuine tension — be fair, but "
    "don't soften real friction into nothing.",
    "humor": "\n\nSHARPEN THE FOCUS on comedy. Identify who actually makes the "
    "group laugh (not just who laughs), each person's comedic style (dry, "
    "absurd, roast, self-deprecating), the running bits, and the single funniest "
    "line in the sample. Quote liberally.",
    "engagement": "\n\nSHARPEN THE FOCUS on who carries the chat versus who "
    "coasts. Who initiates and sustains conversation, who only reacts, who's "
    "drifting away, and whether replies are reciprocated. Note anyone who seems "
    "to be pulling back over time.",
}


def _extract_text(message) -> str:
    """Pull the final text out of a streamed message, handling edge cases."""
    if message.stop_reason == "refusal":
        return "_The model declined to analyze this thread._"
    text = "".join(b.text for b in message.content if b.type == "text").strip()
    if not text:
        return ("_The model ran out of output budget before writing its answer. "
                "Try again, or set IMSG_EFFORT=low for a shorter pass._")
    return text


def analyze(
    title: str,
    stats: list[PersonStats],
    messages: list[Message],
    contacts: dict[str, str],
    focus: str = "balanced",
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
        f"{_people_context()}\n\n"
        f"Per-person stats:\n{render_stats_table(stats)}\n\n"
        f"Transcript:\n{transcript}"
    )

    with _client().messages.stream(
        model=config.MODEL,
        max_tokens=16000,
        system=_SYSTEM + FOCUS_PROMPTS.get(focus, ""),
        thinking={"type": "adaptive"},
        output_config={"effort": config.EFFORT},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = stream.get_final_message()

    return _extract_text(message)


# --- Timeline: how the group's dynamics shifted over time -------------------
def bucket_by_period(messages: list[Message], by: str = "year") -> dict:
    """Group messages into ordered time buckets ("2021", "2021 Q2", "2021-06")."""
    buckets: dict[str, list[Message]] = {}
    for m in messages:
        if by == "quarter":
            label = f"{m.date.year} Q{(m.date.month - 1) // 3 + 1}"
        elif by == "month":
            label = f"{m.date:%Y-%m}"
        else:
            label = str(m.date.year)
        buckets.setdefault(label, []).append(m)
    return buckets


def filter_periods(buckets: dict, min_fraction: float = 0.03) -> tuple[dict, list]:
    """Drop periods that are too small to be meaningful (e.g. a 5-message year).

    A period is kept if it has at least ``min_fraction`` of the busiest period's
    message count (floor of 10). Returns (kept_buckets, dropped_labels).
    """
    if not buckets:
        return buckets, []
    biggest = max(len(m) for m in buckets.values())
    threshold = max(10, int(biggest * min_fraction))
    kept, dropped = {}, []
    for label, msgs in buckets.items():
        (kept.__setitem__(label, msgs) if len(msgs) >= threshold
         else dropped.append(label))
    return (kept or buckets), dropped


def _trend(shares: list[float]) -> str:
    if len(shares) < 2:
        return "→"
    delta = shares[-1] - shares[0]
    return "↑" if delta > 5 else "↓" if delta < -5 else "→"


def timeline_share_table(buckets: dict, contacts: dict[str, str], top: int = 8) -> str:
    """Markdown table of each person's % share of messages per period."""
    periods = list(buckets.keys())
    period_totals = {p: len(msgs) for p, msgs in buckets.items()}
    per: dict[str, dict[str, int]] = {}
    totals: dict[str, int] = {}
    for p, msgs in buckets.items():
        for m in msgs:
            name = _speaker(m, contacts)
            per.setdefault(name, {})
            per[name][p] = per[name].get(p, 0) + 1
            totals[name] = totals.get(name, 0) + 1

    people = sorted(totals, key=lambda n: totals[n], reverse=True)[:top]
    header = "| Person | " + " | ".join(periods) + " | Trend |"
    sep = "|---|" + "---:|" * len(periods) + "---|"
    lines = [header, sep]
    for name in people:
        shares, cells = [], []
        for p in periods:
            c = per.get(name, {}).get(p, 0)
            share = 100 * c / period_totals[p] if period_totals[p] else 0
            shares.append(share)
            cells.append(f"{share:.0f}%")
        lines.append(f"| {name} | " + " | ".join(cells) + f" | {_trend(shares)} |")
    lines.append(
        "| _total msgs_ | " + " | ".join(str(period_totals[p]) for p in periods)
        + " | |"
    )
    return "\n".join(lines)


def _sample(msgs: list[Message], k: int) -> list[Message]:
    if len(msgs) <= k:
        return msgs
    step = len(msgs) / k
    return [msgs[int(i * step)] for i in range(k)]


_TIMELINE_SYSTEM = """You trace how a group text thread has changed over time for \
its member ("Me"). You're given the message-share table by period and a sample of \
messages from each period. Tell the story of the group across the eras.

Ground claims in the samples; quote briefly. Be candid but good-natured — this is \
the user's own family/friends.

Write markdown:
- **The arc** — a short narrative of how the group evolved (who rose, who faded, \
how the energy and tone shifted across the periods).
- **Era by era** — one line per period capturing its character and dominant voices.
- **Risers & faders** — who grew into the chat and who drifted out.
- **Turning points** — moments the vibe shifted (warmer, tenser, quieter) and what \
seemed to drive it."""


def analyze_timeline(
    title: str,
    buckets: dict,
    contacts: dict[str, str],
    focus: str = "balanced",
    budget: int = 400,
) -> str:
    """Return a markdown narrative of the group's evolution. Raises on API errors."""
    from .insights import _client

    periods = list(buckets.keys())
    per_period = max(8, budget // max(1, len(periods)))
    parts = []
    for p in periods:
        sample = _sample(buckets[p], per_period)
        tx = "\n".join(
            f"[{m.date:%Y-%m-%d}] {_speaker(m, contacts)}: {m.text}" for m in sample
        )
        parts.append(f"=== {p} ({len(buckets[p])} messages) ===\n{tx}")

    prompt = (
        f"Group: {title}\n\n"
        f"{_people_context()}\n\n"
        f"Share of messages by period:\n{timeline_share_table(buckets, contacts)}\n\n"
        f"Sampled messages by period:\n\n" + "\n\n".join(parts)
    )
    with _client().messages.stream(
        model=config.MODEL,
        max_tokens=16000,
        system=_TIMELINE_SYSTEM + FOCUS_PROMPTS.get(focus, ""),
        thinking={"type": "adaptive"},
        output_config={"effort": config.EFFORT},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = stream.get_final_message()

    return _extract_text(message)
