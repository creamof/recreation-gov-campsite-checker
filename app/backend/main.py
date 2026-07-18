"""FastAPI backend for the National Parks Campsite & Backcountry Planner.

Milestone 1 — the Timeline Planner:
  * GET  /api/health
  * GET  /api/search?q=...             -> facility search (campgrounds + permits)
  * GET  /api/lotteries?year=YYYY      -> known backcountry lotteries for a year
  * POST /api/timeline                 -> generate a booking timeline for a target
  * GET  /api/availability/{id}        -> live availability snapshot (best-effort)

The timeline engine is pure and always works. Live recreation.gov calls degrade
gracefully: if the site is unreachable the endpoints return a clear, structured
"offline" signal instead of failing, and the planner still works from manual
input.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from datetime import date

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import concierge
import push
import recreation
import watcher
from lotteries import all_lotteries
from parks import all_parks, get_park
from prep import build_trip_plan, find_trip, steps_to_ics
from schemas import SearchResult, TimelinePlan, TimelineRequest, TimelineStep
from timeline import build_timeline


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Run the cancellation-watch poller for the app's lifetime."""
    task = None
    if os.environ.get("TRAILHEAD_DISABLE_POLLER") != "1":
        interval = int(os.environ.get("TRAILHEAD_WATCH_INTERVAL", "300"))

        async def poll_loop() -> None:
            while True:
                try:
                    await asyncio.to_thread(watcher.check_all)
                except Exception:
                    pass  # a bad cycle must never kill the poller
                await asyncio.sleep(interval)

        task = asyncio.create_task(poll_loop())
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="National Parks Campsite & Backcountry Planner",
    version="0.2.0",
    description="Plan when to book campgrounds and apply for backcountry lotteries.",
    lifespan=lifespan,
)

# The PWA is served from a different origin during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchResponse(BaseModel):
    query: str
    online: bool
    results: list[SearchResult]
    note: str | None = None


class AvailabilityResponse(BaseModel):
    id: str
    online: bool
    available: int | None = None
    total: int | None = None
    note: str | None = None


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "campsite-planner", "version": app.version}


@app.get("/api/search", response_model=SearchResponse)
def api_search(q: str, size: int = 15) -> SearchResponse:
    q = q.strip()
    if len(q) < 2:
        return SearchResponse(query=q, online=True, results=[], note="Type at least 2 characters.")
    try:
        raw = recreation.search(q, size=size)
        return SearchResponse(
            query=q,
            online=True,
            results=[SearchResult(**r) for r in raw],
        )
    except recreation.RecreationUnavailable as exc:
        # Degrade gracefully — the UI offers manual entry when offline.
        return SearchResponse(
            query=q,
            online=False,
            results=[],
            note=(
                "recreation.gov is unreachable from the server right now. "
                "You can still generate a timeline by entering a facility name and "
                f"ID manually. ({exc})"
            ),
        )


class ConciergeRequest(BaseModel):
    query: str
    month: int | None = None
    year: int | None = None


@app.post("/api/concierge")
def api_concierge(req: ConciergeRequest) -> dict:
    """Free text in → parsed intent + curated, time-aware trip options."""
    q = req.query.strip()
    if not q:
        raise HTTPException(status_code=422, detail="Tell me what you're dreaming about first.")
    if req.month is not None and not 1 <= req.month <= 12:
        raise HTTPException(status_code=422, detail="Month must be 1-12.")
    return concierge.suggest(q, month=req.month, year=req.year)


class PrepareRequest(BaseModel):
    park_slug: str
    trip_title: str
    month: int | None = None
    year: int | None = None


@app.post("/api/prepare", response_model=TimelinePlan)
def api_prepare(req: PrepareRequest) -> TimelinePlan:
    """Full prep calendar for a curated trip: every window + lottery merged."""
    found = find_trip(req.park_slug, req.trip_title)
    if found is None:
        raise HTTPException(status_code=404, detail="Unknown trip.")
    park, trip = found
    return build_trip_plan(park, trip, req.month, req.year)


class IcsRequest(BaseModel):
    title: str
    steps: list[TimelineStep]


@app.post("/api/ics")
def api_ics(req: IcsRequest) -> Response:
    """Export timeline steps as a calendar file with reminder alarms."""
    ics = steps_to_ics(req.title, req.steps)
    return Response(
        content=ics,
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="trailhead-plan.ics"'},
    )


@app.get("/api/parks")
def api_parks() -> dict:
    """Summaries for the Explore grid."""
    return {"parks": all_parks()}


@app.get("/api/parks/{slug}")
def api_park(slug: str) -> dict:
    """Full curated guide for one park: trips, activities, eats, amenities."""
    park = get_park(slug)
    if park is None:
        raise HTTPException(status_code=404, detail=f"Unknown park: {slug}")
    return park


@app.get("/api/lotteries")
def api_lotteries(year: int | None = None) -> dict:
    year = year or date.today().year
    return {"year": year, "lotteries": all_lotteries(year)}


@app.post("/api/timeline", response_model=TimelinePlan)
def api_timeline(req: TimelineRequest) -> TimelinePlan:
    if req.departure <= req.arrival:
        raise HTTPException(status_code=422, detail="Departure must be after arrival.")
    return build_timeline(req)


class WatchCreate(BaseModel):
    campground_id: str
    name: str
    arrival: date
    departure: date


@app.get("/api/watches")
def api_watches() -> dict:
    """All watches plus whether server-side push is configured."""
    return {
        "watches": [w.model_dump(mode="json") for w in watcher.load_watches()],
        "push_enabled": push.enabled(),
    }


@app.post("/api/watches")
def api_watch_create(req: WatchCreate) -> dict:
    if req.departure <= req.arrival:
        raise HTTPException(status_code=422, detail="Departure must be after arrival.")
    if req.arrival <= date.today():
        raise HTTPException(status_code=422, detail="Arrival must be in the future.")
    if not req.campground_id.strip().isdigit():
        raise HTTPException(status_code=422, detail="Campground ID must be the number from the recreation.gov URL.")
    watch = watcher.add_watch(req.campground_id.strip(), req.name.strip() or f"Campground {req.campground_id}", req.arrival, req.departure)
    # First check right away so the user sees a status immediately.
    watch = watcher.check_watch(watch)
    return watch.model_dump(mode="json")


@app.post("/api/watches/{watch_id}/check")
def api_watch_check(watch_id: str) -> dict:
    watch = watcher.get_watch(watch_id)
    if watch is None:
        raise HTTPException(status_code=404, detail="Unknown watch.")
    return watcher.check_watch(watch).model_dump(mode="json")


@app.post("/api/watches/{watch_id}/dismiss")
def api_watch_dismiss(watch_id: str) -> dict:
    watch = watcher.dismiss_alert(watch_id)
    if watch is None:
        raise HTTPException(status_code=404, detail="Unknown watch.")
    return watch.model_dump(mode="json")


@app.delete("/api/watches/{watch_id}")
def api_watch_delete(watch_id: str) -> dict:
    if not watcher.delete_watch(watch_id):
        raise HTTPException(status_code=404, detail="Unknown watch.")
    return {"deleted": watch_id}


@app.get("/api/push/config")
def api_push_config() -> dict:
    return {"enabled": push.enabled(), "public_key": push.public_key()}


@app.post("/api/push/subscribe")
def api_push_subscribe(subscription: dict) -> dict:
    if not push.enabled():
        raise HTTPException(status_code=400, detail="Push is not configured on this server.")
    if "endpoint" not in subscription:
        raise HTTPException(status_code=422, detail="Not a PushSubscription.")
    count = push.add_subscription(subscription)
    return {"subscribed": True, "subscriptions": count}


@app.get("/api/availability/{campground_id}", response_model=AvailabilityResponse)
def api_availability(campground_id: str, arrival: date, departure: date) -> AvailabilityResponse:
    if departure <= arrival:
        raise HTTPException(status_code=422, detail="Departure must be after arrival.")
    try:
        available, total = recreation.count_available_sites(campground_id, arrival, departure)
        return AvailabilityResponse(
            id=campground_id, online=True, available=available, total=total
        )
    except recreation.RecreationUnavailable as exc:
        return AvailabilityResponse(
            id=campground_id,
            online=False,
            note=f"Live availability unavailable from the server: {exc}",
        )


# --------------------------------------------------------------------------- #
# Static frontend (production single-service deploys)
#
# When the built PWA exists (app/frontend/dist, or FRONTEND_DIST), serve it
# from this same process so one always-on service is the whole deployment.
# Mounted last so every /api route above takes precedence.
# --------------------------------------------------------------------------- #

_dist = Path(os.environ.get("FRONTEND_DIST", Path(__file__).parent.parent / "frontend" / "dist"))
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
