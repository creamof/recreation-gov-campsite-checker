"""Tests for the curated parks guide data and API."""

from fastapi.testclient import TestClient

import main
from parks import PARKS, get_park

client = TestClient(main.app)


def test_slugs_are_unique():
    slugs = [p.slug for p in PARKS]
    assert len(slugs) == len(set(slugs))


def test_every_park_is_complete():
    for p in PARKS:
        assert p.trips, p.slug
        assert p.activities, p.slug
        assert p.eats, p.slug
        assert p.amenities.showers, f"{p.slug}: campers need shower info"
        assert p.amenities.laundry, p.slug
        assert p.official_url.startswith("https://www.nps.gov/")
        for trip in p.trips:
            assert trip.targets, f"{p.slug}/{trip.title}: trip must link to a plannable facility"
            assert trip.nights >= 1
            for t in trip.targets:
                assert t.entity_type in {"campground", "permit"}


def test_parks_list_endpoint():
    r = client.get("/api/parks")
    assert r.status_code == 200
    parks = r.json()["parks"]
    assert len(parks) == len(PARKS)
    assert all({"slug", "name", "tagline", "trip_count"} <= set(p) for p in parks)


def test_park_detail_endpoint():
    r = client.get("/api/parks/yosemite")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Yosemite"
    assert any(t["title"] == "Half Dome Summit Bid" for t in body["trips"])
    # The known-good facility IDs survive serialization.
    valley = next(t for t in body["trips"] if t["title"] == "Valley Floor Classic")
    assert any(x["rec_gov_id"] == "232447" for x in valley["targets"])


def test_park_detail_404():
    assert client.get("/api/parks/atlantis").status_code == 404


def test_get_park_helper():
    assert get_park("zion")["state"] == "Utah"
    assert get_park("nope") is None
