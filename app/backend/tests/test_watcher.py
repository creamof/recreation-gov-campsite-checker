"""Tests for the cancellation watcher: storage, transitions, API."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import main
import watcher

client = TestClient(main.app)

ARRIVAL = date.today() + timedelta(days=60)
DEPART = ARRIVAL + timedelta(days=3)


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    """Each test gets its own data dir and no demo availability."""
    monkeypatch.setenv("TRAILHEAD_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("TRAILHEAD_DEMO_AVAILABILITY", raising=False)


def _mk(**kw):
    return watcher.add_watch(
        kw.get("campground_id", "232447"),
        kw.get("name", "Upper Pines"),
        kw.get("arrival", ARRIVAL),
        kw.get("departure", DEPART),
    )


# --- storage ---------------------------------------------------------------


def test_add_load_delete_roundtrip():
    w = _mk()
    assert watcher.get_watch(w.id).name == "Upper Pines"
    assert len(watcher.load_watches()) == 1
    assert watcher.delete_watch(w.id) is True
    assert watcher.load_watches() == []
    assert watcher.delete_watch("nope") is False


# --- transitions -----------------------------------------------------------


def test_sold_out_to_available_raises_alert(monkeypatch):
    w = _mk()
    monkeypatch.setattr(watcher, "fetch_availability", lambda *a: (0, 40))
    w = watcher.check_watch(w)
    assert w.status == "unavailable" and w.alert is None

    monkeypatch.setattr(watcher, "fetch_availability", lambda *a: (2, 40))
    w = watcher.check_watch(w)
    assert w.status == "available"
    assert w.alert and w.alert["available"] == 2


def test_alert_fires_only_on_transition(monkeypatch):
    w = _mk()
    monkeypatch.setattr(watcher, "fetch_availability", lambda *a: (2, 40))
    w = watcher.check_watch(w)
    first_alert = w.alert["at"]
    # Still available on the next check → alert unchanged (no re-fire).
    w = watcher.check_watch(w)
    assert w.alert["at"] == first_alert


def test_alert_clears_when_availability_drops(monkeypatch):
    w = _mk()
    monkeypatch.setattr(watcher, "fetch_availability", lambda *a: (1, 40))
    w = watcher.check_watch(w)
    assert w.alert
    monkeypatch.setattr(watcher, "fetch_availability", lambda *a: (0, 40))
    w = watcher.check_watch(w)
    assert w.status == "unavailable" and w.alert is None


def test_network_error_recorded_not_raised(monkeypatch):
    w = _mk()

    def boom(*a):
        raise RuntimeError("proxy said no")

    monkeypatch.setattr(watcher, "fetch_availability", boom)
    w = watcher.check_watch(w)
    assert w.status == "error"
    assert "proxy" in w.error


def test_past_watch_expires():
    w = _mk(arrival=date.today() - timedelta(days=1), departure=date.today() + timedelta(days=1))
    w = watcher.check_watch(w)
    assert w.status == "expired" and w.active is False


def test_notify_called_on_alert(monkeypatch):
    calls = []
    monkeypatch.setattr(watcher, "_notify", lambda w: calls.append(w.id))
    monkeypatch.setattr(watcher, "fetch_availability", lambda *a: (3, 40))
    w = watcher.check_watch(_mk())
    assert calls == [w.id]


# --- demo availability hook ------------------------------------------------


def test_demo_availability_env(monkeypatch):
    monkeypatch.setenv("TRAILHEAD_DEMO_AVAILABILITY", "232447:3/40, 232450:0/73")
    assert watcher.fetch_availability("232447", ARRIVAL, DEPART) == (3, 40)
    assert watcher.fetch_availability("232450", ARRIVAL, DEPART) == (0, 73)


def test_demo_ignores_malformed(monkeypatch):
    monkeypatch.setenv("TRAILHEAD_DEMO_AVAILABILITY", "garbage,232447:x/y")
    assert watcher._demo_availability("232447") is None


# --- check_all -------------------------------------------------------------


def test_check_all_skips_inactive(monkeypatch):
    monkeypatch.setattr(watcher, "fetch_availability", lambda *a: (0, 10))
    a = _mk()
    b = _mk(campground_id="232450", name="Lower Pines")
    b.active = False
    watcher.update_watch(b)
    checked = watcher.check_all()
    assert [w.id for w in checked] == [a.id]


# --- API -------------------------------------------------------------------


def test_watch_api_lifecycle(monkeypatch):
    monkeypatch.setenv("TRAILHEAD_DEMO_AVAILABILITY", "232447:0/40")
    r = client.post("/api/watches", json={
        "campground_id": "232447", "name": "Upper Pines",
        "arrival": ARRIVAL.isoformat(), "departure": DEPART.isoformat(),
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "unavailable"

    # Cancellation shows up → manual check raises the alert.
    monkeypatch.setenv("TRAILHEAD_DEMO_AVAILABILITY", "232447:2/40")
    r = client.post(f"/api/watches/{body['id']}/check")
    assert r.json()["alert"]["available"] == 2

    # Listed with push flag.
    listing = client.get("/api/watches").json()
    assert len(listing["watches"]) == 1
    assert listing["push_enabled"] is False

    # Dismiss + delete.
    assert client.post(f"/api/watches/{body['id']}/dismiss").json()["alert"] is None
    assert client.delete(f"/api/watches/{body['id']}").status_code == 200
    assert client.get("/api/watches").json()["watches"] == []


def test_watch_api_validation():
    bad_dates = client.post("/api/watches", json={
        "campground_id": "232447", "name": "x",
        "arrival": DEPART.isoformat(), "departure": ARRIVAL.isoformat(),
    })
    assert bad_dates.status_code == 422
    bad_id = client.post("/api/watches", json={
        "campground_id": "not-a-number", "name": "x",
        "arrival": ARRIVAL.isoformat(), "departure": DEPART.isoformat(),
    })
    assert bad_id.status_code == 422


def test_push_endpoints_when_disabled():
    cfg = client.get("/api/push/config").json()
    assert cfg["enabled"] is False
    assert client.post("/api/push/subscribe", json={"endpoint": "https://x"}).status_code == 400
