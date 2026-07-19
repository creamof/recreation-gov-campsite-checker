"""Local analytics for group-chat reports.

Everything here is computed on-device from the message list — no API calls,
with one exception: caption_peak_days() (labeled clearly) asks Claude for a
one-line caption per busy day.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from statistics import median

from . import config
from .chatdb import Message
from .dynamics import _EMOJI, _LAUGH, _speaker

# Messages closer together than this are treated as replies to each other.
REPLY_GAP_S = 3600
# Ignore gaps longer than this when measuring response times (overnight etc.).
RESPONSE_CAP_S = 12 * 3600

_WARMTH = re.compile(
    r"love|miss you|thank|proud|congrat|beautiful|adorable|wonderful|sweet|"
    r"blessed|[❤♥]|🥰|😘|🤗|💕|💖|💗",
    re.IGNORECASE,
)

_STOP = set(
    """the and for that this with you your have has was were are is it's its not
    but they them then than out get got just like know going good great time
    when what where who how why yes yeah okay our their his her him she he we
    all can will would could should there here about back come came went see
    saw say said one two too very much many more some had did does don't didn't
    can't i'm it'll won't isn't aren't wasn't from over into been being now
    today tomorrow think thought make made need want look looks let lets still
    also well really them these those only even after before because""".split()
)


# -- rhythms -----------------------------------------------------------------
def hourly_heatmap(messages: list[Message]) -> list[list[int]]:
    """7x24 grid of message counts: rows Mon..Sun, cols hour 0..23."""
    grid = [[0] * 24 for _ in range(7)]
    for m in messages:
        grid[m.date.weekday()][m.date.hour] += 1
    return grid


def monthly_volume(messages: list[Message]) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for m in messages:
        counts[f"{m.date:%Y-%m}"] += 1
    return sorted(counts.items())


def share_over_time(
    messages: list[Message], contacts: dict, top: int = 6
) -> tuple[list[str], dict[str, list[float]]]:
    """Quarterly share-of-messages per person for the `top` most active."""
    from .dynamics import bucket_by_period, filter_periods

    buckets, _ = filter_periods(bucket_by_period(messages, by="quarter"))
    periods = list(buckets.keys())
    totals: Counter[str] = Counter()
    per: dict[str, Counter] = defaultdict(Counter)
    for p, msgs in buckets.items():
        for m in msgs:
            name = _speaker(m, contacts)
            per[name][p] += 1
            totals[name] += 1
    people = [n for n, _ in totals.most_common(top)]
    series = {
        name: [
            100 * per[name][p] / len(buckets[p]) if buckets[p] else 0.0
            for p in periods
        ]
        for name in people
    }
    return periods, series


# -- reply network & response times ------------------------------------------
def reply_network(
    messages: list[Message], contacts: dict
) -> tuple[list[str], dict[tuple[str, str], int]]:
    """Directed reply counts: (replier, replied_to) -> n, within REPLY_GAP_S."""
    edges: Counter[tuple[str, str]] = Counter()
    volume: Counter[str] = Counter()
    for prev, cur in zip(messages, messages[1:]):
        a, b = _speaker(prev, contacts), _speaker(cur, contacts)
        volume[b] += 1
        if a != b and (cur.date - prev.date).total_seconds() <= REPLY_GAP_S:
            edges[(b, a)] += 1
    people = [n for n, _ in volume.most_common(10)]
    keep = {k: v for k, v in edges.items() if k[0] in people and k[1] in people}
    return people, keep


def response_times(
    messages: list[Message], contacts: dict
) -> dict[str, dict[str, float]]:
    """Per person: median seconds they take to reply ('replies_after') and the
    median seconds until someone answers them ('answered_in')."""
    replies: dict[str, list[float]] = defaultdict(list)
    answered: dict[str, list[float]] = defaultdict(list)
    for prev, cur in zip(messages, messages[1:]):
        a, b = _speaker(prev, contacts), _speaker(cur, contacts)
        gap = (cur.date - prev.date).total_seconds()
        if a != b and 0 <= gap <= RESPONSE_CAP_S:
            replies[b].append(gap)
            answered[a].append(gap)
    out = {}
    for name in set(replies) | set(answered):
        out[name] = {
            "replies_after": median(replies[name]) if replies.get(name) else None,
            "answered_in": median(answered[name]) if answered.get(name) else None,
            "n": len(replies.get(name, [])),
        }
    return out


# -- signatures ---------------------------------------------------------------
def signatures(
    messages: list[Message], contacts: dict, top_people: int = 10
) -> dict[str, dict]:
    """Per person: favorite emoji and distinctive words/phrases."""
    texts: dict[str, list[str]] = defaultdict(list)
    for m in messages:
        texts[_speaker(m, contacts)].append(m.text)
    people = sorted(texts, key=lambda n: len(texts[n]), reverse=True)[:top_people]

    def words_of(t: str) -> list[str]:
        return [w for w in re.findall(r"[a-z']{3,}", t.lower()) if w not in _STOP]

    global_words: Counter[str] = Counter()
    global_bigrams: Counter[str] = Counter()
    per_words: dict[str, Counter] = {}
    per_bigrams: dict[str, Counter] = {}
    per_emoji: dict[str, Counter] = {}
    for name in people:
        wc, bc, ec = Counter(), Counter(), Counter()
        for t in texts[name]:
            ws = words_of(t)
            wc.update(ws)
            bc.update(" ".join(p) for p in zip(ws, ws[1:]))
            ec.update(_EMOJI.findall(t))
        per_words[name], per_bigrams[name], per_emoji[name] = wc, bc, ec
        global_words.update(wc)
        global_bigrams.update(bc)

    g_total = max(1, sum(global_words.values()))
    out: dict[str, dict] = {}
    for name in people:
        p_total = max(1, sum(per_words[name].values()))

        def distinct(counter: Counter, glob: Counter, min_n: int) -> list[tuple[str, int]]:
            scored = []
            for term, n in counter.items():
                if n < min_n:
                    continue
                score = (n / p_total) / (glob[term] / g_total)
                scored.append((score, term, n))
            scored.sort(reverse=True)
            return [(term, n) for _, term, n in scored[:5]]

        out[name] = {
            "messages": len(texts[name]),
            "emoji": per_emoji[name].most_common(5),
            "words": distinct(per_words[name], global_words, 4),
            "phrases": distinct(per_bigrams[name], global_bigrams, 3),
        }
    return out


# -- peak days ----------------------------------------------------------------
def peak_days(messages: list[Message], top: int = 10) -> list[dict]:
    by_day: dict[str, list[Message]] = defaultdict(list)
    for m in messages:
        by_day[f"{m.date:%Y-%m-%d}"].append(m)
    days = sorted(by_day.items(), key=lambda kv: len(kv[1]), reverse=True)[:top]
    days.sort(key=lambda kv: kv[0])
    return [{"date": d, "count": len(msgs), "messages": msgs} for d, msgs in days]


_CAPTION_SCHEMA = {
    "type": "object",
    "properties": {
        "captions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"date": {"type": "string"}, "caption": {"type": "string"}},
                "required": ["date", "caption"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["captions"],
    "additionalProperties": False,
}


def caption_peak_days(days: list[dict], contacts: dict) -> dict[str, str]:
    """One-line 'what happened that day' captions via the Claude API."""
    from .insights import _client

    blocks = []
    for d in days:
        msgs = d["messages"]
        step = max(1, len(msgs) // 12)
        sample = msgs[::step][:12]
        tx = "\n".join(f"  {_speaker(m, contacts)}: {m.text[:120]}" for m in sample)
        blocks.append(f"=== {d['date']} ({d['count']} messages) ===\n{tx}")
    prompt = (
        "For each day below, write one short, specific caption (under 15 words) "
        "saying what was going on in this family group chat that day. Be "
        "concrete, not generic.\n\n" + "\n\n".join(blocks)
    )
    response = _client().messages.create(
        model=config.MODEL,
        max_tokens=2000,
        output_config={"format": {"type": "json_schema", "schema": _CAPTION_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        return {}
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        return {c["date"]: c["caption"] for c in json.loads(text)["captions"]}
    except (json.JSONDecodeError, KeyError):
        return {}


# -- warmth trend --------------------------------------------------------------
def warmth_trend(messages: list[Message]) -> tuple[list[str], list[float], list[float]]:
    """Per quarter: % of messages with warmth markers, % with laughter."""
    from .dynamics import bucket_by_period, filter_periods

    buckets, _ = filter_periods(bucket_by_period(messages, by="quarter"))
    labels, warmth, laughs = [], [], []
    for label, msgs in buckets.items():
        n = len(msgs) or 1
        labels.append(label)
        warmth.append(100 * sum(1 for m in msgs if _WARMTH.search(m.text)) / n)
        laughs.append(100 * sum(1 for m in msgs if _LAUGH.search(m.text)) / n)
    return labels, warmth, laughs
