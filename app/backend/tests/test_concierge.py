"""Tests for the concierge (intent parsing + suggestions) and prep plans."""

from datetime import date

from fastapi.testclient import TestClient

import main
from concierge import parse_intent_local, resolve_target, suggest
from parks import PARKS
from prep import build_trip_plan, find_trip, steps_to_ics

client = TestClient(main.app)
TODAY = date(2026, 7, 18)


# --- intent parsing (local engine) ---------------------------------------


def test_parse_months_and_seasons():
    i = parse_intent_local("thinking about july, maybe early fall too")
    assert 7 in i.months and 9 in i.months and 10 in i.months


def test_parse_interests_party_places():
    i = parse_intent_local("Waterfalls and big granite walls in Yosemite with my kids")
    assert "waterfalls" in i.interests
    assert "granite" in i.interests
    assert i.party == "family"
    assert "Yosemite" in i.places


def test_parse_permit_mentions():
    i = parse_intent_local("I want to finally do Half Dome this summer")
    assert any("half dome" in p.lower() for p in i.places)
    assert set(i.months) >= {6, 7, 8}


def test_empty_text_yields_open_intent():
    i = parse_intent_local("somewhere nice")
    assert i.months == [] and i.summary


# --- target month resolution ----------------------------------------------


def test_resolve_rolls_to_next_year_when_month_too_soon():
    # July 18 asking for "July" → July next year (needs prep lead time).
    assert resolve_target(7, None, TODAY) == date(2027, 7, 15)


def test_resolve_uses_this_year_when_far_enough_out():
    assert resolve_target(10, None, TODAY) == date(2026, 10, 15)


def test_resolve_honors_explicit_year():
    assert resolve_target(7, 2028, TODAY) == date(2028, 7, 15)


# --- suggestions -----------------------------------------------------------


def test_yosemite_waterfalls_query_ranks_yosemite_first():
    out = suggest("waterfalls and granite in Yosemite in July with kids", today=TODAY)
    assert out["engine"] == "local"  # no API key in test env
    assert out["options"], "should always return options"
    assert out["options"][0]["park_slug"] == "yosemite"
    assert any("Yosemite" in w for w in out["options"][0]["why"])


def test_half_dome_query_surfaces_lottery_timing():
    out = suggest("I want to summit Half Dome in July", today=TODAY)
    top = out["options"][0]
    assert top["trip_title"] == "Half Dome Summit Bid"
    labels = " ".join(t["label"] for t in top["timing"])
    assert "Preseason lottery" in labels
    # July 2027 target → preseason closes Mar 31 2027 → upcoming.
    phase = next(t for t in top["timing"] if "Preseason" in t["label"])
    assert phase["status"] == "upcoming"


def test_desert_stars_query_finds_joshua_tree():
    out = suggest("stargazing in the desert with friends", today=TODAY)
    assert any(o["park_slug"] == "joshua-tree" for o in out["options"])


def test_vague_query_still_returns_seasonal_options():
    out = suggest("just want to get outside", month=9, today=TODAY)
    assert out["options"]


def test_out_of_season_warning():
    out = suggest("Joshua Tree boulders in July", today=TODAY)
    jt = next(o for o in out["options"] if o["park_slug"] == "joshua-tree")
    assert any("best months" in w.lower() for w in jt["why"])


# --- trip prep plans -------------------------------------------------------


def test_find_trip():
    assert find_trip("yosemite", "Valley Floor Classic") is not None
    assert find_trip("yosemite", "Nope") is None


def test_trip_plan_merges_campground_and_lottery():
    park, trip = find_trip("zion", "Canyon Classic")
    plan = build_trip_plan(park, trip, month=5, year=2027, today=TODAY)
    titles = " | ".join(s.title for s in plan.steps)
    assert "Watchman" in titles  # campground moment, suffixed with name
    assert "lottery" in titles.lower()  # Angels Landing phases merged in
    # Chronological among dated steps.
    whens = [s.when for s in plan.steps if s.when]
    assert whens == sorted(whens)


def test_trip_plan_dedupes_shared_steps():
    park, trip = find_trip("yosemite", "Valley Floor Classic")
    plan = build_trip_plan(park, trip, month=9, year=2027, today=TODAY)
    starts = [s for s in plan.steps if "Trip starts" in s.title]
    assert len(starts) == 1  # not once per campground target


# --- ICS export ------------------------------------------------------------


def test_ics_has_events_and_alarms():
    park, trip = find_trip("yosemite", "Half Dome Summit Bid")
    plan = build_trip_plan(park, trip, month=8, year=2027, today=TODAY)
    ics = steps_to_ics("Test plan", plan.steps)
    assert ics.startswith("BEGIN:VCALENDAR")
    assert "BEGIN:VEVENT" in ics
    assert "BEGIN:VALARM" in ics
    assert "END:VCALENDAR" in ics.strip().splitlines()[-1]
    # Past steps are excluded.
    assert ics.count("BEGIN:VEVENT") == len([s for s in plan.steps if s.when and not s.is_past])


# --- API endpoints ---------------------------------------------------------


def test_concierge_endpoint():
    r = client.post("/api/concierge", json={"query": "geysers and wildlife with the family in June"})
    assert r.status_code == 200
    body = r.json()
    assert body["options"]
    assert any(o["park_slug"] == "yellowstone" for o in body["options"])


def test_concierge_rejects_empty_and_bad_month():
    assert client.post("/api/concierge", json={"query": "  "}).status_code == 422
    assert client.post("/api/concierge", json={"query": "hi", "month": 13}).status_code == 422


def test_prepare_endpoint():
    r = client.post("/api/prepare", json={"park_slug": "zion", "trip_title": "Canyon Classic", "month": 5, "year": 2027})
    assert r.status_code == 200
    assert r.json()["steps"]
    assert client.post("/api/prepare", json={"park_slug": "zion", "trip_title": "Nope"}).status_code == 404


def test_ics_endpoint():
    plan = client.post("/api/prepare", json={"park_slug": "yosemite", "trip_title": "Half Dome Summit Bid", "month": 8, "year": 2027}).json()
    r = client.post("/api/ics", json={"title": "My plan", "steps": plan["steps"]})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VEVENT" in r.text
