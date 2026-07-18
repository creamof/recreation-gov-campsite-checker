"""Seed data for well-known recreation.gov backcountry permits & lotteries.

Backcountry / high-demand permits do not use the rolling campground window.
They use *lottery* or *fixed-release* application windows: you apply during a
window, and either results are drawn (lottery) or permits are released at a
fixed date/time on a rolling basis (fixed-release).

These dates shift every year and each entry carries a ``verify_url``. The
timeline always tells the user to confirm the current year's dates. Where the
window follows a stable annual rule we compute it for any target year; where it
does not, we store the most recent known window and flag it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class LotteryPhase:
    """One phase of a permit system (e.g. preseason lottery, daily lottery)."""

    name: str
    kind: str  # "lottery" | "fixed-release"
    # Application window, as (month, day) tuples applied to the target year.
    opens: tuple[int, int]
    closes: tuple[int, int]
    # When results are announced, as (month, day) — None for fixed-release.
    results: Optional[tuple[int, int]] = None
    notes: str = ""
    # A "rolling" phase (e.g. a daily lottery) is active across a season rather
    # than having a single application deadline. It gets one informational step,
    # not open/deadline/results milestones.
    rolling: bool = False

    def window_for_year(self, year: int) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "opens": date(year, *self.opens).isoformat(),
            "closes": date(year, *self.closes).isoformat(),
            "results": date(year, *self.results).isoformat() if self.results else None,
            "notes": self.notes,
            "rolling": self.rolling,
        }


@dataclass
class PermitLottery:
    """A named permit/lottery with one or more phases."""

    slug: str
    name: str
    park: str
    verify_url: str
    match_names: tuple[str, ...]
    phases: tuple[LotteryPhase, ...]
    summary: str = ""

    def for_year(self, year: int) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "park": self.park,
            "verify_url": self.verify_url,
            "summary": self.summary,
            "phases": [p.window_for_year(year) for p in self.phases],
        }


# NOTE: Dates below follow each permit's typical annual rule. They are seeds for
# the timeline and are always presented with a "confirm current-year dates"
# note. Verify against the linked recreation.gov page before relying on them.
LOTTERIES: tuple[PermitLottery, ...] = (
    PermitLottery(
        slug="half-dome",
        name="Half Dome Cables",
        park="Yosemite National Park",
        verify_url="https://www.recreation.gov/permits/234652",
        match_names=("half dome",),
        summary="Preseason lottery in spring, plus a daily lottery ~2 days ahead.",
        phases=(
            LotteryPhase(
                name="Preseason lottery application",
                kind="lottery",
                opens=(3, 1),
                closes=(3, 31),
                results=(4, 14),
                notes="Apply anytime in March; results mid-April. Covers most permits for the season.",
            ),
            LotteryPhase(
                name="Daily lottery",
                kind="lottery",
                opens=(5, 15),
                closes=(10, 15),
                results=None,
                rolling=True,
                notes="Rolling daily lottery during the season: apply ~2 days before your hike; results that evening.",
            ),
        ),
    ),
    PermitLottery(
        slug="the-wave",
        name="Coyote Buttes North (The Wave)",
        park="Vermilion Cliffs / BLM",
        verify_url="https://www.recreation.gov/permits/4094840",
        match_names=("the wave", "coyote buttes north", "coyote buttes"),
        summary="Advance monthly lottery (~4 months ahead) plus a daily geographic lottery.",
        phases=(
            LotteryPhase(
                name="Advance lottery application",
                kind="lottery",
                opens=(1, 1),
                closes=(1, 31),
                results=(2, 1),
                notes="Runs every month for permits ~4 months out. Example shown is January's window; apply the whole month.",
            ),
            LotteryPhase(
                name="Daily lottery",
                kind="lottery",
                opens=(1, 1),
                closes=(12, 31),
                results=None,
                rolling=True,
                notes="Geographic daily lottery: apply 2 days before, from within the designated area. Results same evening.",
            ),
        ),
    ),
    PermitLottery(
        slug="enchantments",
        name="Enchantments / Alpine Lakes",
        park="Okanogan-Wenatchee National Forest",
        verify_url="https://www.recreation.gov/permits/233273",
        match_names=("enchantment", "alpine lakes", "colchuck", "snow lakes"),
        summary="Single spring lottery for the core summer permit season.",
        phases=(
            LotteryPhase(
                name="Lottery application",
                kind="lottery",
                opens=(2, 15),
                closes=(3, 5),
                results=(3, 25),
                notes="One application window in late winter; results late March. Unclaimed permits released later on recreation.gov.",
            ),
        ),
    ),
    PermitLottery(
        slug="mount-whitney",
        name="Mount Whitney",
        park="Inyo National Forest",
        verify_url="https://www.recreation.gov/permits/233260",
        match_names=("whitney",),
        summary="Spring lottery for the main season; leftover permits released after.",
        phases=(
            LotteryPhase(
                name="Lottery application",
                kind="lottery",
                opens=(2, 1),
                closes=(3, 15),
                results=(3, 24),
                notes="Apply Feb 1 – Mar 15; results late March. Leftover/cancelled permits appear on recreation.gov afterward.",
            ),
        ),
    ),
    PermitLottery(
        slug="angels-landing",
        name="Angels Landing",
        park="Zion National Park",
        verify_url="https://www.nps.gov/zion/planyourvisit/angels-landing-hiking-permits.htm",
        match_names=("angels landing",),
        summary="Quarterly seasonal lotteries plus a day-before lottery for the chained ridge.",
        phases=(
            LotteryPhase(
                name="Seasonal lottery (example: summer window)",
                kind="lottery",
                opens=(4, 1),
                closes=(4, 20),
                results=(4, 25),
                notes="Four seasonal windows a year (Jan/Apr/Jul/Oct pattern) each covering the following season — apply in the window before your trip season.",
            ),
            LotteryPhase(
                name="Day-before lottery",
                kind="lottery",
                opens=(1, 1),
                closes=(12, 31),
                results=None,
                rolling=True,
                notes="Enter between 12:01 AM and 3 PM MT the day before your hike; results that evening.",
            ),
        ),
    ),
    PermitLottery(
        slug="mount-st-helens",
        name="Mount St. Helens (Monitor Ridge)",
        park="Mount St. Helens National Volcanic Monument",
        verify_url="https://www.recreation.gov/permits/4675317",
        match_names=("st. helens", "st helens", "monitor ridge"),
        summary="Spring lottery for peak-season summit permits; fixed release for shoulder season.",
        phases=(
            LotteryPhase(
                name="Peak-season lottery",
                kind="lottery",
                opens=(2, 1),
                closes=(2, 28),
                results=(3, 12),
                notes="Lottery covers the high-demand May 15 – Oct 31 window.",
            ),
        ),
    ),
)


def find_lottery(*names: Optional[str]) -> Optional[PermitLottery]:
    """Return the lottery matching any of the provided name hints, if known."""
    haystack = " ".join(n.lower() for n in names if n)
    for lot in LOTTERIES:
        for needle in lot.match_names:
            if needle in haystack:
                return lot
    return None


def all_lotteries(year: int) -> list[dict]:
    return [lot.for_year(year) for lot in LOTTERIES]
