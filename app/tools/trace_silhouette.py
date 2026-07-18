#!/usr/bin/env python3
"""Trace a monument's skyline from a reference photo into an SVG path.

    pip install pillow
    python3 app/tools/trace_silhouette.py app/reference/yosemite.jpg

Scans each pixel column from the top for the first "terrain" pixel (darker
than the sky), smooths the resulting skyline, simplifies it with
Douglas–Peucker, and prints an SVG path in the stamps' 500×320 scene
coordinates — ready to paste into a ParkArt scene (or hand back to Claude).

Works best on photos where the monument stands against open sky. Tune
--threshold if the sky/terrain split misjudges (higher = more counts as sky).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def skyline(img, threshold: float) -> list[tuple[int, int]]:
    """For each column, the first y from the top darker than `threshold`."""
    gray = img.convert("L")
    w, h = gray.size
    px = gray.load()
    pts: list[tuple[int, int]] = []
    for x in range(w):
        y_hit = h - 1
        for y in range(h):
            if px[x, y] < threshold:
                y_hit = y
                break
        pts.append((x, y_hit))
    return pts


def median_smooth(pts: list[tuple[int, int]], k: int = 5) -> list[tuple[int, int]]:
    ys = [p[1] for p in pts]
    out = []
    half = k // 2
    for i, (x, _) in enumerate(pts):
        window = sorted(ys[max(0, i - half): i + half + 1])
        out.append((x, window[len(window) // 2]))
    return out


def rdp(pts: list[tuple[float, float]], eps: float) -> list[tuple[float, float]]:
    """Douglas–Peucker simplification."""
    if len(pts) < 3:
        return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    norm = (dx * dx + dy * dy) ** 0.5 or 1.0
    dmax, idx = 0.0, 0
    for i in range(1, len(pts) - 1):
        x0, y0 = pts[i]
        d = abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / norm
        if d > dmax:
            dmax, idx = d, i
    if dmax > eps:
        left = rdp(pts[: idx + 1], eps)
        right = rdp(pts[idx:], eps)
        return left[:-1] + right
    return [pts[0], pts[-1]]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image", type=Path)
    ap.add_argument("--threshold", type=float, default=140, help="sky/terrain luminance split (0-255)")
    ap.add_argument("--epsilon", type=float, default=2.2, help="simplification tolerance (px)")
    args = ap.parse_args()

    try:
        from PIL import Image
    except ImportError:
        print("Pillow is required:  pip install pillow", file=sys.stderr)
        return 1

    img = Image.open(args.image)
    if img.width > 1200:
        img = img.resize((1200, int(img.height * 1200 / img.width)))

    pts = median_smooth(skyline(img, args.threshold))

    # Scale into the 500×320 scene box, ground line at y=282.
    w, h = img.size
    lo = min(y for _, y in pts)
    hi = max(y for _, y in pts)
    span = max(hi - lo, 1)
    scaled = [(x * 500 / w, 40 + (y - lo) * (282 - 40) / span) for x, y in pts]
    simple = rdp(scaled, args.epsilon)

    d = f"M{simple[0][0]:.0f} {simple[0][1]:.0f} " + " ".join(
        f"L{x:.0f} {y:.0f}" for x, y in simple[1:]
    )
    print(f"<!-- {args.image.name}: {len(simple)} points, threshold={args.threshold} -->")
    print(f'const TRACED = "{d} L500 282 L0 282 Z";')
    return 0


if __name__ == "__main__":
    main()
