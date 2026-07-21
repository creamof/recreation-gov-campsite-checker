# imessage-insights — Rearchitecture & Design

## Why this doc

The tool grew to ~15 commands chasing the fun analysis features, and the two
things it was actually built for got buried:

1. **I miss messages** — I need to reliably know who's waiting on a reply.
2. **I need help with my tone** — I want a reply drafted in my own voice.

This redesign puts those two jobs back at the center, makes them **automatic**
(not commands you remember to run), and keeps the analysis — but as something
that *shows up on its own*, simpler, not operated by hand.

## Principles

- **Automatic over manual.** The core loop runs in the background. The default
  action is "look at what it already prepared," not "run a command."
- **One screen.** A single page answers "who needs me, and what do I say?"
- **Draft-only, always.** Nothing is ever sent automatically. Every reply is
  reviewed and sent by the user. (Unchanged from day one.)
- **Local-first.** Message data never leaves the Mac except the specific text
  sent to the Claude API for ranking, drafting, and analysis.
- **Few surfaces, deep automation.** Retire the command sprawl; keep a tiny set.

## The product in one line

> A quiet background assistant that, a few times a day, finds the messages you
> owe a reply to, drafts each one in your voice, and shows them on one screen —
> and once a week tells you what moved in your chats.

---

## Architecture

Three layers. Most of the machinery already exists — this is consolidation, not
a rewrite.

### Layer 1 — The agent loop (automation engine)

A single scheduled job (macOS launchd) that wakes ~3×/day and runs end to end
with no input:

```
triage()      scan unanswered threads, Claude-rank what truly needs a reply
   ↓           (direct questions / 1:1s up; group noise & "lol ok" filtered)
draft()        for each top item, generate a reply in the user's voice
   ↓
render()       write the Reply Cockpit (one HTML page)
   ↓
notify()       macOS banner: "5 replies waiting" → opens the cockpit
```

Weekly, the same scheduler runs `digest()` → a short "this week in your chats"
summary appended to the cockpit (and a banner).

### Layer 2 — The Reply Cockpit (the one screen)

A single local page (`~/.imessage-insights/cockpit.html`) the agent keeps
fresh. It replaces the scattered `.md`/`.html` outputs and most commands.

Each waiting conversation is a card:

```
┌─────────────────────────────────────────────────────────┐
│ Jennifer · 1:1 · waiting 2 days              ● high       │
│ "Are you still coming Sunday?"                            │
│                                                           │
│ Draft (your voice):                                       │
│   "Yeah! What time works — I can bring dessert."          │
│                        [ Copy ]  [ Open in Messages ]     │
│   ↻ another option                                        │
└─────────────────────────────────────────────────────────┘
```

- **[Copy]** puts the draft on the clipboard; **[Open in Messages]** launches
  the conversation (`imessage://` URL). Two clicks: copy → paste → send.
- Sorted by priority. A "caught up" state when the queue is empty.
- A collapsed **This week** strip at the top when a fresh digest exists.

### Layer 3 — Analysis (demoted, not deleted)

- **Weekly digest** — automatic, short, delivered. What changed, who's newly
  quiet, notable moments. No command needed.
- **Deep report** — the existing visual `report` stays, on demand, as a
  "dig into this chat" action. Still there for fun; never required.

---

## Voice / tone engine

Tone help is central, so make it consistent and cheap:

- **Voice profile (cached).** Once (and refreshed occasionally), summarize *how
  the user writes* from their sent messages — length, punctuation, capitalization,
  emoji habits, warmth, signature phrases — into a compact profile stored in
  `~/.imessage-insights/voice.json`. Drafts reference the profile instead of
  re-deriving style every time (more consistent, fewer tokens).
- **Per-thread drafts.** The draft engine combines the cached profile + the
  specific thread context to produce 1–2 options per card.

---

## Command surface: 15 → 4

| Keep | Purpose |
|---|---|
| *(default, no args)* | Open the Reply Cockpit |
| `run` | Force the agent loop now (triage → draft → render → notify) |
| `setup` | One-time: API key, Full Disk Access check, enable the schedule |
| `report <chat>` | On-demand deep visual analysis of one chat |

Everything else (`followups`, `draft`, `dynamics`, `timeline`, `unanswered`,
`show`, `chats`, `stats`, `summarize`, `digest`, `schedule`, `menu`, `doctor`,
`notify`) becomes an **internal module** used by the loop, or is retired.
The interactive menu can stay as a thin front door but is no longer the point.

---

## Proposed module layout

Incremental — reuse existing files, regroup by role. No big-bang rename.

```
imessage_insights/
  core/        db, contacts, model client + key/settings, config   (exists)
  jobs/
    triage.py  scan + Claude-rank unanswered → PriorityItem[]        (from followups)
    voice.py   cached voice profile + per-thread drafts              (from draft)
    digest.py  weekly analysis summary                               (from dynamics)
  render/
    cockpit.py the one screen                                        (new, small)
    report.py  on-demand deep report                                 (from cli/htmlreport)
    charts.py  SVG chart builders                                    (htmlreport)
  agent.py     the loop                                              (new, small)
  cli.py       thin: default→cockpit, run, setup, report             (slimmed)
```

---

## Phased plan

**Phase 1 — The cockpit + the loop (the core reframe).**
Build `render/cockpit.py` and `agent.py`; wire triage (existing ranking) +
voice drafts (existing engine) + notify into one `run`. Default command opens
the cockpit. This alone delivers "don't miss messages + tone help, automatically."

**Phase 2 — Automate it.** Point the launchd schedule at `run` (3×/day). One
`setup` enables it. Reminders become the agent loop.

**Phase 3 — Voice profile.** Add the cached `voice.json` profile so drafts are
consistent and cheaper.

**Phase 4 — Weekly digest.** `jobs/digest.py` + a weekly schedule; surface it in
the cockpit's "This week" strip.

**Phase 5 — Consolidate.** Move files into the `core/jobs/render` layout, retire
dead commands, slim the CLI to the 4 keepers.

Each phase is shippable on its own and reuses code already written and tested.

---

## Decisions (current defaults — reversible)

| Decision | Choice |
|---|---|
| Primary surface | Auto-updating web page (Reply Cockpit) |
| What needs a reply | Smart priority (Claude-ranked; group noise filtered) |
| Analysis cadence | Automatic weekly digest + on-demand deep report |
| Sending | Draft-only, forever. Copy → paste → you send. |
| Model | **Local-first: an open model (Llama) via Ollama by default; Claude optional for top-quality analysis.** Swappable via one setting. |

## Model backend (local-first)

All AI features go through one function, `model.generate()`, so the choice of
where the intelligence runs is a single setting, not scattered code.

- **Local (default): an open Llama model via [Ollama](https://ollama.com).**
  Runs on the Mac; message text never leaves the machine; free. Reached over
  `http://localhost:11434` using only the standard library (no extra install in
  this tool). Requires the one-time Ollama install + `ollama pull llama3.1`.
- **Cloud (optional): Claude.** Better at the nuanced analysis ("who stirs the
  pot") and slightly sharper voice drafts. Sends text to the Anthropic API.

Chosen once in `setup`. Because the always-on triage loop scans *all* messages
every cycle, running it on the local model keeps the bulk of your data on-device
by default. You can point the occasional deep analysis at Claude if you want the
extra quality, without changing anything else.

Model requirements: Ollama runs best on Apple Silicon; `llama3.1` (8B) wants
~16GB RAM. On a lighter Mac, set a smaller model (e.g. `llama3.2:3b`) via
`IMSG_LOCAL_MODEL`.
