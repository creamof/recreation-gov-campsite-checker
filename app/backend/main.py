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

from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

import concierge
import recreation
from lotteries import all_lotteries
from parks import all_parks, get_park
from prep import build_trip_plan, find_trip, steps_to_ics
from schemas import SearchResult, TimelinePlan, TimelineRequest, TimelineStep
from timeline import build_timeline

app = FastAPI(
    title="National Parks Campsite & Backcountry Planner",
    version="0.1.0",
    description="Plan when to book campgrounds and apply for backcountry lotteries.",
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
