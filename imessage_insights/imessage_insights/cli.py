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
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from . import __version__, chatdb, config
from .chatdb import Chat, ChatDB
from .contacts import load_contacts, resolve


def _title(chat: Chat, db: ChatDB, contacts: dict[str, str]) -> str:
    return chatdb.thread_title(db, chat, contacts)


def _find_chat(db: ChatDB, needle: str, contacts: dict[str, str]) -> Chat | None:
    chats = db.chats()
    if needle.isdigit():
        for c in chats:
            if c.rowid == int(needle):
                return c
    low = needle.lower()
    # Prefer a direct title/identifier substring match.
    for c in chats:
        title = _title(c, db, contacts).lower()
        if low in title or low in c.identifier.lower():
            return c
    # Fall back to token matching: "Moulton-Barry" -> all of {moulton, barry}
    # must appear across the chat's name and participant names.
    tokens = [t for t in re.split(r"[^a-z0-9]+", low) if t]
    if tokens:
        for c in chats:
            hay = (_title(c, db, contacts) + " "
                   + " ".join(resolve(p, contacts) for p in db.participants(c.rowid)))
            hay = hay.lower()
            if all(t in hay for t in tokens):
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


def cmd_dynamics(args, db: ChatDB) -> int:
    from . import dynamics

    contacts = load_contacts()
    chat = _find_chat(db, args.chat, contacts)
    if not chat:
        print(f"No chat matched {args.chat!r}. Try `chats --groups` to list them.")
        return 1

    since = chatdb.default_window(args.days) if args.days else None
    msgs = db.messages(chat.rowid, since=since)
    if not msgs:
        print("No messages in that window.")
        return 1
    reactions = db.reaction_counts(chat.rowid, since=since)
    stats = dynamics.compute_stats(msgs, reactions, contacts)
    title = _title(chat, db, contacts)

    print(f"# Group dynamics — {title}")
    print(f"_{len(msgs)} messages, {len(stats)} people"
          + (f", last {args.days} days" if args.days else "") + "_\n")
    print(dynamics.render_stats_table(stats))

    if args.no_ai:
        return 0
    print("\n---\n")
    try:
        report = dynamics.analyze(title, stats, msgs, contacts, focus=args.focus)
        out = f"# Group dynamics — {title}\n\n{dynamics.render_stats_table(stats)}\n\n{report}\n"
        if args.out:
            Path(args.out).write_text(out, encoding="utf-8")
            print(f"(Wrote full report to {args.out})")
        print(report)
    except RuntimeError as e:
        print(f"_Skipping the AI read: {e}_")
        print("_(The stats above are still complete. Set ANTHROPIC_API_KEY for "
              "the full analysis.)_")
    return 0


def cmd_timeline(args, db: ChatDB) -> int:
    from . import dynamics

    contacts = load_contacts()
    chat = _find_chat(db, args.chat, contacts)
    if not chat:
        print(f"No chat matched {args.chat!r}. Try `chats --groups` to list them.")
        return 1
    msgs = db.messages(chat.rowid)
    if not msgs:
        print("No messages to analyze.")
        return 1
    buckets = dynamics.bucket_by_period(msgs, by=args.by)
    dropped = []
    if not args.all_periods:
        buckets, dropped = dynamics.filter_periods(buckets)
    title = _title(chat, db, contacts)

    print(f"# Dynamics over time — {title}")
    print(f"_{len(msgs)} messages across {len(buckets)} {args.by}s "
          f"({msgs[0].date:%Y-%m} → {msgs[-1].date:%Y-%m})_\n")
    if dropped:
        print(f"_(Skipped {', '.join(dropped)} — too few messages to be "
              f"meaningful; use --all-periods to include them.)_\n")
    print(dynamics.timeline_share_table(buckets, contacts))

    if args.no_ai:
        return 0
    print("\n---\n")
    try:
        report = dynamics.analyze_timeline(title, buckets, contacts, focus=args.focus)
        if args.out:
            out = (f"# Dynamics over time — {title}\n\n"
                   f"{dynamics.timeline_share_table(buckets, contacts)}\n\n{report}\n")
            Path(args.out).write_text(out, encoding="utf-8")
            print(f"(Wrote full report to {args.out})")
        print(report)
    except RuntimeError as e:
        print(f"_Skipping the AI read: {e}_")
        print("_(The table above is still complete. Set ANTHROPIC_API_KEY for "
              "the narrative.)_")
    return 0


def cmd_followups(args, db: ChatDB) -> int:
    from . import followups, notify

    contacts = load_contacts()
    since = chatdb.default_window(args.days)
    items = followups.collect(db, since, groups_only=args.groups)
    ranked, used_llm = followups.rank(db, items, contacts)
    brief = followups.render_brief(ranked, contacts, used_llm)

    out_path = Path(args.out) if args.out else config.BRIEF_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(brief, encoding="utf-8")

    if args.notify and ranked:
        notify.send(
            followups.summary_line(ranked, contacts),
            subtitle=f"Open {out_path}",
        )
    if args.open:
        subprocess.run(["open", str(out_path)], check=False)
    if not args.quiet:
        print(brief)
    return 0


def cmd_schedule(args, db: ChatDB) -> int:
    from . import schedule

    if args.action == "install":
        try:
            path = schedule.install(args.times, db=args.db)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        print(f"Installed reply reminders at {args.times} → {path}")
        if sys.platform != "darwin":
            print("(Not on macOS: wrote the plist but couldn't load it with launchctl.)")
        else:
            print("You'll get a notification at those times. Test now with: "
                  "imessage-insights followups --notify")
    elif args.action == "uninstall":
        print("Removed reply reminders." if schedule.uninstall()
              else "No reminders were installed.")
    else:  # status
        info = schedule.status()
        if not info["installed"]:
            print("Reply reminders: not installed.")
        else:
            state = "loaded" if info["loaded"] else "installed (not loaded)"
            print(f"Reply reminders: {state}")
            print(f"  Times: {', '.join(info['times']) or 'n/a'}")
            print(f"  Plist: {info['path']}")
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

    sp = sub.add_parser(
        "dynamics", help="Analyze a group chat's social dynamics (tone, humor, roles)."
    )
    sp.add_argument("chat", help="Chat id, name, or participant names (e.g. Moulton-Barry).")
    sp.add_argument("--days", type=int, default=0, help="Only analyze the last N days.")
    sp.add_argument(
        "--focus", choices=["balanced", "tension", "humor", "engagement"],
        default="balanced", help="Sharpen the read toward one dimension.",
    )
    sp.add_argument("--no-ai", action="store_true", help="Local stats only, no API call.")
    sp.add_argument("--out", help="Also write the full report to this markdown file.")
    sp.set_defaults(func=cmd_dynamics)

    sp = sub.add_parser(
        "timeline", help="How a group chat's dynamics shifted over time."
    )
    sp.add_argument("chat", help="Chat id, name, or participant names.")
    sp.add_argument(
        "--by", choices=["year", "quarter", "month"], default="year",
        help="Time bucket size (default: year).",
    )
    sp.add_argument(
        "--focus", choices=["balanced", "tension", "humor", "engagement"],
        default="balanced", help="Sharpen the narrative toward one dimension.",
    )
    sp.add_argument("--all-periods", action="store_true",
                    help="Include tiny periods (default drops negligible ones).")
    sp.add_argument("--no-ai", action="store_true", help="Local share table only.")
    sp.add_argument("--out", help="Also write the full report to this markdown file.")
    sp.set_defaults(func=cmd_timeline)

    sp = sub.add_parser(
        "followups", help="Prioritized list of messages awaiting your reply."
    )
    sp.add_argument("--days", type=int, default=7, help="Look back N days.")
    sp.add_argument("--groups", action="store_true", help="Group chats only.")
    sp.add_argument("--notify", action="store_true", help="Send a macOS notification.")
    sp.add_argument("--open", action="store_true", help="Open the brief file.")
    sp.add_argument("--quiet", action="store_true", help="Don't print the brief.")
    sp.add_argument("--out", help="Brief output path (default ~/.imessage-insights/).")
    sp.set_defaults(func=cmd_followups)

    sp = sub.add_parser(
        "schedule", help="Manage the automatic reply-reminder notifications."
    )
    sp.add_argument(
        "action", choices=["install", "uninstall", "status"], nargs="?",
        default="status",
    )
    sp.add_argument(
        "--times", default=config.DEFAULT_REMINDER_TIMES,
        help='Comma-separated HH:MM times, e.g. "9:00,13:00,17:30".',
    )
    sp.set_defaults(func=cmd_schedule, needs_db=False)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        # Some commands (e.g. schedule) don't need to open the database.
        if getattr(args, "needs_db", True) is False:
            return args.func(args, None)
        with ChatDB.open(args.db) as db:
            return args.func(args, db)
    except (FileNotFoundError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
