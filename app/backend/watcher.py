"""The cancellation watcher: catch sold-out sites the moment they free up.

You add a *watch* (campground + your dates). A background poller re-checks
recreation.gov availability on an interval; when a watched campground goes
from sold out to available — someone cancelled — the watch raises an *alert*,
which the UI surfaces immediately and (optionally) delivers as a Web Push
notification via push.py.

Persistence is a simple JSON file (no database to run), guarded by a lock.

Demo mode: recreation.gov isn't always reachable (offline dev, CI). Set
``TRAILHEAD_DEMO_AVAILABILITY="232447:3/40,232450:0/73"`` to fake per-
campground availability so the whole watcher loop can be exercised end to
end. This is a development hook and is documented as such.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

import recreation

_LOCK = threading.Lock()


def _data_file() -> Path:
    root = Path(os.environ.get("TRAILHEAD_DATA_DIR", Path(__file__).parent / "data"))
    root.mkdir(parents=True, exist_ok=True)
    return root / "watches.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Watch(BaseModel):
    id: str
    campground_id: str
    name: str
    arrival: date
    departure: date
    active: bool = True
    created_at: str = ""
    last_checked: Optional[str] = None
    # unknown | available | unavailable | error | expired
    status: str = "unknown"
    available: Optional[int] = None
    total: Optional[int] = None
    alert: Optional[dict] = None  # {"at": iso, "available": n}
    error: Optional[str] = None


# ------------------------------------------------------------------ storage


def load_watches() -> list[Watch]:
    path = _data_file()
    if not path.exists():
        return []
    with _LOCK:
        raw = json.loads(path.read_text() or "[]")
    return [Watch(**w) for w in raw]


def save_watches(watches: list[Watch]) -> None:
    path = _data_file()
    with _LOCK:
        path.write_text(json.dumps([w.model_dump(mode="json") for w in watches], indent=1))


def add_watch(campground_id: str, name: str, arrival: date, departure: date) -> Watch:
    watch = Watch(
        id=uuid.uuid4().hex[:12],
        campground_id=str(campground_id),
        name=name,
        arrival=arrival,
        departure=departure,
        created_at=_now(),
    )
    watches = load_watches()
    watches.append(watch)
    save_watches(watches)
    return watch


def get_watch(watch_id: str) -> Optional[Watch]:
    return next((w for w in load_watches() if w.id == watch_id), None)


def update_watch(updated: Watch) -> None:
    watches = load_watches()
    for i, w in enumerate(watches):
        if w.id == updated.id:
            watches[i] = updated
            break
    save_watches(watches)


def delete_watch(watch_id: str) -> bool:
    watches = load_watches()
    remaining = [w for w in watches if w.id != watch_id]
    if len(remaining) == len(watches):
        return False
    save_watches(remaining)
    return True


def dismiss_alert(watch_id: str) -> Optional[Watch]:
    watch = get_watch(watch_id)
    if watch is None:
        return None
    watch.alert = None
    update_watch(watch)
    return watch


# ------------------------------------------------------------ availability


def _demo_availability(campground_id: str) -> Optional[tuple[int, int]]:
    """Parse TRAILHEAD_DEMO_AVAILABILITY ("id:avail/total,id:avail/total")."""
    raw = os.environ.get("TRAILHEAD_DEMO_AVAILABILITY", "")
    for part in raw.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        cid, counts = part.split(":", 1)
        if cid.strip() == str(campground_id) and "/" in counts:
            a, t = counts.split("/", 1)
            try:
                return int(a), int(t)
            except ValueError:
                return None
    return None


def fetch_availability(campground_id: str, arrival: date, departure: date) -> tuple[int, int]:
    demo = _demo_availability(campground_id)
    if demo is not None:
        return demo
    return recreation.count_available_sites(campground_id, arrival, departure)


# ------------------------------------------------------------------- check


def check_watch(watch: Watch, today: Optional[date] = None) -> Watch:
    """Run one availability check and update status/alert transitions."""
    today = today or date.today()

    if watch.arrival <= today:
        watch.active = False
        watch.status = "expired"
        watch.alert = None
        update_watch(watch)
        return watch

    was_available = watch.status == "available"
    watch.last_checked = _now()
    try:
        available, total = fetch_availability(watch.campground_id, watch.arrival, watch.departure)
        watch.available, watch.total = available, total
        watch.error = None
        if available > 0:
            watch.status = "available"
            if not was_available:
                # The moment we exist for: sold out (or unknown) → open sites.
                watch.alert = {"at": _now(), "available": available}
                _notify(watch)
        else:
            watch.status = "unavailable"
            watch.alert = None  # the window closed again; don't show stale alerts
    except Exception as exc:  # network, API shape, proxy...
        watch.status = "error"
        watch.error = str(exc)[:300]
    update_watch(watch)
    return watch


def check_all(today: Optional[date] = None) -> list[Watch]:
    results = []
    for watch in load_watches():
        if not watch.active:
            continue
        results.append(check_watch(watch, today=today))
    return results


def _notify(watch: Watch) -> None:
    """Best-effort push notification; never allowed to break a check."""
    try:
        import push

        push.send_alert(
            title=f"🏕 {watch.name}: site available!",
            body=(
                f"{watch.available} site(s) open for "
                f"{watch.arrival.strftime('%b %-d')}–{watch.departure.strftime('%b %-d')}. "
                "Book on recreation.gov before it's gone."
            ),
            url=f"https://www.recreation.gov/camping/campgrounds/{watch.campground_id}",
        )
    except Exception:
        pass
