"""The trip concierge: free text in, curated + time-aware options out.

Flow:
  1. Parse the user's free text into a structured ``Intent`` — target months,
     interests, party style, and any specific places mentioned.
  2. Score every curated trip (parks.py) against the intent.
  3. For each matching option, compute a *timing brief* for the target month:
     when the booking window opens, when lotteries close, and whether each of
     those moments is upcoming, urgent, or already passed.

Parsing is local-first (a deterministic keyword engine that works offline).
If an Anthropic API key is configured, the backend upgrades parsing with
Claude for better natural-language understanding — with automatic fallback
to the local parser on any failure, so the feature never breaks the app.
"""

from __future__ import annotations

import os
import re
from datetime import date, timedelta
from typing import Optional

from pydantic import BaseModel, Field

from booking_rules import compute_window_open
from lotteries import find_lottery
from parks import PARKS, Park, Trip

# --------------------------------------------------------------------------- #
# Intent model
# --------------------------------------------------------------------------- #

INTEREST_VOCAB = (
    "waterfalls", "granite", "climbing", "hiking", "backpacking", "wildlife",
    "geysers", "desert", "stargazing", "coast", "lakes", "canyons", "biking",
    "photography", "swimming", "quiet", "family", "food", "summit",
)


class Intent(BaseModel):
    """Structured reading of what the user is dreaming about."""

    months: list[int] = Field(default_factory=list, description="Target months 1-12")
    interests: list[str] = Field(default_factory=list, description=f"Subset of {INTEREST_VOCAB}")
    party: Optional[str] = Field(None, description="family | couple | solo | friends, if stated")
    places: list[str] = Field(default_factory=list, description="Specific parks/trails/permits mentioned")
    summary: str = Field("", description="One-line human-readable echo of the parsed intent")


# --------------------------------------------------------------------------- #
# Local (offline) intent parser
# --------------------------------------------------------------------------- #

_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
_SEASONS = {
    "spring": [4, 5], "summer": [6, 7, 8], "fall": [9, 10], "autumn": [9, 10],
    "winter": [12, 1, 2],
}
_INTEREST_KEYWORDS: dict[str, tuple[str, ...]] = {
    "waterfalls": ("waterfall", "falls", "cascade"),
    "granite": ("granite", "big wall", "dome"),
    "climbing": ("climb", "boulder", "scramble", "cables"),
    "hiking": ("hike", "hiking", "trail", "walk"),
    "backpacking": ("backpack", "backcountry", "wilderness", "overnight", "thru"),
    "wildlife": ("wildlife", "bison", "wolf", "wolves", "moose", "bear", "elk", "animals", "birds"),
    "geysers": ("geyser", "hot spring", "thermal", "prismatic"),
    "desert": ("desert", "cactus", "dunes", "joshua"),
    "stargazing": ("stars", "stargaz", "milky way", "night sky", "dark sky", "astro"),
    "coast": ("coast", "ocean", "sea", "beach", "tidepool", "lobster", "lighthouse"),
    "lakes": ("lake", "paddle", "canoe", "kayak"),
    "canyons": ("canyon", "slot", "narrows", "gorge"),
    "biking": ("bike", "biking", "cycling", "carriage road"),
    "photography": ("photo", "photograph", "sunrise", "sunset"),
    "swimming": ("swim", "river float", "wade"),
    "quiet": ("quiet", "crowd", "solitude", "peaceful", "less busy", "off the beaten"),
    "family": ("family", "kids", "children", "toddler"),
    "food": ("food", "restaurant", "eat", "dining", "brewery"),
    "summit": ("summit", "peak", "cables", "whitney", "half dome", "st helens"),
}
_PARTY_KEYWORDS = {
    "family": ("family", "kids", "children"),
    "couple": ("couple", "partner", "anniversary", "honeymoon"),
    "solo": ("solo", "myself", "alone", "by myself"),
    "friends": ("friends", "group", "crew", "buddies"),
}


def parse_intent_local(text: str) -> Intent:
    low = text.lower()
    months: list[int] = []
    for name, num in _MONTHS.items():
        if re.search(rf"\b{name}\b", low) and num not in months:
            months.append(num)
    for season, season_months in _SEASONS.items():
        if re.search(rf"\b{season}\b", low):
            months.extend(m for m in season_months if m not in months)

    interests = [
        tag for tag, needles in _INTEREST_KEYWORDS.items()
        if any(n in low for n in needles)
    ]

    party = next(
        (p for p, needles in _PARTY_KEYWORDS.items() if any(n in low for n in needles)),
        None,
    )

    # Specific place mentions: park names + trip/lottery keywords.
    places: list[str] = []
    for park in PARKS:
        if park.name.lower() in low or park.slug.replace("-", " ") in low:
            places.append(park.name)
    for phrase in ("half dome", "the wave", "enchantments", "whitney", "angels landing",
                   "narrows", "teton crest", "rim to river", "cadillac"):
        if phrase in low:
            places.append(phrase.title())

    bits = []
    if months:
        month_names = [date(2000, m, 1).strftime("%B") for m in sorted(set(months))]
        bits.append("/".join(month_names))
    if party:
        bits.append(party)
    bits.extend([i for i in interests if i != party][:3])
    if places:
        bits.append("near " + ", ".join(places[:2]))

    return Intent(
        months=sorted(set(months)),
        interests=interests,
        party=party,
        places=places,
        summary=" · ".join(bits) if bits else "open to anything",
    )


# --------------------------------------------------------------------------- #
# Optional Claude-powered parser (graceful fallback to local)
# --------------------------------------------------------------------------- #

def _claude_enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def parse_intent(text: str) -> tuple[Intent, str]:
    """Parse free text; returns (intent, engine) where engine is 'claude'|'local'."""
    if _claude_enabled():
        try:
            return _parse_intent_claude(text), "claude"
        except Exception:
            # Any API/SDK problem falls back to the deterministic parser.
            pass
    return parse_intent_local(text), "local"


def _parse_intent_claude(text: str) -> Intent:
    import anthropic  # optional dependency, imported lazily

    client = anthropic.Anthropic()
    response = client.messages.parse(
        model=os.environ.get("TRAILHEAD_CLAUDE_MODEL", "claude-opus-4-8"),
        max_tokens=1024,
        thinking={"type": "adaptive"},
        output_config={"effort": "low"},
        system=(
            "You extract structured trip intent from a camper's free-form text. "
            f"interests must be a subset of: {', '.join(INTEREST_VOCAB)}. "
            "months are integers 1-12 (expand seasons: summer=6,7,8 etc). "
            "places are specific parks/trails/permits the user named. "
            "summary is a short human-readable echo like 'July · family · waterfalls'."
        ),
        messages=[{"role": "user", "content": text}],
        output_format=Intent,
    )
    intent = response.parsed_output
    # Keep the vocab constraint even if the model drifts.
    intent.interests = [i for i in intent.interests if i in INTEREST_VOCAB]
    intent.months = [m for m in intent.months if 1 <= m <= 12]
    return intent


# --------------------------------------------------------------------------- #
# Park & trip tagging (curated relevance signals)
# --------------------------------------------------------------------------- #

PARK_TAGS: dict[str, set[str]] = {
    "yosemite": {"waterfalls", "granite", "climbing", "hiking", "biking", "photography", "summit"},
    "zion": {"canyons", "hiking", "swimming", "summit", "food", "photography"},
    "grand-canyon": {"canyons", "hiking", "backpacking", "photography", "stargazing"},
    "yellowstone": {"geysers", "wildlife", "family", "photography", "lakes"},
    "glacier": {"lakes", "wildlife", "hiking", "backpacking", "photography", "quiet"},
    "grand-teton": {"lakes", "wildlife", "photography", "backpacking", "food", "family"},
    "joshua-tree": {"desert", "climbing", "stargazing", "quiet", "food"},
    "acadia": {"coast", "biking", "family", "food", "photography"},
}
_STYLE_TAGS: dict[str, set[str]] = {
    "classic": {"hiking", "photography"},
    "family": {"family"},
    "backcountry": {"backpacking", "quiet"},
    "adventure": {"climbing", "summit"},
}


def _trip_months(trip: Trip) -> set[int]:
    """Parse 'May–Jun, Sep' style best_months strings into month numbers."""
    months: set[int] = set()
    txt = trip.best_months.lower()
    abbrs = {k: v for k, v in _MONTHS.items() if len(k) == 3}
    found = [(m.start(), abbrs[m.group(0)]) for m in re.finditer(r"\b(" + "|".join(abbrs) + r")\b", txt)]
    # Expand ranges written with a dash between adjacent mentions.
    for i, (pos, month) in enumerate(found):
        months.add(month)
        if i + 1 < len(found):
            between = txt[pos:found[i + 1][0]]
            if "–" in between or "-" in between:
                m = month
                while m != found[i + 1][1]:
                    months.add(m)
                    m = m % 12 + 1
    return months


# --------------------------------------------------------------------------- #
# Timing briefs
# --------------------------------------------------------------------------- #

def resolve_target(month: Optional[int], year: Optional[int], today: date) -> date:
    """Pick a representative arrival date (the 15th) for the requested month."""
    if not month:
        # No month stated: suggest ~3 months out.
        m = (today.month + 2) % 12 + 1
        y = today.year + (1 if m <= today.month else 0)
        return date(y, m, 15)
    if year:
        return date(year, month, 15)
    candidate = date(today.year, month, 15)
    # Too soon (or past): roll to next year — prep windows need lead time.
    if candidate < today + timedelta(days=30):
        candidate = date(today.year + 1, month, 15)
    return candidate


def timing_brief(trip: Trip, park: Park, arrival: date, today: date) -> list[dict]:
    """Key booking moments for this trip, with status relative to today."""
    briefs: list[dict] = []
    seen: set[str] = set()
    for target in trip.targets:
        if target.entity_type == "permit":
            lot = find_lottery(target.name, park.name)
            if lot is None:
                briefs.append({
                    "label": f"{target.name}: check permit rules",
                    "when": None,
                    "status": "info",
                    "detail": "Permit release rules vary — confirm on recreation.gov.",
                })
                continue
            for phase in lot.for_year(arrival.year)["phases"]:
                key = f"{lot.slug}:{phase['name']}"
                if key in seen:
                    continue
                seen.add(key)
                if phase.get("rolling"):
                    briefs.append({
                        "label": f"{phase['name']} ({lot.name})",
                        "when": None,
                        "status": "info",
                        "detail": phase["notes"],
                    })
                    continue
                closes = date.fromisoformat(phase["closes"])
                opens = date.fromisoformat(phase["opens"])
                if today > closes:
                    status, detail = "passed", "This window has closed for the year — plan for next cycle or watch for leftovers."
                elif opens <= today <= closes:
                    status, detail = "act-now", f"Open NOW — apply before {closes.strftime('%b %-d')}."
                else:
                    status, detail = "upcoming", f"Apply {opens.strftime('%b %-d')} – {closes.strftime('%b %-d')}, {closes.year}."
                briefs.append({
                    "label": f"🎟 {phase['name']} ({lot.name})",
                    "when": phase["closes"],
                    "status": status,
                    "detail": detail,
                })
        else:  # campground
            key = f"cg:{target.name}"
            if key in seen:
                continue
            seen.add(key)
            window = compute_window_open(arrival, target.name, park.name)
            opens_day = window.opens_at.date()
            if opens_day <= today:
                briefs.append({
                    "label": f"🏕 {target.name}: bookable now",
                    "when": today.isoformat(),
                    "status": "act-now",
                    "detail": f"The window for {arrival.strftime('%b %Y')} opened {opens_day.strftime('%b %-d')} — check availability or watch cancellations.",
                })
            else:
                soon = (opens_day - today) <= timedelta(days=14)
                briefs.append({
                    "label": f"🏕 {target.name}: window opens",
                    "when": window.opens_at.isoformat(),
                    "status": "act-now" if soon else "upcoming",
                    "detail": f"Mark {opens_day.strftime('%a, %b %-d, %Y')} at {window.opens_at.strftime('%-I:%M %p %Z')} — {window.rule_name}.",
                })
    return briefs


# --------------------------------------------------------------------------- #
# Matching & scoring
# --------------------------------------------------------------------------- #

def suggest(query: str, month: Optional[int] = None, year: Optional[int] = None,
            today: Optional[date] = None, limit: int = 6) -> dict:
    today = today or date.today()
    intent, engine = parse_intent(query)
    if month:
        intent.months = sorted(set(intent.months) | {month})
    arrival = resolve_target(month or (intent.months[0] if intent.months else None), year, today)

    options = []
    for park in PARKS:
        park_tags = PARK_TAGS.get(park.slug, set())
        park_mentioned = park.name in intent.places or any(
            park.name.lower() in p.lower() or p.lower() in park.name.lower() for p in intent.places
        )
        for trip in park.trips:
            tags = park_tags | _STYLE_TAGS.get(trip.style, set())
            why: list[str] = []
            score = 0.0

            overlap = [i for i in intent.interests if i in tags]
            score += 2.0 * len(overlap)
            for o in overlap[:3]:
                why.append(f"Matches your interest in {o}")

            trip_mentioned = any(
                p.lower() in trip.title.lower()
                or any(p.lower() in t.name.lower() for t in trip.targets)
                for p in intent.places
            )
            if trip_mentioned:
                score += 6.0
                why.append("You mentioned this by name")
            elif park_mentioned:
                score += 4.0
                why.append(f"You mentioned {park.name}")

            tm = _trip_months(trip)
            if intent.months and tm:
                if any(m in tm for m in intent.months):
                    score += 2.5
                    why.append(f"In season for your dates ({trip.best_months})")
                else:
                    score -= 2.0
                    why.append(f"Heads-up: best months are {trip.best_months}")

            if intent.party == "family" and trip.style == "family":
                score += 1.5
                why.append("Family-friendly pick")
            if intent.party == "family" and trip.style in ("backcountry", "adventure"):
                score -= 1.0

            if score <= 0:
                continue
            options.append({
                "park_slug": park.slug,
                "park_name": park.name,
                "state": park.state,
                "trip_title": trip.title,
                "style": trip.style,
                "nights": trip.nights,
                "best_months": trip.best_months,
                "summary": trip.summary,
                "score": round(score, 2),
                "why": why,
                "timing": timing_brief(trip, park, arrival, today),
            })

    options.sort(key=lambda o: -o["score"])
    if not options:
        # Nothing matched — fall back to seasonal picks so the user always
        # gets somewhere to start.
        for park in PARKS:
            for trip in park.trips:
                tm = _trip_months(trip)
                if arrival.month in tm:
                    options.append({
                        "park_slug": park.slug,
                        "park_name": park.name,
                        "state": park.state,
                        "trip_title": trip.title,
                        "style": trip.style,
                        "nights": trip.nights,
                        "best_months": trip.best_months,
                        "summary": trip.summary,
                        "score": 1.0,
                        "why": [f"In season for {arrival.strftime('%B')}"],
                        "timing": timing_brief(trip, park, arrival, today),
                    })
        options.sort(key=lambda o: -o["score"])

    return {
        "intent": intent.model_dump(),
        "engine": engine,
        "target_month": arrival.strftime("%B %Y"),
        "arrival": arrival.isoformat(),
        "options": options[:limit],
    }
