#!/usr/bin/env python3
"""Download public-domain/free reference photos for the stamp artwork.

Run this LOCALLY (it needs open internet access, which Claude's build
environment doesn't have):

    python3 app/tools/fetch_references.py

For each park it searches Wikimedia Commons for the park's monumental view,
downloads the top result into ``app/reference/<slug>.jpg``, and records the
author/license for every file in ``app/reference/CREDITS.txt``.

Then hand the folder back to Claude ("references are in app/reference/") and
the exact silhouettes get traced into the stamp engravings — or run
``trace_silhouette.py`` yourself to see the extracted skyline path.

Uses only the Python standard library. Wikimedia Commons hosts free-licensed
and public-domain media; the credits file tells you the license of each file
you downloaded — glance at it before publishing the derived artwork.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# The monumental subject per park — tuned queries for the classic views.
QUERIES: dict[str, str] = {
    "yosemite": "Half Dome from Yosemite Valley",
    "grand-canyon": "Grand Canyon South Rim Vishnu Temple",
    "grand-teton": "Grand Teton peak Snake River",
    "joshua-tree": "Joshua tree Yucca brevifolia Joshua Tree National Park",
    "yellowstone": "Old Faithful geyser eruption",
    "zion": "Great White Throne Zion",
    "glacier": "Mount Reynolds Glacier National Park",
    "acadia": "Bass Harbor Head Lighthouse",
}

API = "https://commons.wikimedia.org/w/api.php"
UA = "TrailheadStampArt/1.0 (personal project; reference images for engravings)"
OUT_DIR = Path(__file__).resolve().parent.parent / "reference"


def api_call(params: dict) -> dict:
    query = urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def find_image(query: str) -> dict | None:
    """Top bitmap search hit with its url + license metadata, or None."""
    data = api_call({
        "action": "query",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": 6,  # File:
        "gsrlimit": 5,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": 1600,
    })
    pages = (data.get("query") or {}).get("pages") or {}
    # Pages come keyed by pageid with an 'index' for search rank.
    for page in sorted(pages.values(), key=lambda p: p.get("index", 99)):
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        url = info.get("thumburl") or info.get("url")
        if not url or not url.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        meta = info.get("extmetadata") or {}
        get = lambda k: (meta.get(k) or {}).get("value", "?")
        return {
            "title": page.get("title", "?"),
            "url": url,
            "page_url": info.get("descriptionurl", "?"),
            "license": get("LicenseShortName"),
            "artist": get("Artist"),
        }
    return None


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        dest.write_bytes(resp.read())


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    credits: list[str] = ["Reference images downloaded from Wikimedia Commons.", ""]
    failures = 0

    for slug, query in QUERIES.items():
        print(f"[{slug}] searching: {query!r}")
        try:
            hit = find_image(query)
            if hit is None:
                print(f"  !! no usable result — search Commons manually and save as {slug}.jpg")
                failures += 1
                continue
            dest = OUT_DIR / f"{slug}.jpg"
            download(hit["url"], dest)
            print(f"  -> {dest.name}  ({hit['license']})  {hit['title']}")
            credits += [
                f"{slug}.jpg",
                f"  file:    {hit['title']}",
                f"  source:  {hit['page_url']}",
                f"  license: {hit['license']}",
                f"  artist:  {hit['artist']}",
                "",
            ]
        except Exception as exc:
            print(f"  !! failed: {exc}")
            failures += 1

    (OUT_DIR / "CREDITS.txt").write_text("\n".join(credits))
    print(f"\nDone. {len(QUERIES) - failures}/{len(QUERIES)} downloaded to {OUT_DIR}")
    print("Check CREDITS.txt for licenses. Replace any image you'd rather swap —")
    print("the filename (slug.jpg) is all that matters.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
