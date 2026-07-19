# imessage-insights

A local, **read-only** CLI that reads your Mac's Messages database (iMessage +
SMS) to help you explore your history and get AI-generated insights into your
group threads.

**This is v1 and it never sends messages.** It reads your data and, for the
`summarize`/`digest` commands, uses the Claude API to brief you on what's
happening in your group chats. Everything else runs entirely on your Mac.

## How it works

macOS stores every iMessage and SMS in a SQLite database at
`~/Library/Messages/chat.db`. This tool opens that database read-only and:

- lists and ranks your conversations by activity;
- prints threads (decoding the modern `attributedBody` message format);
- computes stats (busiest threads, most active people in your groups);
- flags threads where someone is **waiting on your reply**;
- generates markdown **briefings** of your active group threads via Claude.

SMS/RCS texts from your iPhone appear here only if you have **Text Message
Forwarding** enabled on the phone (Settings → Messages → Text Message
Forwarding).

## Setup (on your Mac)

1. **Grant Full Disk Access.** System Settings → Privacy & Security → Full Disk
   Access → enable it for your terminal app (Terminal or iTerm). This is
   required to read `chat.db`. Quit and reopen the terminal afterward.

2. **Install.**
   ```bash
   cd imessage_insights
   pip install -e .          # installs the `imessage-insights` command + anthropic
   ```
   (Only `summarize`/`digest` need `anthropic`; the rest use the standard
   library, so you can also just run `python3 -m imessage_insights ...`.)

3. **Verify access.**
   ```bash
   imessage-insights doctor
   ```
   If it reports messages, you're set. If it says the database is empty or
   permission-denied, re-check Full Disk Access.

4. **For AI briefings, set your API key.**
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...
   ```

## Usage

```bash
# Explore (all local, no API)
imessage-insights chats --groups --days 30      # most active group chats this month
imessage-insights show "Weekend Trip"           # print a thread by name/id/substring
imessage-insights stats --days 30               # who's most active, busiest threads
imessage-insights unanswered --days 7           # threads awaiting your reply

# AI briefings (uses the Claude API)
imessage-insights summarize "Weekend Trip"      # briefing for one thread
imessage-insights digest --days 3 --top 5       # briefing across your 5 busiest groups
imessage-insights digest --out today.md         # write it to a file

# Never lose a message (reply reminders)
imessage-insights followups --days 7            # prioritized list of who's waiting
imessage-insights schedule install              # get notified automatically

# Read the room (group-chat dynamics)
imessage-insights dynamics "Moulton-Barry"      # tone, humor, roles, who stirs the pot
imessage-insights dynamics "Moulton-Barry" --no-ai   # just the local stats table
```

Each briefing gives a TL;DR, key points, **what's waiting on you**, open
questions, and the thread's vibe.

## Group-chat dynamics — read the room

`dynamics` profiles a group thread: who talks, who's funny, who's checked out,
and who's stirring the pot. It has two layers:

- **Local stats** (always shown, no API): per person — message share, average
  length, how often they ask questions, laughter/emoji rate, how many
  conversations they kick off, and how many reactions they send.
- **Claude's read** (needs an API key): a grounded write-up — the group's vibe,
  each person's role/archetype and style, the funniest member (with a quoted
  bit), who barely engages, and who provokes friction. Every characterization is
  backed by a real quote from the thread.

```bash
imessage-insights dynamics "Moulton-Barry"           # full read
imessage-insights dynamics "Moulton-Barry" --days 90 # just the last 90 days
imessage-insights dynamics "Moulton-Barry" --no-ai   # stats table only
imessage-insights dynamics "Moulton-Barry" --out room.md   # save the report
```

**Sharpen the lens** with `--focus`:

```bash
imessage-insights dynamics "Moulton-Barry" --focus tension     # who stirs the pot, factions, flashpoints
imessage-insights dynamics "Moulton-Barry" --focus humor       # who's actually funny, with the best lines
imessage-insights dynamics "Moulton-Barry" --focus engagement  # who carries it vs. who's drifting
```

**Zoom into a past window** with `--since` / `--until` (great for investigating
when someone went quiet):

```bash
imessage-insights dynamics "Moulton-Barry" --since 2025-03-01 --until 2025-07-31 --focus tension
```

You can name a chat by its group name, by any substring, or by the members
(`"Moulton-Barry"` matches a group containing both Moulton and Barry). Use
`chats --groups` to see the exact names and ids.

### How it's changed over time

`timeline` shows the group's evolution: a per-year table of each person's share
of the conversation (with ↑/↓ trend arrows for who's rising or fading), plus a
Claude narrative of the arc — who grew into the chat, who drifted out, and when
the tone shifted.

```bash
imessage-insights timeline "Moulton-Barry"                 # by year
imessage-insights timeline "Moulton-Barry" --by quarter    # finer buckets
imessage-insights timeline "Moulton-Barry" --focus tension # track friction over time
imessage-insights timeline "Moulton-Barry" --no-ai         # just the share table
```

## Fixing names & pronouns

Names come from your Mac's Contacts, which are sometimes wrong (a nickname like
"Mom", a mis-saved contact, or the wrong person). Create
`~/.imessage-insights/people.json` to override them everywhere — stats, reports,
and the AI reads:

```json
{
  "me": "David",
  "rename": {
    "Karen Osborn": "Ben Osborn",
    "Mom": "Jennifer"
  },
  "notes": {
    "Ben Osborn": "male (he/him)"
  }
}
```

- **`me`** — your own display name (default "Me").
- **`rename`** — map a current name *or* a phone/email to the correct name.
- **`notes`** — per-person hints (pronouns, relationship) passed to the model so
  it stops guessing wrong (e.g. calling Ben "she").

## Reply reminders — for messages that get lost

If you tend to leave people on read by accident, this is the part for you. The
`followups` command finds every thread whose last message is waiting on *you*,
then has Claude rank them — a direct question that's three days old rises to the
top, while "lol ok" gets dropped — and writes a prioritized brief:

```
# Reply reminders — Sat Jul 18, 09:00
_3 waiting on a reply (ranked by Claude)._

1. 🔴 **Mom** — waiting 3d
    > Mom: Are you still coming Sunday?
    _Direct question, unanswered 3 days._
2. 🟠 **Weekend Trip 🏕️** — waiting 5h
    > Alex: So are we meeting at 9am?
    _Open logistics question for the group._
```

If Claude isn't available (no API key), it falls back to a local ranking by how
long each message has been waiting — so it always works.

### Make it automatic

So you don't have to remember to run it, install a scheduled reminder. This sets
up a macOS LaunchAgent that runs `followups --notify` at the times you choose and
pops a native notification ("3 people waiting — top: Mom (3d)"):

```bash
imessage-insights schedule install --times "9:00,13:00,17:30"
imessage-insights schedule status       # check it's loaded
imessage-insights schedule uninstall     # stop the reminders
```

The full brief is written to `~/.imessage-insights/followups.md` each run; the
notification points you there.

> **Note:** the scheduled agent needs your `ANTHROPIC_API_KEY`, so `schedule
> install` copies it (and any `IMSG_*` settings) from your current shell into the
> LaunchAgent plist. The plist is written with `600` permissions (readable only
> by you). Without a key, scheduled runs still work using the local ranking.

### Configuration

Environment variables (all optional):

| Variable | Default | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | — | Required for `summarize`/`digest`. |
| `IMSG_MODEL` | `claude-opus-4-8` | Model for briefings. |
| `IMSG_EFFORT` | `medium` | `low`/`medium`/`high`/`xhigh`/`max` — quality vs. cost. |
| `IMSG_MAX_MESSAGES` | `300` | Max messages per thread sent to the API. |
| `IMSG_REMINDER_TIMES` | `9:00,13:00,17:30` | Default reminder times for `schedule`. |
| `IMSG_OUTPUT_DIR` | `~/.imessage-insights` | Where briefs and logs are written. |
| `IMSG_MAX_FOLLOWUPS` | `25` | Max waiting threads ranked per reminder. |

You can also point at a different database with `--db /path/to/chat.db`.

## Privacy

- The `doctor`, `chats`, `show`, `stats`, and `unanswered` commands are **100%
  local** — nothing leaves your machine.
- The `summarize`, `digest`, and `followups` commands send the relevant thread
  text to the Anthropic API (for briefings / ranking). `followups` degrades to a
  fully-local ranking when no API key is set. Nothing is ever written back to
  Messages and no message is ever sent on your behalf.

## Notes & limitations

- Conversation activity counts (`chats`, `stats`) include tapbacks and group
  events; the `show`/briefing views filter those out and show real messages only.
- Contact names are resolved best-effort from your local AddressBook. Where a
  name isn't found, the raw phone number or email is shown.
- If the database is busy, the tool transparently copies it (and its WAL
  sidecars) to a temp dir and reads the copy.

## Roadmap

This v1 covers **read + explore**, **group insights**, and **reply reminders**.
Natural next steps:

- **Voice-matched draft replies** (draft-only, reviewed by you before sending):
  learn your style from your own past messages and propose responses — a natural
  pairing with reply reminders (surface who's waiting, then draft the reply).
- **Snooze / mark-done** so a reminder stops nagging once you've handled it.
- A "what did I miss" morning brief combining the digest and followups.
- A menu-bar UI over this same core.
