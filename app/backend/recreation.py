"""Thin client for the recreation.gov public/undocumented APIs.

Builds on the endpoints already used by the repo's ``camping.py`` and adds
search + facility metadata. All calls are best-effort: on any network/API
failure they raise ``RecreationUnavailable`` so the API layer can degrade
gracefully (the timeline planner still works from manual input + the rules
engine when recreation.gov is unreachable).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

import requests

BASE_URL = "https://www.recreation.gov"
SEARCH_ENDPOINT = "/api/search"
AVAILABILITY_ENDPOINT = "/api/camps/availability/campground/"
CAMPGROUND_ENDPOINT = "/api/camps/campgrounds/"

# A realistic desktop UA; recreation.gov rejects obvious bot agents.
DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
HEADERS = {"User-Agent": DEFAULT_UA}
TIMEOUT = 15


class RecreationUnavailable(RuntimeError):
    """Raised when recreation.gov cannot be reached or returns an error."""


def _get(path: str, params: Optional[dict] = None) -> Any:
    url = path if path.startswith("http") else f"{BASE_URL}{path}"
    try:
        resp = requests.get(url, params=params or {}, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as exc:  # network, DNS, proxy, timeout
        raise RecreationUnavailable(f"Could not reach recreation.gov: {exc}") from exc
    if resp.status_code != 200:
        raise RecreationUnavailable(
            f"recreation.gov returned {resp.status_code} for {url}"
        )
    try:
        return resp.json()
    except ValueError as exc:
        raise RecreationUnavailable("recreation.gov returned a non-JSON response") from exc


def search(query: str, size: int = 15) -> list[dict]:
    """Search facilities. Returns a normalized list of result dicts.

    Recreation.gov's ``/api/search`` returns ``{"results": [...]}`` where each
    result carries ``entity_id``, ``entity_type`` ("campground"/"permit"/...),
    ``name``, ``parent_name``, ``city``, ``state_code``, lat/lng and
    ``reservable``.
    """
    data = _get(SEARCH_ENDPOINT, {"q": query, "size": size, "exact": "false"})
    results = data.get("results", []) if isinstance(data, dict) else []
    out: list[dict] = []
    for r in results:
        etype = (r.get("entity_type") or "").lower()
        if etype not in {"campground", "permit"}:
            # Keep only the entity types the planner acts on.
            continue
        out.append(
            {
                "id": str(r.get("entity_id") or r.get("id") or ""),
                "name": r.get("name") or "",
                "entity_type": etype,
                "parent_name": r.get("parent_name") or r.get("parent_asset_name"),
                "city": r.get("city"),
                "state": r.get("state_code") or r.get("state"),
                "lat": _to_float(r.get("lat") or r.get("latitude")),
                "lon": _to_float(r.get("lng") or r.get("longitude")),
                "reservable": r.get("reservable"),
            }
        )
    return out


def facility_name(campground_id: str) -> Optional[str]:
    data = _get(f"{CAMPGROUND_ENDPOINT}{campground_id}")
    try:
        return data["campground"]["facility_name"]
    except (KeyError, TypeError):
        return None


def count_available_sites(
    campground_id: str, start: date, end: date
) -> tuple[int, int]:
    """Return (available_sites, total_sites) for the given date range.

    Mirrors the availability logic from the repo's ``camping.py``: a site counts
    as available only if every night of the stay is "Available".
    """
    params = {
        "start_date": _fmt(start),
        "end_date": _fmt(end),
    }
    data = _get(f"{AVAILABILITY_ENDPOINT}{campground_id}", params)
    maximum = data.get("count", 0)
    num_days = (end - start).days
    wanted = {
        _fmt(end - timedelta(days=i)) for i in range(1, num_days + 1)
    }
    available = 0
    for site in data.get("campsites", {}).values():
        avail = bool(site.get("availabilities"))
        for day, status in site.get("availabilities", {}).items():
            if day not in wanted:
                continue
            if status != "Available":
                avail = False
                break
        if avail and site.get("availabilities"):
            available += 1
    return available, maximum


def _fmt(d: date) -> str:
    return datetime(d.year, d.month, d.day).strftime("%Y-%m-%dT00:00:00Z")


def _to_float(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
