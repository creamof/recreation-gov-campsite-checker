"""The timeline engine: turn a target + trip dates into an actionable plan.

This is the planning "brain". It is a pure function of its inputs (plus a
``today`` reference for deterministic tests) and never touches the network, so
it is fully unit-testable and works even when recreation.gov is unreachable.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from booking_rules import compute_window_open
from lotteries import find_lottery
from schemas import SearchResult, TimelinePlan, TimelineRequest, TimelineStep

_PACIFIC = ZoneInfo("America/Los_Angeles")


def _iso(dt: datetime | date) -> str:
    return dt.isoformat()


def _fmt_day(d: date) -> str:
    return d.strftime("%b %-d, %Y")


def _nights(arrival: date, departure: date) -> int:
    return max((departure - arrival).days, 0)


def build_campground_timeline(req: TimelineRequest, today: date) -> TimelinePlan:
    """Rolling-window campground plan: when the window opens and what to do."""
    window = compute_window_open(req.arrival, req.name, req.parent_name)
    opens_at = window.opens_at
    opens_day = opens_at.date()
    nights = _nights(req.arrival, req.departure)

    steps: list[TimelineStep] = []

    # 1. Prep — always do-now.
    steps.append(
        TimelineStep(
            when=None,
            title="Set up before the window opens",
            detail=(
                "Create/verify your recreation.gov account, save your payment method, "
                f"and note the facility (‘{req.name}’). Decide your exact "
                f"{nights}-night dates ({_fmt_day(req.arrival)} → {_fmt_day(req.departure)}) "
                "and 1–2 backup sites in case your first choice is gone."
            ),
            kind="prep",
            urgency="medium",
        )
    )

    window_open = opens_day > today
    if window_open:
        # 2. Reminder the day before.
        remind_day = opens_day - timedelta(days=1)
        if remind_day > today:
            steps.append(
                TimelineStep(
                    when=_iso(remind_day),
                    title="Reminder: booking opens tomorrow",
                    detail=(
                        "Final prep. Log in tonight, confirm your dates, and set an alarm "
                        f"for the release time ({opens_at.strftime('%-I:%M %p %Z')})."
                    ),
                    kind="reminder",
                    urgency="high" if window.competitiveness == "high" else "medium",
                )
            )

        # 3. The critical moment.
        steps.append(
            TimelineStep(
                when=_iso(opens_at),
                title="🎯 Booking window opens — book now",
                detail=(
                    f"{window.explanation} Have the campground page loaded 1–2 minutes early "
                    "and complete checkout the moment it opens. "
                    + (
                        "High-demand sites can sell out in seconds."
                        if window.competitiveness == "high"
                        else "Popular sites go quickly, so don't wait."
                    )
                ),
                kind="critical",
                urgency="high",
                verify_url=window.verify_url,
            )
        )
    else:
        # Window already open — bookable right now (or arrival is very soon).
        steps.append(
            TimelineStep(
                when=_iso(today),
                title="✅ This date is already bookable — act now",
                detail=(
                    f"The 6-month-style window for {_fmt_day(req.arrival)} has already opened "
                    "(it opened around "
                    f"{_fmt_day(opens_day)}). Check availability immediately and book if open. "
                    "If it's sold out, set up a last-minute cancellation watch instead."
                ),
                kind="critical",
                urgency="high",
                verify_url=window.verify_url,
            )
        )
        steps.append(
            TimelineStep(
                when=None,
                title="No luck? Set a cancellation watch",
                detail=(
                    "Sold-out sites free up constantly as people cancel. Add this facility "
                    "and your dates to your watch list to get a last-minute alert."
                ),
                kind="action",
                urgency="medium",
            )
        )

    # 4. Trip start/end.
    steps.append(
        TimelineStep(
            when=_iso(req.arrival),
            title="🏕️ Trip starts (arrival / check-in)",
            detail=f"First night of your {nights}-night stay at {req.name}.",
            kind="trip",
            urgency="low",
        )
    )
    steps.append(
        TimelineStep(
            when=_iso(req.departure),
            title="Trip ends (check-out)",
            detail="Departure day — you are not staying this night.",
            kind="trip",
            urgency="low",
        )
    )

    _mark_past(steps, today)

    headline = (
        f"Book {req.name} on {_fmt_day(opens_day)} at "
        f"{opens_at.strftime('%-I:%M %p %Z')} to lock in {_fmt_day(req.arrival)}."
        if window_open
        else f"{req.name} is bookable now for {_fmt_day(req.arrival)} — grab it or set a watch."
    )

    return TimelinePlan(
        target=_target_from_req(req),
        arrival=req.arrival,
        departure=req.departure,
        strategy="campground",
        headline=headline,
        rule_name=window.rule_name,
        competitiveness=window.competitiveness,
        steps=steps,
        verify_url=window.verify_url,
    )


def build_lottery_timeline(req: TimelineRequest, today: date) -> TimelinePlan:
    """Lottery/permit plan: application windows, deadlines and result dates."""
    lot = find_lottery(req.name, req.parent_name)
    assert lot is not None  # caller guarantees this
    year = req.arrival.year
    data = lot.for_year(year)

    steps: list[TimelineStep] = [
        TimelineStep(
            when=None,
            title=f"Understand the {lot.name} permit system",
            detail=(
                f"{lot.summary} This is a lottery/permit, not a first-come campground — "
                "you apply during a window and either win a draw or grab a fixed release. "
                "Confirm this year's exact dates on recreation.gov before relying on them."
            ),
            kind="prep",
            urgency="medium",
            verify_url=lot.verify_url,
        )
    ]

    for phase in data["phases"]:
        opens = date.fromisoformat(phase["opens"])
        closes = date.fromisoformat(phase["closes"])

        # Rolling phases (daily lotteries) have no single deadline: one info step.
        if phase.get("rolling"):
            steps.append(
                TimelineStep(
                    when=phase["opens"],
                    title=f"{phase['name']} runs {opens.strftime('%b %-d')} – {closes.strftime('%b %-d')}",
                    detail=phase["notes"],
                    kind="info",
                    urgency="medium",
                    verify_url=lot.verify_url,
                )
            )
            continue

        # Application opens.
        steps.append(
            TimelineStep(
                when=phase["opens"],
                title=f"{phase['name']} opens",
                detail=phase["notes"],
                kind="action",
                urgency="medium",
                verify_url=lot.verify_url,
            )
        )
        # Deadline reminder (2 days before close) + the close date itself.
        remind = closes - timedelta(days=2)
        if remind > opens:
            steps.append(
                TimelineStep(
                    when=_iso(remind),
                    title=f"⏰ Apply now — {phase['name']} closes in 2 days",
                    detail="Don't miss the deadline. Submit your application before the window closes.",
                    kind="reminder",
                    urgency="high",
                )
            )
        steps.append(
            TimelineStep(
                when=phase["closes"],
                title=f"🎯 {phase['name']} closes (deadline)",
                detail="Last day to apply for this phase.",
                kind="critical",
                urgency="high",
                verify_url=lot.verify_url,
            )
        )
        if phase["results"]:
            steps.append(
                TimelineStep(
                    when=phase["results"],
                    title=f"Results announced — {phase['name']}",
                    detail=(
                        "Check your recreation.gov account/email. If you won, confirm and pay "
                        "any fees by the stated deadline or you'll forfeit the permit."
                    ),
                    kind="info",
                    urgency="medium",
                    verify_url=lot.verify_url,
                )
            )

    steps.append(
        TimelineStep(
            when=_iso(req.arrival),
            title="🥾 Trip / permit start date",
            detail=f"Target start for your {lot.name} trip.",
            kind="trip",
            urgency="low",
        )
    )

    # Sort chronologically; do-now (when=None) prep steps sort to the top.
    steps.sort(key=lambda s: s.when or "")
    _mark_past(steps, today)

    return TimelinePlan(
        target=_target_from_req(req),
        arrival=req.arrival,
        departure=req.departure,
        strategy="lottery",
        headline=(
            f"{lot.name} is a lottery. Your key deadline is the application close date — "
            "apply during the window; don't wait for a release."
        ),
        rule_name="lottery",
        competitiveness="high",
        steps=steps,
        verify_url=lot.verify_url,
    )


def build_timeline(req: TimelineRequest, today: date | None = None) -> TimelinePlan:
    """Dispatch to the right strategy based on the target and any hints."""
    today = today or date.today()

    lot = find_lottery(req.name, req.parent_name)
    is_permit = req.entity_type.lower() in {"permit", "permits"} or lot is not None

    if req.force_strategy == "lottery" or (req.force_strategy != "campground" and lot is not None):
        if lot is not None:
            return build_lottery_timeline(req, today)
    if req.force_strategy == "campground":
        return build_campground_timeline(req, today)
    if is_permit and lot is None:
        # A permit we don't have seed data for: give a generic permit plan.
        return _generic_permit_timeline(req, today)
    return build_campground_timeline(req, today)


def _generic_permit_timeline(req: TimelineRequest, today: date) -> TimelinePlan:
    steps = [
        TimelineStep(
            when=None,
            title="Check this permit's release/lottery rules",
            detail=(
                f"‘{req.name}’ is a permit. Recreation.gov permits use either a lottery "
                "(apply in a window, results drawn) or a fixed/rolling release. Open its "
                "recreation.gov page to find the exact application window and set reminders "
                "for the open and close dates."
            ),
            kind="prep",
            urgency="high",
            verify_url=f"https://www.recreation.gov/permits/{req.id}",
        ),
        TimelineStep(
            when=_iso(req.arrival),
            title="🥾 Target trip start",
            detail=f"Your intended start date at {req.name}.",
            kind="trip",
            urgency="low",
        ),
    ]
    _mark_past(steps, today)
    return TimelinePlan(
        target=_target_from_req(req),
        arrival=req.arrival,
        departure=req.departure,
        strategy="unknown",
        headline=f"{req.name} is a permit — confirm its lottery/release rules on recreation.gov.",
        rule_name=None,
        competitiveness="high",
        steps=steps,
        verify_url=f"https://www.recreation.gov/permits/{req.id}",
    )


def _target_from_req(req: TimelineRequest) -> SearchResult:
    return SearchResult(
        id=req.id,
        name=req.name,
        entity_type=req.entity_type,
        parent_name=req.parent_name,
    )


def _mark_past(steps: list[TimelineStep], today: date) -> None:
    for s in steps:
        if not s.when:
            continue
        try:
            d = date.fromisoformat(s.when[:10])
        except ValueError:
            continue
        s.is_past = d < today
