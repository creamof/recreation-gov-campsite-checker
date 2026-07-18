"""Find conversations awaiting your reply and rank them by how much they need one.

Ranking uses the Claude API when available and falls back to a purely local
heuristic (by age) if the API key or ``anthropic`` package is missing, or if the
call fails — so scheduled runs never crash.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from . import config
from .chatdb import Chat, ChatDB, Message, thread_title
from .contacts import resolve

_URGENCY_RANK = {"high": 0, "medium": 1, "low": 2}
_URGENCY_EMOJI = {"high": "🔴", "medium": "🟠", "low": "🟡"}


@dataclass
class Followup:
    chat: Chat
    last: Message
    context: list[Message]
    needs_reply: bool = True
    urgency: str = "medium"
    reason: str = ""
    title: str = ""
    sort_key: tuple = field(default=(), repr=False)


def _age_hours(dt: datetime) -> float:
    return max(0.0, (datetime.now() - dt).total_seconds() / 3600)


def fmt_age(dt: datetime) -> str:
    h = _age_hours(dt)
    if h < 1:
        return f"{int(h * 60)}m"
    if h < 24:
        return f"{int(h)}h"
    return f"{int(h / 24)}d"


def collect(
    db: ChatDB,
    since: datetime,
    groups_only: bool = False,
    context: int = 12,
) -> list[Followup]:
    """Gather threads whose most recent message is inbound and unanswered."""
    counts = db.activity_counts(since=since)
    items: list[Followup] = []
    for chat in db.chats(groups_only=groups_only):
        if not counts.get(chat.rowid):
            continue
        last = db.last_message(chat.rowid)
        if last and not last.is_from_me and last.date >= since:
            msgs = db.messages(chat.rowid, limit=context)
            items.append(Followup(chat=chat, last=last, context=msgs))
    # Bound the workload; keep the most recently-active waiting threads.
    items.sort(key=lambda f: f.last.date, reverse=True)
    return items[: config.MAX_FOLLOWUPS]


def rank(
    db: ChatDB,
    items: list[Followup],
    contacts: dict[str, str],
) -> tuple[list[Followup], bool]:
    """Return (ranked followups, used_llm). Falls back to heuristic on failure."""
    for f in items:
        f.title = thread_title(db, f.chat, contacts)

    used_llm = False
    try:
        used_llm = _llm_rank(items, contacts)
    except Exception:
        used_llm = False
    if not used_llm:
        _heuristic_rank(items)

    ranked = [f for f in items if f.needs_reply]
    ranked.sort(key=lambda f: (_URGENCY_RANK.get(f.urgency, 1), -_age_hours(f.last.date)))
    return ranked, used_llm


def _heuristic_rank(items: list[Followup]) -> None:
    """Older unanswered messages are treated as more urgent (more likely lost)."""
    for f in items:
        h = _age_hours(f.last.date)
        f.urgency = "high" if h >= 72 else "medium" if h >= 24 else "low"
        f.reason = f"Waiting {fmt_age(f.last.date)}; you haven't replied."
        f.needs_reply = True


_RANK_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "needs_reply": {"type": "boolean"},
                    "urgency": {"type": "string", "enum": ["high", "medium", "low"]},
                    "reason": {"type": "string"},
                },
                "required": ["id", "needs_reply", "urgency", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

_RANK_SYSTEM = """You triage a person's unanswered text threads. For each thread \
you're given the recent messages; the person is labeled "Me". Decide, for each:
- needs_reply: does the last inbound message actually warrant a reply from Me? \
Casual sign-offs ("lol", "ok", "👍"), pure FYIs, and spam do NOT.
- urgency: high (time-sensitive, a direct question/request, or waiting a long \
time), medium (a normal reply is expected), or low (nice-to-reply).
- reason: one short phrase explaining the call (e.g. "direct question, 3 days old").
Return one entry per thread id. Be decisive; don't over-flag."""


def _llm_rank(items: list[Followup], contacts: dict[str, str]) -> bool:
    """Populate urgency/reason/needs_reply via Claude. Returns True on success."""
    if not items:
        return False
    try:
        import anthropic
    except ImportError:
        return False

    blocks = []
    for f in items:
        lines = []
        for m in f.context:
            who = "Me" if m.is_from_me else resolve(m.handle, contacts)
            lines.append(f"  [{m.date:%Y-%m-%d %H:%M}] {who}: {m.text}")
        blocks.append(
            f"Thread id={f.chat.rowid} ({f.title}), "
            f"last inbound {fmt_age(f.last.date)} ago:\n" + "\n".join(lines)
        )
    prompt = "Triage these threads:\n\n" + "\n\n".join(blocks)

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=config.MODEL,
        max_tokens=4000,
        system=_RANK_SYSTEM,
        thinking={"type": "adaptive"},
        output_config={"effort": config.EFFORT, "format": {
            "type": "json_schema", "schema": _RANK_SCHEMA,
        }},
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        return False

    import json

    text = next((b.text for b in response.content if b.type == "text"), "")
    verdicts = {v["id"]: v for v in json.loads(text).get("items", [])}
    by_id = {f.chat.rowid: f for f in items}
    for cid, v in verdicts.items():
        f = by_id.get(cid)
        if not f:
            continue
        f.needs_reply = bool(v["needs_reply"])
        f.urgency = v.get("urgency", "medium")
        f.reason = v.get("reason", "")
    return True


def render_brief(
    ranked: list[Followup],
    contacts: dict[str, str],
    used_llm: bool,
) -> str:
    """Render the ranked followups as a markdown brief."""
    source = "ranked by Claude" if used_llm else "ranked by recency"
    header = f"# Reply reminders — {datetime.now():%a %b %d, %H:%M}\n"
    if not ranked:
        return header + "\nInbox zero — nobody's waiting on you. 🎉\n"

    lines = [header, f"_{len(ranked)} waiting on a reply ({source})._\n"]
    for i, f in enumerate(ranked, 1):
        who = resolve(f.last.handle, contacts) if f.last.handle else "Someone"
        emoji = _URGENCY_EMOJI.get(f.urgency, "🟠")
        preview = f.last.text.replace("\n", " ")
        preview = preview[:120] + ("…" if len(preview) > 120 else "")
        lines.append(f"{i}. {emoji} **{f.title}** — waiting {fmt_age(f.last.date)}")
        lines.append(f"    > {who}: {preview}")
        if f.reason:
            lines.append(f"    _{f.reason}_")
        lines.append("")
    return "\n".join(lines)


def summary_line(ranked: list[Followup], contacts: dict[str, str]) -> str:
    """One-line summary for a notification banner."""
    if not ranked:
        return "You're all caught up. 🎉"
    top = ranked[0]
    n = len(ranked)
    noun = "person" if n == 1 else "people"
    return f"{n} {noun} waiting — top: {top.title} ({fmt_age(top.last.date)})"
