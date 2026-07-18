# 🏔️ Trailhead — Campsite & Backcountry Booking Planner

A web app **and** installable phone app (PWA) that helps you plan national park
campground and backcountry-permit trips on [recreation.gov](https://www.recreation.gov).

It grows out of the CLI availability checker in the repo root and adds a real
planning brain on top of the same recreation.gov APIs.

## Capabilities

| # | Capability | Status |
|---|------------|--------|
| 1 | **Trip concierge (AI-driven search)** — say what you're dreaming about in your own words ("waterfalls in Yosemite with the kids in July"); get curated trips that fit, each with a timing brief: which lottery closes when, which booking window opens when, and whether each moment is upcoming / act-now / passed. | ✅ **Built** |
| 2 | **Prep calendars with reminders** — one click merges every booking moment across a trip (campground windows + permit lotteries) into a chronological prep calendar, exportable as an .ics file whose events carry built-in alarms (day-before + 30-min warnings), so deadlines hit your phone. | ✅ **Built** |
| 3 | **Booking timeline planner** — pick any campground or permit + your dates, and get an exact timeline: when the reservation window opens, when a lottery closes, what to do on each date. | ✅ **Built** |
| 4 | **Explore parks field guide** — eight flagship parks rendered as vintage engraved postage stamps (perforated edges, aged paper, one ink per park in the style of the 1934 National Parks issue), curated trips wired into the planner, things to do, places to eat, and camp logistics (showers, laundry, resupply, connectivity). | ✅ **Built** |
| 5 | **Cancellation watcher** — watch a sold-out campground for your dates; a background poller re-checks recreation.gov and raises an alert the moment sites free up, with OS notifications (and optional Web Push that works even when the app is closed). | ✅ **Built** |

### Stamp artwork: making the engravings topographically true

The stamps are engraved line art generated in code — one monument per park,
hatched and ruled like the 1934 National Parks issue. The silhouettes are
currently drawn from memory (the "75% version"). To make each profile
match the real mountain:

1. **Run locally** (needs internet): `python3 app/tools/fetch_references.py`
   — searches Wikimedia Commons for each park's classic view, downloads a
   reference photo per park into `app/reference/`, and writes `CREDITS.txt`
   with the license/author of each file. Swap in your own photos freely;
   only the `slug.jpg` filename matters.
2. Optionally inspect a traced skyline: `pip install pillow`, then
   `python3 app/tools/trace_silhouette.py app/reference/yosemite.jpg`
   prints the monument's outline as an SVG path in stamp coordinates.
3. Hand the folder back ("references are in app/reference/") and the traced
   geometry replaces the from-memory silhouettes in `ParkArt.tsx`.

### Cancellation watcher notes

* Watches persist in `app/backend/data/` (plain JSON, no database). The
  backend's poller re-checks every active watch on an interval
  (`TRAILHEAD_WATCH_INTERVAL` seconds, default 300). The server must be
  running to watch — that's the whole point.
* **Notifications**: with the tab open (or the PWA installed), alerts fire OS
  notifications via the service worker — zero setup. For push that works with
  the app fully closed, generate VAPID keys (`npx web-push generate-vapid-keys`)
  and set `TRAILHEAD_VAPID_PUBLIC_KEY`, `TRAILHEAD_VAPID_PRIVATE_KEY`,
  `TRAILHEAD_VAPID_EMAIL` — the UI picks it up automatically.
* **Demo mode** (development): `TRAILHEAD_DEMO_AVAILABILITY="232447:3/40,232450:0/73"`
  fakes availability per campground so the whole loop can be exercised offline.

### How the concierge parses your words

The concierge is local-first: a deterministic intent engine (months, seasons,
interests, party, place mentions) that works fully offline. If the backend has
an `ANTHROPIC_API_KEY` set, parsing upgrades to Claude (`claude-opus-4-8` via
the Anthropic SDK, structured output into the same `Intent` schema) with
automatic fallback to the local engine on any failure — the feature never
breaks the app. Set `TRAILHEAD_CLAUDE_MODEL` to override the model.

## Why a timeline, not just a search

recreation.gov has **two different booking systems**, and getting a coveted spot
is really about *timing*:

- **Campgrounds** release inventory on a rolling window (commonly ~6 months
  ahead; some parks differ — e.g. **Yosemite** releases 5 months ahead on the
  15th of each month at 7 AM Pacific). High-demand sites sell out in *seconds*
  the instant the window opens.
- **Backcountry permits** (Half Dome, The Wave, Enchantments, Mount Whitney, …)
  use **lotteries**: you apply during a window and results are drawn. Miss the
  application window and there's no "book it later."

The planner encodes these rules and turns them into a dated, actionable plan.

## Architecture

```
app/
├── backend/                 FastAPI service (reuses the repo's recreation.gov API knowledge)
│   ├── main.py              API routes: /concierge, /prepare, /ics, /search, /timeline, /lotteries, /parks, /availability
│   ├── concierge.py         NL intent parsing (local + optional Claude) → scored trip options + timing briefs
│   ├── prep.py              trip-level prep calendars + .ics export with VALARM reminders
│   ├── recreation.py        recreation.gov client (search + metadata + availability)
│   ├── booking_rules.py     rolling-window rules engine (+ Yosemite override)
│   ├── lotteries.py         seed data for well-known backcountry lotteries
│   ├── parks.py             curated field guide: trips, activities, eats, amenities
│   ├── timeline.py          the planning brain — pure, unit-tested, works offline
│   ├── schemas.py           pydantic models
│   └── tests/               39 unit tests (timeline, parks, concierge, prep, ICS)
└── frontend/                React + TypeScript PWA (Vite)
    ├── src/components/ParkArt.tsx    hand-drawn WPA-poster SVG art per park
    ├── src/components/Park*.tsx      explore grid + park guide pages
    ├── src/                          search → dates → timeline UI; lottery browser
    └── public/                       manifest + service worker (installable; push-ready)
```

Guide data (trips/eats/showers/laundry) is curated seed content in `parks.py` —
editorial, offline-friendly, and always linked back to official sources since
hours and policies drift. Facility IDs are only hard-coded where confident;
otherwise the planner opens pre-filled and the user completes the ID from the
recreation.gov URL.

The **timeline engine is a pure function** of its inputs — no network — so it
works even when recreation.gov is unreachable, and the search endpoint degrades
gracefully to manual facility entry.

## Run it locally

**1. Backend** (Python 3.9+):

```bash
cd app/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# API docs at http://localhost:8000/docs
```

**2. Frontend** (Node 18+):

```bash
cd app/frontend
npm install
npm run dev          # http://localhost:5173  (proxies /api -> :8000)
```

Open http://localhost:5173, search a campground or permit (or enter one
manually), pick your dates, and hit **Build my booking timeline**. On mobile you
can **Add to Home Screen** to install it as an app.

**Run the tests:**

```bash
cd app/backend && source .venv/bin/activate && python -m pytest -q
```

## Deploy notes

- Build the frontend with `npm run build` (outputs `app/frontend/dist/`) and
  serve those static files from the same origin as the API so `/api/*` calls
  resolve without CORS. Set `VITE_API_BASE` if you host the API elsewhere.
- Recreation.gov has no official public reservation API; this uses the same
  undocumented endpoints the website itself calls. Be a good citizen: cache
  responses and don't hammer it. Booking rules and lottery dates are best-effort
  and **change yearly** — the UI always links to recreation.gov to confirm.

## Roadmap → Milestone 2 (alerts)

The PWA is already installable and its service worker has `push` /
`notificationclick` handlers. To finish last-minute alerts:

1. Add a `watches` store + `POST /api/watches` (facility + dates + push subscription).
2. Add a scheduled poller that calls `recreation.count_available_sites(...)`
   (already implemented) and sends a Web Push when a watched site opens up.
3. Wire the frontend "Set a cancellation watch" CTA to register a
   `PushSubscription` with VAPID keys.
