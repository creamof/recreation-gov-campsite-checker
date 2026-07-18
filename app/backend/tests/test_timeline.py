"""Unit tests for the pure timeline engine (no network required)."""

from datetime import date

import booking_rules
from schemas import TimelineRequest
from timeline import build_timeline


def _req(**kw):
    base = dict(
        id="232447",
        name="Upper Pines",
        entity_type="campground",
        parent_name="Yosemite National Park",
        arrival=date(2026, 7, 20),
        departure=date(2026, 7, 23),
    )
    base.update(kw)
    return TimelineRequest(**base)


# --- booking_rules --------------------------------------------------------


def test_standard_rolling_opens_six_months_before():
    w = booking_rules.compute_window_open(date(2026, 7, 20), "Basin Montana Campground")
    assert w.rule_name == "standard-rolling-6mo"
    assert w.opens_at.date() == date(2026, 1, 20)


def test_yosemite_rule_uses_15th_five_months_out():
    # Arrival Jul 20 -> block starts Jul 15 -> window opens Feb 15 at 7am PT.
    w = booking_rules.compute_window_open(date(2026, 7, 20), "Upper Pines", "Yosemite National Park")
    assert w.rule_name == "yosemite-5mo-15th"
    assert w.opens_at.date() == date(2026, 2, 15)
    assert w.opens_at.hour == 7


def test_yosemite_before_the_15th_uses_previous_block():
    # Arrival Jul 10 -> block starts Jun 15 -> window opens Jan 15.
    w = booking_rules.compute_window_open(date(2026, 7, 10), "Lower Pines")
    assert w.opens_at.date() == date(2026, 1, 15)


def test_month_clamping_handles_short_months():
    # 6 months before Aug 31 -> Feb 28 (2026 is not a leap year).
    d = booking_rules._months_before(date(2026, 8, 31), 6)
    assert d == date(2026, 2, 28)


# --- campground timeline --------------------------------------------------


def test_campground_timeline_has_critical_booking_step_in_future():
    plan = build_timeline(_req(name="Basin Montana Campground", parent_name=None), today=date(2026, 1, 1))
    assert plan.strategy == "campground"
    criticals = [s for s in plan.steps if s.kind == "critical"]
    assert criticals
    assert any("Booking window opens" in s.title for s in criticals)
    # Trip start + end present.
    assert any(s.kind == "trip" for s in plan.steps)


def test_campground_timeline_when_window_already_open():
    # today is after the window opened -> "bookable now" path.
    plan = build_timeline(_req(name="Basin Montana Campground", parent_name=None), today=date(2026, 6, 1))
    assert any("already bookable" in s.title.lower() or "act now" in s.title.lower() for s in plan.steps)
    assert "bookable now" in plan.headline.lower()


def test_past_steps_are_marked():
    # today is after the trip, so the arrival/departure steps are in the past.
    plan = build_timeline(_req(), today=date(2026, 8, 1))
    assert any(s.is_past for s in plan.steps if s.when)


# --- lottery timeline -----------------------------------------------------


def test_half_dome_is_detected_as_lottery():
    plan = build_timeline(
        _req(id="234652", name="Half Dome Cables", entity_type="permit", arrival=date(2026, 8, 1)),
        today=date(2026, 1, 1),
    )
    assert plan.strategy == "lottery"
    assert any("closes (deadline)" in s.title for s in plan.steps)
    # Deadline reminders exist and are high urgency.
    assert any(s.kind == "reminder" and s.urgency == "high" for s in plan.steps)


def test_prep_step_is_first_in_lottery_plan():
    plan = build_timeline(
        _req(id="234652", name="Half Dome Cables", entity_type="permit", arrival=date(2026, 8, 1)),
        today=date(2026, 1, 1),
    )
    assert plan.steps[0].kind == "prep"


def test_daily_lottery_is_rolling_not_a_deadline():
    plan = build_timeline(
        _req(id="234652", name="Half Dome Cables", entity_type="permit", arrival=date(2026, 8, 1)),
        today=date(2026, 1, 1),
    )
    titles = [s.title for s in plan.steps]
    # A rolling daily lottery must NOT be framed as a single application deadline.
    assert not any("Daily lottery closes (deadline)" in t for t in titles)
    assert any(t.startswith("Daily lottery runs") for t in titles)


def test_lottery_steps_are_chronological():
    plan = build_timeline(
        _req(id="4094840", name="The Wave", parent_name=None, entity_type="permit", arrival=date(2026, 5, 1)),
        today=date(2026, 1, 1),
    )
    whens = [s.when for s in plan.steps if s.when]
    assert whens == sorted(whens)


def test_unknown_permit_gets_generic_plan():
    plan = build_timeline(
        _req(id="999999", name="Some Obscure Wilderness Permit", parent_name=None, entity_type="permit"),
        today=date(2026, 1, 1),
    )
    assert plan.strategy == "unknown"
    assert plan.verify_url and "999999" in plan.verify_url


def test_force_strategy_campground_overrides_lottery_match():
    plan = build_timeline(
        _req(id="234652", name="Half Dome Cables", entity_type="permit", force_strategy="campground"),
        today=date(2026, 1, 1),
    )
    assert plan.strategy == "campground"
