"""Booking-window rules for recreation.gov campgrounds.

Recreation.gov does not expose a single, uniform "when does booking open" field,
and the rules vary by park. This module encodes a small, transparent rules
engine:

* A sensible default (rolling 6-month window) that applies to most campgrounds.
* A handful of well-known park-specific overrides (e.g. Yosemite's 5-month,
  15th-of-the-month release).

Every rule is expressed as a pure function of the *arrival date* and returns the
moment the reservation window opens, plus a human-readable explanation. Nothing
here touches the network, so it is fully unit-testable and works offline.

IMPORTANT: booking policies change. Each rule carries a ``verify_url`` and the
timeline surfaces an explicit "confirm on recreation.gov" note so the user is
never misled into missing a window because a policy shifted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Callable, Optional
from zoneinfo import ZoneInfo


def _months_before(d: date, months: int) -> date:
    """Return the date ``months`` calendar months before ``d``.

    Clamps to the last valid day when the target month is shorter (e.g. three
    months before May 31 -> Feb 28/29).
    """
    month_index = (d.month - 1) - months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = d.day
    # Clamp to end of target month.
    while True:
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1


@dataclass
class WindowOpen:
    """The computed moment a booking window opens for a given arrival date."""

    opens_at: datetime  # timezone-aware
    explanation: str
    rule_name: str
    verify_url: str
    # How competitive/urgent this booking typically is: low | medium | high.
    competitiveness: str = "medium"


@dataclass
class BookingRule:
    """A named booking-window rule.

    ``compute`` maps an arrival date to the datetime the window opens.
    """

    name: str
    description: str
    compute: Callable[[date], WindowOpen]
    # Matching hints: substrings that, if found in a facility/park name,
    # select this rule. Case-insensitive.
    match_names: tuple[str, ...] = field(default_factory=tuple)
    verify_url: str = "https://www.recreation.gov"


# --- Concrete rules -------------------------------------------------------


def _standard_rolling(arrival: date) -> WindowOpen:
    """Most recreation.gov campgrounds: bookable 6 months ahead, rolling daily.

    The site releases each day's inventory 6 months in advance. Release time
    varies by facility; 8:00 AM in the facility's local time is the common
    default, but high-demand sites effectively "sell out" within seconds of
    the release, so we treat 8:00 AM local as the target.
    """
    opens_day = _months_before(arrival, 6)
    opens_at = datetime.combine(opens_day, time(8, 0), tzinfo=ZoneInfo("America/Denver"))
    return WindowOpen(
        opens_at=opens_at,
        explanation=(
            "Standard recreation.gov rolling window: this arrival date becomes "
            "bookable 6 months in advance, around 8:00 AM local time. Release "
            "time can vary by facility."
        ),
        rule_name="standard-rolling-6mo",
        verify_url="https://www.recreation.gov",
        competitiveness="medium",
    )


def _yosemite_rolling(arrival: date) -> WindowOpen:
    """Yosemite campgrounds: 5 months ahead, on the 15th at 7:00 AM Pacific.

    Yosemite releases reservations in one-month blocks. Reservations for a given
    arrival month open on the 15th of the month five months earlier. Example:
    for arrivals July 15 - Aug 14, the window opens March 15 at 7:00 AM PT.
    """
    # The block that contains `arrival` starts on the 15th of arrival's month
    # (or the previous month if arrival is before the 15th).
    if arrival.day >= 15:
        block_month = arrival.replace(day=15)
    else:
        block_month = _months_before(arrival.replace(day=15), 1)
    opens_day = _months_before(block_month, 5)
    opens_at = datetime.combine(opens_day, time(7, 0), tzinfo=ZoneInfo("America/Los_Angeles"))
    return WindowOpen(
        opens_at=opens_at,
        explanation=(
            "Yosemite releases campground reservations 5 months in advance on "
            "the 15th of each month at 7:00 AM Pacific, in one-month blocks. "
            "These sell out within seconds — be logged in and ready early."
        ),
        rule_name="yosemite-5mo-15th",
        verify_url="https://www.nps.gov/yose/planyourvisit/campreservations.htm",
        competitiveness="high",
    )


def _two_weeks_rolling(arrival: date) -> WindowOpen:
    """Some first-come-adjacent / short-window facilities open ~2 weeks ahead."""
    opens_day = arrival - timedelta(days=14)
    opens_at = datetime.combine(opens_day, time(8, 0), tzinfo=ZoneInfo("America/Denver"))
    return WindowOpen(
        opens_at=opens_at,
        explanation=(
            "This facility uses a short booking window (about 2 weeks ahead). "
            "Confirm the exact window on the facility's recreation.gov page."
        ),
        rule_name="short-2wk",
        verify_url="https://www.recreation.gov",
        competitiveness="medium",
    )


RULES: tuple[BookingRule, ...] = (
    BookingRule(
        name="Yosemite (5-month, 15th release)",
        description="Yosemite Valley/park campgrounds: 5 months ahead on the 15th, 7 AM PT.",
        compute=_yosemite_rolling,
        match_names=(
            "yosemite",
            "upper pines",
            "lower pines",
            "north pines",
            "tuolumne meadows",
            "wawona",
            "hodgdon meadow",
            "crane flat",
        ),
        verify_url="https://www.nps.gov/yose/planyourvisit/campreservations.htm",
    ),
    BookingRule(
        name="Standard rolling 6-month window",
        description="Default recreation.gov campground rule.",
        compute=_standard_rolling,
        match_names=(),
        verify_url="https://www.recreation.gov",
    ),
)

DEFAULT_RULE = RULES[-1]


def select_rule(*names: Optional[str]) -> BookingRule:
    """Pick the best-matching booking rule from any of the provided name hints.

    Pass e.g. the campground name and its parent park name; the first rule whose
    ``match_names`` appears in any hint wins. Falls back to the standard rule.
    """
    haystack = " ".join(n.lower() for n in names if n)
    for rule in RULES:
        for needle in rule.match_names:
            if needle in haystack:
                return rule
    return DEFAULT_RULE


def compute_window_open(arrival: date, *names: Optional[str]) -> WindowOpen:
    """Compute when the booking window opens for ``arrival`` at the named place."""
    rule = select_rule(*names)
    return rule.compute(arrival)
