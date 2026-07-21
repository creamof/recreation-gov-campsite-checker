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
import getpass
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from . import __version__, chatdb, config
from .chatdb import Chat, ChatDB
from .contacts import load_contacts, me_label, resolve


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
        who = me_label() if m.is_from_me else resolve(m.handle, contacts)
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


def _parse_date(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        raise SystemExit(f"Bad date {s!r} — use YYYY-MM-DD (e.g. 2025-03-01).")


def _copy_clipboard(text: str) -> bool:
    try:
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=False, timeout=5)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def cmd_draft(args, db: ChatDB) -> int:
    from . import draft

    contacts = load_contacts()
    chat = _find_chat(db, args.chat, contacts)
    if not chat:
        print(f"No chat matched {args.chat!r}. Try `chats` to list them.")
        return 1
    thread = db.messages(chat.rowid, limit=30)
    if not thread:
        print("No messages in that thread.")
        return 1
    voice = db.my_messages(limit=300)
    if len(voice) < 10:
        print("(Heads up: not many of your own messages found, so the voice "
              "match may be rough.)")

    title = _title(chat, db, contacts)
    print(f"# Draft replies — {title}\n")
    for m in thread[-5:]:
        who = me_label() if m.is_from_me else resolve(m.handle, contacts)
        preview = m.text[:80] + ("…" if len(m.text) > 80 else "")
        print(f"  {who}: {preview}")
    print()
    try:
        options = draft.draft_replies(thread, voice, contacts, n=args.num, about=args.about)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    if not options:
        print("No drafts produced — try again or add --about to steer it.")
        return 1
    for i, opt in enumerate(options, 1):
        print(f"[{i}] {opt}\n")
    print("These are drafts — review, then send yourself. "
          "Copy one with: draft ... --copy N")
    if args.copy:
        idx = args.copy - 1
        if 0 <= idx < len(options) and _copy_clipboard(options[idx]):
            print(f"\n✓ Copied option {args.copy} to your clipboard — "
                  f"paste it into Messages.")
    return 0


def _md_to_html(md: str) -> str:
    """Minimal markdown → HTML for embedding AI reads in the report."""
    import html as _html

    out = []
    for line in md.split("\n"):
        s = line.strip()
        if s.startswith("|"):
            continue  # stats tables are rendered separately as charts
        s = _html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        if s.startswith("# "):
            out.append(f"<h1>{s[2:]}</h1>")
        elif s.startswith("## "):
            out.append(f"<h2>{s[3:]}</h2>")
        elif s.startswith("- ") or s.startswith("* "):
            out.append(f"<div>• {s[2:]}</div>")
        elif s.startswith("&gt; "):
            out.append(f"<blockquote>{s[5:]}</blockquote>")
        elif s:
            out.append(f"<p>{s}</p>")
    return "".join(out)


def cmd_report(args, db: ChatDB) -> int:
    from . import analytics, dynamics, htmlreport
    from .contacts import notes as people_notes  # noqa: F401  (loaded for cache)

    contacts = load_contacts()
    chat = _find_chat(db, args.chat, contacts)
    if not chat:
        print(f"No chat matched {args.chat!r}. Try `chats --groups` to list them.")
        return 1
    msgs = db.messages(chat.rowid)
    if len(msgs) < 20:
        print("Not enough messages in that chat for a report.")
        return 1
    title = _title(chat, db, contacts)
    print(f"Building report for {title} ({len(msgs):,} messages)…")

    reactions = db.reaction_counts(chat.rowid)
    stats = dynamics.compute_stats(msgs, reactions, contacts)
    sections: list[str] = []

    # 1. Conversation share over time
    periods, series = analytics.share_over_time(msgs, contacts)
    if len(periods) >= 2:
        sections.append(htmlreport.section(
            "Who carries the conversation",
            "Each person's share of messages per quarter.",
            htmlreport.line_chart(periods, series),
        ))

    # 2. Monthly volume
    sections.append(htmlreport.section(
        "The chat's pulse", "Messages per month across its whole history.",
        htmlreport.bar_chart(analytics.monthly_volume(msgs)),
    ))

    # 3. Rhythms heatmap
    sections.append(htmlreport.section(
        "When the chat is alive", "Message volume by day of week and hour.",
        htmlreport.heatmap(analytics.hourly_heatmap(msgs)),
    ))

    # 4. Reaction economy
    pts = [(s.name, float(s.messages), float(s.reactions_given))
           for s in stats if s.messages >= 5]
    sections.append(htmlreport.section(
        "The reaction economy",
        "Talkers vs. appreciators: messages sent vs. reactions (tapbacks) given.",
        htmlreport.scatter(pts, "messages sent", "reactions given"),
    ))

    # 5. Reply network
    people, edges = analytics.reply_network(msgs, contacts)
    sections.append(htmlreport.section(
        "Who replies to whom",
        "Replies within an hour of another person's message. Bright cells are "
        "strong response pairs; empty rows are broadcasters.",
        htmlreport.matrix(people, edges),
    ))

    # 6. Response times
    rt = analytics.response_times(msgs, contacts)
    rows = [(n, d["replies_after"]) for n, d in rt.items()
            if d["replies_after"] is not None and d["n"] >= 20]
    rows.sort(key=lambda kv: kv[1])
    if rows:
        sections.append(htmlreport.section(
            "Who leaves you hanging",
            "Median time each person takes to reply when the chat is active "
            "(fastest first).",
            htmlreport.hbar_chart(
                [(n, v, htmlreport._fmt_dur(v)) for n, v in rows]),
        ))

    # 7. Warmth trend
    wl, warm, laugh = analytics.warmth_trend(msgs)
    if len(wl) >= 2:
        sections.append(htmlreport.section(
            "Warmth & laughter over time",
            "Share of messages with affection markers (hearts, 'love', thanks) "
            "vs. laughter, per quarter.",
            htmlreport.line_chart(wl, {"Warmth": warm, "Laughter": laugh}),
        ))

    # 8. Signatures
    sigs = analytics.signatures(msgs, contacts)
    cards = []
    for name, s in sigs.items():
        emoji = "".join(e for e, _ in s["emoji"]) or "—"
        words = ", ".join(w for w, _ in s["words"]) or "—"
        phrases = ", ".join(f"“{p}”" for p, _ in s["phrases"])
        cards.append(
            f"<div class='card'><h3>{htmlreport._e(name)}</h3>"
            f"<div class='emoji'>{emoji}</div>"
            f"<div class='terms'><b>Their words:</b> {htmlreport._e(words)}</div>"
            + (f"<div class='terms'><b>Catchphrases:</b> {htmlreport._e(phrases)}</div>" if phrases else "")
            + "</div>"
        )
    sections.append(
        f"<h2>Signatures</h2><p class='note'>Each person's favorite emoji and "
        f"most distinctive vocabulary.</p><div class='sig'>{''.join(cards)}</div>"
    )

    # 9. Peak days (+ AI captions)
    days = analytics.peak_days(msgs)
    captions: dict[str, str] = {}
    use_ai = not args.no_ai
    if use_ai and days:
        try:
            print("  Asking Claude for peak-day captions…")
            captions = analytics.caption_peak_days(days, contacts)
        except RuntimeError as e:
            print(f"  (Skipping AI captions: {e})")
            use_ai = False
    rows_html = "".join(
        f"<div class='peak'><span class='d'>{d['date']}</span>"
        f"<span class='n'>{d['count']} msgs</span>"
        f"<span>{htmlreport._e(captions.get(d['date'], ''))}</span></div>"
        for d in days
    )
    sections.append(htmlreport.section(
        "The big days", "The busiest days in the chat's history.", rows_html))

    # 10. AI reads
    if use_ai:
        try:
            print("  Asking Claude for the dynamics read…")
            read = dynamics.analyze(title, stats, msgs, contacts, focus=args.focus)
            sections.append(htmlreport.section(
                "The read: roles, humor & pot-stirring",
                "Claude's qualitative analysis, grounded in quoted messages.",
                f"<div class='ai'>{_md_to_html(read)}</div>"))
            print("  Asking Claude for the timeline narrative…")
            buckets, _ = dynamics.filter_periods(
                dynamics.bucket_by_period(msgs, by="year"))
            story = dynamics.analyze_timeline(title, buckets, contacts,
                                              focus=args.focus)
            sections.append(htmlreport.section(
                "The story over time",
                "How the group evolved, era by era.",
                f"<div class='ai'>{_md_to_html(story)}</div>"))
        except RuntimeError as e:
            print(f"  (Skipping AI reads: {e})")

    out_dir = Path(args.out).parent if args.out else config.OUTPUT_DIR / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9 _-]", "", title).strip().replace(" ", "-") or "chat"
    out_path = (Path(args.out) if args.out
                else out_dir / f"{safe}-{datetime.now():%Y-%m-%d}.html")
    subtitle = (f"{len(msgs):,} messages · {len(stats)} people · "
                f"{msgs[0].date:%b %Y} – {msgs[-1].date:%b %Y}")
    out_path.write_text(htmlreport.build(f"{title} — Group Report", subtitle,
                                         sections), encoding="utf-8")
    print(f"\n✓ Report written to {out_path}")
    if not args.no_open and sys.platform == "darwin":
        subprocess.run(["open", str(out_path)], check=False)
        print("  (Opened in your browser — use File → Print for a PDF.)")
    return 0


def cmd_setup(args, db: ChatDB) -> int:
    from . import model, settings

    print("iMessage Insights — setup\n")
    print(f"✓ Messages database readable ({db.message_count():,} messages).")

    print("\nHow should the AI run?")
    print("  1) Local & private — an open model on your Mac via Ollama.")
    print("     Nothing leaves your machine. Free. (Recommended)")
    print("  2) Cloud — Anthropic's Claude. Best quality; sends text to the API.")
    try:
        choice = input("Pick 1 or 2 [1]: ").strip() or "1"
    except (EOFError, KeyboardInterrupt):
        return 0

    if choice == "2":
        settings.update(backend="claude")
        if settings.get_api_key() and not args.force:
            print("✓ Claude API key already configured.")
        else:
            print("Paste your key from console.anthropic.com (saved privately, "
                  "0600, to ~/.imessage-insights/config.json).")
            try:
                key = getpass.getpass("API key (hidden): ").strip()
            except (EOFError, KeyboardInterrupt):
                key = ""
            if key:
                settings.set_api_key(key)
                print("✓ Saved.")
            else:
                print("Skipped — run `setup` again to add it.")
    else:
        settings.update(backend="ollama")
        mdl = model.local_model()
        if model.ollama_available():
            print(f"✓ Ollama is running. Using the '{mdl}' model.")
            print(f"  (If you haven't yet:  ollama pull {mdl})")
        else:
            print("\nLocal mode uses Ollama — a free app that runs the model:")
            print("  1. Install it:  https://ollama.com/download   (or: brew install ollama)")
            print("  2. Open the Ollama app (or run:  ollama serve)")
            print(f"  3. Download the model once:  ollama pull {mdl}")
            print("Then you're set — re-run setup to confirm.")

    print(f"\nAll set. AI backend: {model.describe()}.")
    return 0


def _ns(**kw) -> argparse.Namespace:
    return argparse.Namespace(**kw)


def cmd_menu(args, db: ChatDB) -> int:
    return run_menu(db)


def run_menu(db: ChatDB) -> int:
    while True:
        print("""
========  iMessage Insights  ========
  1) Who's waiting on my reply
  2) Draft a reply in my voice
  3) Full visual report on a group chat
  4) Quick text analysis of a group chat
  5) List my chats
  6) Set up automatic reminders
  7) Settings (API key)
  0) Quit
""")
        try:
            choice = input("Pick a number: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if choice in ("0", "q", "quit", "exit"):
            return 0
        elif choice == "1":
            cmd_followups(_ns(days=7, groups=False, notify=False, open=False,
                              quiet=False, out=None), db)
        elif choice == "2":
            name = input("Which chat or person? ").strip()
            if name:
                cmd_draft(_ns(chat=name, num=3, about=None, copy=0), db)
        elif choice == "3":
            name = input("Which group chat? ").strip()
            if name:
                focus = input("Focus — balanced / tension / humor / engagement "
                              "[balanced]: ").strip() or "balanced"
                cmd_report(_ns(chat=name, focus=focus, no_ai=False,
                               no_open=False, out=None), db)
        elif choice == "4":
            name = input("Which group chat? ").strip()
            if name:
                focus = input("Focus — balanced / tension / humor / engagement "
                              "[balanced]: ").strip() or "balanced"
                cmd_dynamics(_ns(chat=name, days=0, since=None, until=None,
                                 focus=focus, no_ai=False, out=None), db)
        elif choice == "5":
            cmd_chats(_ns(groups=False, days=0, limit=30), db)
        elif choice == "6":
            times = input(f"Reminder times [{config.DEFAULT_REMINDER_TIMES}]: "
                          ).strip() or config.DEFAULT_REMINDER_TIMES
            cmd_schedule(_ns(action="install", times=times, db=None), db)
        elif choice == "7":
            cmd_setup(_ns(force=True), db)
        else:
            print("Didn't recognize that — pick a number from the list.")
        try:
            input("\n(Press Enter to return to the menu)")
        except (EOFError, KeyboardInterrupt):
            return 0


def cmd_dynamics(args, db: ChatDB) -> int:
    from . import dynamics

    contacts = load_contacts()
    chat = _find_chat(db, args.chat, contacts)
    if not chat:
        print(f"No chat matched {args.chat!r}. Try `chats --groups` to list them.")
        return 1

    if args.since:
        since = _parse_date(args.since)
    elif args.days:
        since = chatdb.default_window(args.days)
    else:
        since = None
    until = _parse_date(args.until) + timedelta(days=1) if args.until else None

    msgs = db.messages(chat.rowid, since=since)
    if until:
        msgs = [m for m in msgs if m.date < until]
    if not msgs:
        print("No messages in that window.")
        return 1
    reactions = db.reaction_counts(chat.rowid, since=since)
    if until:
        # Reactions are counted at DB level (no until); trim not critical for
        # the qualitative read, but keep the window label honest.
        pass
    stats = dynamics.compute_stats(msgs, reactions, contacts)
    title = _title(chat, db, contacts)

    if args.since or args.until:
        window = f", {msgs[0].date:%Y-%m-%d} → {msgs[-1].date:%Y-%m-%d}"
    elif args.days:
        window = f", last {args.days} days"
    else:
        window = ""
    print(f"# Group dynamics — {title}")
    print(f"_{len(msgs)} messages, {len(stats)} people{window}_\n")
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
    sub = p.add_subparsers(dest="command")

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
    sp.add_argument("--since", metavar="YYYY-MM-DD", help="Analyze from this date.")
    sp.add_argument("--until", metavar="YYYY-MM-DD", help="Analyze up to this date.")
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

    sp = sub.add_parser(
        "report", help="Full visual HTML report for a group chat (charts + AI reads)."
    )
    sp.add_argument("chat", help="Chat id, name, or participant names.")
    sp.add_argument(
        "--focus", choices=["balanced", "tension", "humor", "engagement"],
        default="balanced", help="Lens for the AI sections.",
    )
    sp.add_argument("--no-ai", action="store_true",
                    help="Charts and stats only — no API calls.")
    sp.add_argument("--no-open", action="store_true",
                    help="Don't auto-open the report in the browser.")
    sp.add_argument("--out", help="Output path (default ~/.imessage-insights/reports/).")
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("draft", help="Draft reply options in your voice for a thread.")
    sp.add_argument("chat", help="Chat id, name, or participant names.")
    sp.add_argument("-n", "--num", type=int, default=3, help="How many options.")
    sp.add_argument("--about", help="What you want the reply to convey.")
    sp.add_argument("--copy", type=int, default=0, metavar="N",
                    help="Copy option N to the clipboard.")
    sp.set_defaults(func=cmd_draft)

    sp = sub.add_parser("setup", help="Save your API key and check access.")
    sp.add_argument("--force", action="store_true", help="Re-enter the key even if set.")
    sp.set_defaults(func=cmd_setup)

    sp = sub.add_parser("menu", help="Interactive menu (also the default with no command).")
    sp.set_defaults(func=cmd_menu)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        # No sub-command → open the interactive menu.
        if not getattr(args, "command", None):
            with ChatDB.open(args.db) as db:
                return run_menu(db)
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
