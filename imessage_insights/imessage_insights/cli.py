"""Command-line interface for imessage_insights.

Read-only, local-first. Sub-commands:

  doctor       Check database access and Full Disk Access.
  chats        List conversations with activity stats.
  show         Print recent messages of a thread.
  stats        Overall messaging statistics.
  unanswered   Threads where someone is waiting on your reply.
  summarize    LLM briefing for one thread (uses the Claude API).
  digest       LLM briefing across the most active group threads.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from . import __version__, chatdb
from .chatdb import Chat, ChatDB
from .contacts import load_contacts, resolve


def _title(chat: Chat, db: ChatDB, contacts: dict[str, str]) -> str:
    if chat.display_name:
        return chat.display_name
    parts = db.participants(chat.rowid)
    if not parts:
        return chat.identifier or f"chat {chat.rowid}"
    names = [resolve(p, contacts) for p in parts]
    if len(names) > 4:
        return ", ".join(names[:4]) + f" +{len(names) - 4}"
    return ", ".join(names)


def _find_chat(db: ChatDB, needle: str, contacts: dict[str, str]) -> Chat | None:
    chats = db.chats()
    if needle.isdigit():
        for c in chats:
            if c.rowid == int(needle):
                return c
    low = needle.lower()
    # Prefer a title/identifier match.
    for c in chats:
        title = _title(c, db, contacts).lower()
        if low in title or low in c.identifier.lower():
            return c
    return None


# -- commands ----------------------------------------------------------------
def cmd_doctor(args, db: ChatDB) -> int:
    count = db.message_count()
    print("✓ Messages database opened successfully.")
    print(f"  Total messages: {count:,}")
    chats = db.chats()
    groups = [c for c in chats if c.is_group]
    print(f"  Conversations: {len(chats)} ({len(groups)} group)")
    if count == 0:
        print(
            "\n! Database opened but is empty. If you expect messages, grant "
            "Full Disk Access to your terminal in System Settings → Privacy "
            "& Security → Full Disk Access, then retry."
        )
    return 0


def cmd_chats(args, db: ChatDB) -> int:
    contacts = load_contacts()
    since = chatdb.default_window(args.days) if args.days else None
    counts = db.activity_counts(since=since)
    chats = db.chats(groups_only=args.groups)
    ranked = sorted(chats, key=lambda c: counts.get(c.rowid, 0), reverse=True)

    header = f"{'ID':>5}  {'MSGS':>6}  {'TYPE':<6}  TITLE"
    print(header)
    print("-" * len(header))
    for c in ranked[: args.limit]:
        n = counts.get(c.rowid, 0)
        if args.days and n == 0:
            continue
        kind = "group" if c.is_group else "1:1"
        print(f"{c.rowid:>5}  {n:>6}  {kind:<6}  {_title(c, db, contacts)}")
    return 0


def cmd_show(args, db: ChatDB) -> int:
    contacts = load_contacts()
    chat = _find_chat(db, args.chat, contacts)
    if not chat:
        print(f"No chat matched {args.chat!r}. Try `chats` to list them.")
        return 1
    msgs = db.messages(chat.rowid, limit=args.limit)
    print(f"# {_title(chat, db, contacts)}  (chat {chat.rowid})\n")
    for m in msgs:
        who = "Me" if m.is_from_me else resolve(m.handle, contacts)
        stamp = m.date.strftime("%Y-%m-%d %H:%M")
        suffix = "  📎" if m.has_attachment else ""
        print(f"[{stamp}] {who}: {m.text}{suffix}")
    return 0


def cmd_stats(args, db: ChatDB) -> int:
    contacts = load_contacts()
    since = chatdb.default_window(args.days) if args.days else None
    counts = db.activity_counts(since=since)
    chats = {c.rowid: c for c in db.chats()}

    total = sum(counts.values())
    window = f"last {args.days} days" if args.days else "all time"
    print(f"# Messaging stats ({window})\n")
    print(f"Total messages: {total:,}")
    print(f"Active conversations: {sum(1 for n in counts.values() if n):,}\n")

    print("Most active conversations:")
    top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
    for chat_id, n in top:
        c = chats.get(chat_id)
        if not c:
            continue
        print(f"  {n:>6}  {_title(c, db, contacts)}")

    # Busiest people across group threads.
    people: Counter[str] = Counter()
    for c in chats.values():
        if not c.is_group:
            continue
        for m in db.messages(c.rowid, since=since):
            if not m.is_from_me and m.handle:
                people[resolve(m.handle, contacts)] += 1
    if people:
        print("\nMost active people in your group threads:")
        for name, n in people.most_common(10):
            print(f"  {n:>6}  {name}")
    return 0


def cmd_unanswered(args, db: ChatDB) -> int:
    contacts = load_contacts()
    since = chatdb.default_window(args.days)
    counts = db.activity_counts(since=since)
    chats = db.chats(groups_only=args.groups)
    pending = []
    for c in chats:
        if not counts.get(c.rowid):
            continue
        last = db.last_message(c.rowid)
        if last and not last.is_from_me and last.date >= since:
            pending.append((last.date, c, last))
    pending.sort(reverse=True)

    if not pending:
        print(f"Nothing awaiting a reply in the last {args.days} days. 🎉")
        return 0
    print(f"# Waiting on you ({len(pending)} threads, last {args.days} days)\n")
    for when, c, last in pending:
        who = resolve(last.handle, contacts) if last.handle else "Someone"
        preview = last.text[:80] + ("…" if len(last.text) > 80 else "")
        print(f"[{when:%Y-%m-%d %H:%M}] {_title(c, db, contacts)}")
        print(f"    {who}: {preview}\n")
    return 0


def cmd_summarize(args, db: ChatDB) -> int:
    from . import insights  # lazy: only needs `anthropic` here

    contacts = load_contacts()
    chat = _find_chat(db, args.chat, contacts)
    if not chat:
        print(f"No chat matched {args.chat!r}. Try `chats` to list them.")
        return 1
    since = chatdb.default_window(args.days) if args.days else None
    msgs = db.messages(chat.rowid, since=since)
    title = _title(chat, db, contacts)
    print(insights.summarize_thread(title, msgs, contacts))
    return 0


def cmd_digest(args, db: ChatDB) -> int:
    from . import insights  # lazy

    contacts = load_contacts()
    since = chatdb.default_window(args.days)
    counts = db.activity_counts(since=since)
    groups = [c for c in db.chats(groups_only=True) if counts.get(c.rowid)]
    groups.sort(key=lambda c: counts.get(c.rowid, 0), reverse=True)
    groups = groups[: args.top]
    if not groups:
        print(f"No active group threads in the last {args.days} days.")
        return 0

    threads = []
    for c in groups:
        msgs = db.messages(c.rowid, since=since)
        if msgs:
            threads.append((_title(c, db, contacts), msgs))
    out = insights.digest(threads, contacts)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"Wrote digest for {len(threads)} threads to {args.out}")
    else:
        print(out)
    return 0


# -- argument parsing --------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="imessage-insights",
        description="Local, read-only explorer and group-thread analyzer for "
        "macOS Messages.",
    )
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--db", type=Path, help="Path to chat.db (default: ~/Library/Messages/chat.db)")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("doctor", help="Check database access.")
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("chats", help="List conversations by activity.")
    sp.add_argument("--groups", action="store_true", help="Group chats only.")
    sp.add_argument("--days", type=int, default=0, help="Only count last N days.")
    sp.add_argument("--limit", type=int, default=30)
    sp.set_defaults(func=cmd_chats)

    sp = sub.add_parser("show", help="Print recent messages of a thread.")
    sp.add_argument("chat", help="Chat id, title, or identifier substring.")
    sp.add_argument("--limit", type=int, default=40)
    sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("stats", help="Overall messaging statistics.")
    sp.add_argument("--days", type=int, default=0, help="Limit to last N days.")
    sp.set_defaults(func=cmd_stats)

    sp = sub.add_parser("unanswered", help="Threads awaiting your reply.")
    sp.add_argument("--days", type=int, default=7)
    sp.add_argument("--groups", action="store_true", help="Group chats only.")
    sp.set_defaults(func=cmd_unanswered)

    sp = sub.add_parser("summarize", help="LLM briefing for one thread.")
    sp.add_argument("chat", help="Chat id, title, or identifier substring.")
    sp.add_argument("--days", type=int, default=0, help="Only include last N days.")
    sp.set_defaults(func=cmd_summarize)

    sp = sub.add_parser("digest", help="LLM briefing across active group threads.")
    sp.add_argument("--days", type=int, default=3)
    sp.add_argument("--top", type=int, default=5, help="Number of threads.")
    sp.add_argument("--out", help="Write markdown to this file instead of stdout.")
    sp.set_defaults(func=cmd_digest)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        with ChatDB.open(args.db) as db:
            return args.func(args, db)
    except (FileNotFoundError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
