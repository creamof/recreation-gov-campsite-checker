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
```

Each briefing gives a TL;DR, key points, **what's waiting on you**, open
questions, and the thread's vibe.

### Configuration

Environment variables (all optional):

| Variable | Default | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | — | Required for `summarize`/`digest`. |
| `IMSG_MODEL` | `claude-opus-4-8` | Model for briefings. |
| `IMSG_EFFORT` | `medium` | `low`/`medium`/`high`/`xhigh`/`max` — quality vs. cost. |
| `IMSG_MAX_MESSAGES` | `300` | Max messages per thread sent to the API. |

You can also point at a different database with `--db /path/to/chat.db`.

## Privacy

- The `doctor`, `chats`, `show`, `stats`, and `unanswered` commands are **100%
  local** — nothing leaves your machine.
- The `summarize` and `digest` commands send the relevant thread text to the
  Anthropic API to produce the briefing. Nothing is written back to Messages and
  no message is ever sent on your behalf.

## Notes & limitations

- Conversation activity counts (`chats`, `stats`) include tapbacks and group
  events; the `show`/briefing views filter those out and show real messages only.
- Contact names are resolved best-effort from your local AddressBook. Where a
  name isn't found, the raw phone number or email is shown.
- If the database is busy, the tool transparently copies it (and its WAL
  sidecars) to a temp dir and reads the copy.

## Roadmap

This v1 covers **read + explore** and **group insights** — the two priorities
chosen for the first version. Natural next steps:

- **Voice-matched draft replies** (draft-only, reviewed by you before sending):
  learn your style from your own past messages and propose responses.
- Per-thread digests on a schedule, and a "what did I miss" morning brief.
- A menu-bar UI over this same core.
