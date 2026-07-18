# 🏔️ Trailhead — Campsite & Backcountry Booking Planner

A web app **and** installable phone app (PWA) that helps you plan national park
campground and backcountry-permit trips on [recreation.gov](https://www.recreation.gov).

It grows out of the CLI availability checker in the repo root and adds a real
planning brain on top of the same recreation.gov APIs.

## Capabilities

| # | Capability | Status |
|---|------------|--------|
| 1 | **Booking timeline planner** — pick a campground or permit + your dates, and get an exact timeline: when the reservation window opens, when a lottery closes, and what to do on each date so you don't miss it. | ✅ **Milestone 1 — built** |
| 2 | **Explore parks field guide** — eight flagship parks, each with hand-drawn poster artwork, curated trip suggestions wired into the planner, things to do beyond the campsite, places to eat, and camp logistics (showers, laundry, resupply, connectivity). | ✅ **Milestone 1.5 — built** |
| 3 | **Last-minute availability alerts** — watch specific campgrounds/dates and get a web-push notification the moment a cancellation frees a site. | 🔜 Milestone 2 — foundation in place (installable PWA + service-worker push handlers already wired) |

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
│   ├── main.py              API routes: /search, /timeline, /lotteries, /parks, /availability
│   ├── recreation.py        recreation.gov client (search + metadata + availability)
│   ├── booking_rules.py     rolling-window rules engine (+ Yosemite override)
│   ├── lotteries.py         seed data for well-known backcountry lotteries
│   ├── parks.py             curated field guide: trips, activities, eats, amenities
│   ├── timeline.py          the planning brain — pure, unit-tested, works offline
│   ├── schemas.py           pydantic models
│   └── tests/               19 unit tests (timeline engine + parks guide)
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
