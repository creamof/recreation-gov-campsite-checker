"""Trip-level preparation plans and calendar (.ics) export.

Where ``timeline.py`` plans a single facility, this module answers the bigger
question — "I want to do this *trip* in July: what do I prepare, and when?" —
by merging every booking moment across the trip's targets (campground windows
AND permit lotteries) into one chronological prep calendar.

The .ics export turns that calendar into real notifications: each key step
becomes a calendar event with built-in alarms, so lottery deadlines and
window-open moments hit the user's phone without any server infrastructure.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from concierge import resolve_target
from parks import PARKS, Park, Trip
from schemas import SearchResult, TimelinePlan, TimelineRequest, TimelineStep
from timeline import build_timeline


def find_trip(park_slug: str, trip_title: str) -> Optional[tuple[Park, Trip]]:
    for park in PARKS:
        if park.slug != park_slug:
            continue
        for trip in park.trips:
            if trip.title == trip_title:
                return park, trip
    return None


def build_trip_plan(park: Park, trip: Trip, month: Optional[int], year: Optional[int],
                    today: Optional[date] = None) -> TimelinePlan:
    """Merge per-target timelines into one deduplicated prep calendar."""
    today = today or date.today()
    arrival = resolve_target(month, year, today)
    departure = arrival + timedelta(days=trip.nights)

    merged: list[TimelineStep] = []
    seen_titles: set[str] = set()
    strategies: set[str] = set()

    for target in trip.targets:
        req = TimelineRequest(
            id=target.rec_gov_id or "0",
            name=target.name,
            entity_type=target.entity_type,
            parent_name=f"{park.name} National Park",
            arrival=arrival,
            departure=departure,
        )
        plan = build_timeline(req, today=today)
        strategies.add(plan.strategy)
        for step in plan.steps:
            # Dedupe cross-target noise (shared lottery phases, repeated trip
            # start/end markers) while keeping per-campground booking moments.
            key = step.title if step.kind in ("trip", "prep") else f"{target.name}:{step.title}"
            if step.kind in ("critical", "reminder", "action") and target.entity_type == "campground":
                step.title = f"{step.title} — {target.name}"
                key = step.title
            if key in seen_titles:
                continue
            seen_titles.add(key)
            merged.append(step)

    merged.sort(key=lambda s: (s.when or "", s.title))
    # Do-now prep items float to the top.
    merged.sort(key=lambda s: s.when is not None and s.kind != "prep")

    strategy = "lottery" if strategies == {"lottery"} else (
        "campground" if strategies == {"campground"} else "campground"
    )
    n_perm = sum(1 for t in trip.targets if t.entity_type == "permit")
    n_cg = len(trip.targets) - n_perm
    pieces = []
    if n_cg:
        pieces.append(f"{n_cg} campground option{'s' if n_cg > 1 else ''}")
    if n_perm:
        pieces.append(f"{n_perm} permit/lottery")
    headline = (
        f"{trip.title} in {arrival.strftime('%B %Y')}: your prep calendar across "
        f"{' + '.join(pieces)}. Add the reminders so nothing slips."
    )

    return TimelinePlan(
        target=SearchResult(
            id=park.slug, name=f"{park.name} — {trip.title}", entity_type="trip",
            parent_name=f"{park.name} National Park",
        ),
        arrival=arrival,
        departure=departure,
        strategy=strategy,  # dominant flavor; steps carry the detail
        headline=headline,
        rule_name="trip-plan",
        competitiveness="high" if n_perm else "medium",
        steps=merged,
        verify_url=park.official_url,
    )


# --------------------------------------------------------------------------- #
# ICS calendar export with alarms
# --------------------------------------------------------------------------- #

def _esc(text: str) -> str:
    return (
        text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """RFC 5545 line folding at 75 octets."""
    out = []
    while len(line.encode()) > 73:
        cut = 73
        while len(line[:cut].encode()) > 73:
            cut -= 1
        out.append(line[:cut])
        line = " " + line[cut:]
    out.append(line)
    return "\r\n".join(out)


def steps_to_ics(title: str, steps: list[TimelineStep], stamp: Optional[datetime] = None) -> str:
    """Render timeline steps as a VCALENDAR with VALARM reminders.

    * Date-only steps become all-day events with a 9 AM day-of alarm.
    * Timed steps (window-open moments) get alarms 1 day and 30 minutes before.
    """
    stamp = stamp or datetime.utcnow()
    stamp_str = stamp.strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Trailhead//Campsite Planner//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        _fold(f"X-WR-CALNAME:{_esc(title)}"),
    ]
    n = 0
    for step in steps:
        if not step.when or step.is_past:
            continue
        n += 1
        uid = f"trailhead-{stamp_str}-{n}@trailhead.local"
        summary = _esc(step.title)
        desc = _esc(step.detail + (f"\n{step.verify_url}" if step.verify_url else ""))
        lines += ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp_str}"]
        if "T" in step.when:
            dt = datetime.fromisoformat(step.when)
            lines.append("DTSTART:" + dt.astimezone().strftime("%Y%m%dT%H%M%S"))
            alarms = [("-P1D", "Booking moment tomorrow"), ("-PT30M", "Booking opens in 30 minutes — get ready")]
        else:
            d = date.fromisoformat(step.when)
            lines.append("DTSTART;VALUE=DATE:" + d.strftime("%Y%m%d"))
            lines.append("DTEND;VALUE=DATE:" + (d + timedelta(days=1)).strftime("%Y%m%d"))
            alarms = [("-PT0M", step.title)]
            if step.urgency == "high":
                alarms.append(("-P1D", "Deadline tomorrow"))
        lines.append(_fold(f"SUMMARY:{summary}"))
        lines.append(_fold(f"DESCRIPTION:{desc}"))
        for trigger, alarm_text in alarms:
            lines += [
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                _fold(f"DESCRIPTION:{_esc(alarm_text)}"),
                f"TRIGGER:{trigger}",
                "END:VALARM",
            ]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
