"""Self-contained HTML report with pure-SVG charts (no external dependencies).

The generated file opens in any browser and prints cleanly to PDF.
"""

from __future__ import annotations

import html
from datetime import datetime

PALETTE = ["#2c5f8a", "#d1495b", "#3f9e6e", "#e8a13c", "#7b5ea7",
           "#4ba3c3", "#8a6d3b", "#c65fa2", "#5a6b7a", "#96b35c"]


def _e(s) -> str:
    return html.escape(str(s))


def _first(name: str) -> str:
    return name.split()[0]


def _fmt_dur(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 90:
        return f"{seconds:.0f}s"
    if seconds < 5400:
        return f"{seconds / 60:.0f}m"
    return f"{seconds / 3600:.1f}h"


# -- SVG chart builders -------------------------------------------------------
def line_chart(labels: list[str], series: dict[str, list[float]],
               unit: str = "%", height: int = 300) -> str:
    if not labels or not series:
        return ""
    w, pad_l, pad_r, pad_t, pad_b = 860, 44, 150, 16, 46
    iw, ih = w - pad_l - pad_r, height - pad_t - pad_b
    ymax = max(10.0, max(max(v) for v in series.values()) * 1.15)
    n = len(labels)

    def x(i):
        return pad_l + (iw * i / max(1, n - 1))

    def y(v):
        return pad_t + ih - (ih * v / ymax)

    parts = [f'<svg viewBox="0 0 {w} {height}" class="chart">']
    for g in range(5):
        gy = pad_t + ih * g / 4
        val = ymax * (1 - g / 4)
        parts.append(f'<line x1="{pad_l}" y1="{gy:.0f}" x2="{pad_l + iw}" y2="{gy:.0f}" class="grid"/>')
        parts.append(f'<text x="{pad_l - 6}" y="{gy + 4:.0f}" class="tick" text-anchor="end">{val:.0f}{unit}</text>')
    step = max(1, n // 8)
    for i in range(0, n, step):
        parts.append(f'<text x="{x(i):.0f}" y="{height - 24}" class="tick" text-anchor="middle">{_e(labels[i])}</text>')
    for k, (name, vals) in enumerate(series.items()):
        color = PALETTE[k % len(PALETTE)]
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round"/>')
        ly = pad_t + 16 + k * 18
        parts.append(f'<rect x="{w - pad_r + 10}" y="{ly - 9}" width="10" height="10" fill="{color}" rx="2"/>')
        parts.append(f'<text x="{w - pad_r + 26}" y="{ly}" class="legend">{_e(_first(name))}</text>')
    parts.append("</svg>")
    return "".join(parts)


def bar_chart(items: list[tuple[str, int]], height: int = 260) -> str:
    if not items:
        return ""
    w, pad_l, pad_t, pad_b = 860, 44, 14, 46
    iw, ih = w - pad_l - 16, height - pad_t - pad_b
    ymax = max(v for _, v in items) * 1.1 or 1
    bw = iw / len(items)
    parts = [f'<svg viewBox="0 0 {w} {height}" class="chart">']
    for g in range(4):
        gy = pad_t + ih * g / 3
        parts.append(f'<line x1="{pad_l}" y1="{gy:.0f}" x2="{pad_l + iw}" y2="{gy:.0f}" class="grid"/>')
        parts.append(f'<text x="{pad_l - 6}" y="{gy + 4:.0f}" class="tick" text-anchor="end">{ymax * (1 - g / 3):.0f}</text>')
    step = max(1, len(items) // 10)
    for i, (label, v) in enumerate(items):
        bx, bh = pad_l + i * bw, ih * v / ymax
        parts.append(f'<rect x="{bx + 1:.1f}" y="{pad_t + ih - bh:.1f}" width="{max(1, bw - 2):.1f}" height="{bh:.1f}" fill="#2c5f8a" opacity="0.85"/>')
        if i % step == 0:
            parts.append(f'<text x="{bx + bw / 2:.0f}" y="{height - 24}" class="tick" text-anchor="middle">{_e(label)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def heatmap(grid: list[list[int]]) -> str:
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    w, cell, pad_l, pad_t = 860, 31, 44, 26
    height = pad_t + 7 * (cell + 2) + 14
    vmax = max((max(r) for r in grid), default=1) or 1
    parts = [f'<svg viewBox="0 0 {w} {height}" class="chart">']
    for h in range(0, 24, 3):
        parts.append(f'<text x="{pad_l + h * (cell + 2) + cell / 2:.0f}" y="16" class="tick" text-anchor="middle">{h}:00</text>')
    for d in range(7):
        cy = pad_t + d * (cell + 2)
        parts.append(f'<text x="{pad_l - 8}" y="{cy + cell / 2 + 4:.0f}" class="tick" text-anchor="end">{days[d]}</text>')
        for h in range(24):
            v = grid[d][h]
            op = 0.06 + 0.94 * (v / vmax) if v else 0.04
            parts.append(
                f'<rect x="{pad_l + h * (cell + 2)}" y="{cy}" width="{cell}" height="{cell}" '
                f'rx="4" fill="#2c5f8a" opacity="{op:.2f}"><title>{days[d]} {h}:00 — {v} messages</title></rect>'
            )
    parts.append("</svg>")
    return "".join(parts)


def scatter(points: list[tuple[str, float, float]], xlabel: str, ylabel: str) -> str:
    if not points:
        return ""
    w, height, pad_l, pad_r, pad_t, pad_b = 860, 360, 56, 20, 16, 50
    iw, ih = w - pad_l - pad_r, height - pad_t - pad_b
    xmax = max(p[1] for p in points) * 1.12 or 1
    ymax = max(max(p[2] for p in points) * 1.15, 10)
    parts = [f'<svg viewBox="0 0 {w} {height}" class="chart">']
    for g in range(5):
        gy = pad_t + ih * g / 4
        parts.append(f'<line x1="{pad_l}" y1="{gy:.0f}" x2="{pad_l + iw}" y2="{gy:.0f}" class="grid"/>')
        parts.append(f'<text x="{pad_l - 6}" y="{gy + 4:.0f}" class="tick" text-anchor="end">{ymax * (1 - g / 4):.0f}</text>')
    parts.append(f'<text x="{pad_l + iw / 2:.0f}" y="{height - 10}" class="axis" text-anchor="middle">{_e(xlabel)}</text>')
    parts.append(f'<text x="16" y="{pad_t + ih / 2:.0f}" class="axis" text-anchor="middle" transform="rotate(-90 16 {pad_t + ih / 2:.0f})">{_e(ylabel)}</text>')
    for k, (name, xv, yv) in enumerate(points):
        px = pad_l + iw * xv / xmax
        py = pad_t + ih - ih * yv / ymax
        color = PALETTE[k % len(PALETTE)]
        parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="7" fill="{color}" opacity="0.85"/>')
        anchor = "end" if px > pad_l + iw * 0.82 else "start"
        dx = -10 if anchor == "end" else 10
        parts.append(f'<text x="{px + dx:.1f}" y="{py + 4:.1f}" class="dot" text-anchor="{anchor}">{_e(_first(name))}</text>')
    parts.append("</svg>")
    return "".join(parts)


def hbar_chart(items: list[tuple[str, float, str]], unit_note: str = "") -> str:
    """Horizontal bars: (label, value_for_width, display_text)."""
    if not items:
        return ""
    w, row, pad_l, pad_t = 860, 30, 130, 10
    height = pad_t + len(items) * row + 10
    vmax = max(v for _, v, _ in items) or 1
    parts = [f'<svg viewBox="0 0 {w} {height}" class="chart">']
    for i, (label, v, disp) in enumerate(items):
        cy = pad_t + i * row
        bw = (w - pad_l - 110) * v / vmax
        parts.append(f'<text x="{pad_l - 8}" y="{cy + 19}" class="tick" text-anchor="end">{_e(_first(label))}</text>')
        parts.append(f'<rect x="{pad_l}" y="{cy + 6}" width="{max(2, bw):.1f}" height="18" rx="4" fill="#2c5f8a" opacity="0.8"/>')
        parts.append(f'<text x="{pad_l + max(2, bw) + 8:.1f}" y="{cy + 19}" class="dot">{_e(disp)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def matrix(people: list[str], edges: dict[tuple[str, str], int]) -> str:
    if not people:
        return ""
    n = len(people)
    cell, pad_l, pad_t = 52, 120, 96
    w = pad_l + n * (cell + 3) + 20
    height = pad_t + n * (cell + 3) + 16
    vmax = max(edges.values(), default=1) or 1
    parts = [f'<svg viewBox="0 0 {w} {height}" class="chart">']
    parts.append(f'<text x="{pad_l - 10}" y="20" class="axis" text-anchor="end">replies ↓ to →</text>')
    for j, target in enumerate(people):
        tx = pad_l + j * (cell + 3) + cell / 2
        parts.append(f'<text x="{tx:.0f}" y="{pad_t - 10}" class="tick" text-anchor="start" transform="rotate(-40 {tx:.0f} {pad_t - 10})">{_e(_first(target))}</text>')
    for i, replier in enumerate(people):
        cy = pad_t + i * (cell + 3)
        parts.append(f'<text x="{pad_l - 8}" y="{cy + cell / 2 + 4:.0f}" class="tick" text-anchor="end">{_e(_first(replier))}</text>')
        for j, target in enumerate(people):
            v = edges.get((replier, target), 0)
            cx = pad_l + j * (cell + 3)
            if i == j:
                parts.append(f'<rect x="{cx}" y="{cy}" width="{cell}" height="{cell}" rx="6" fill="#eceff2"/>')
                continue
            op = 0.05 + 0.95 * (v / vmax) if v else 0.04
            fill = "#2c5f8a"
            parts.append(f'<rect x="{cx}" y="{cy}" width="{cell}" height="{cell}" rx="6" fill="{fill}" opacity="{op:.2f}"><title>{_e(replier)} → {_e(target)}: {v} replies</title></rect>')
            if v:
                tcol = "#ffffff" if v / vmax > 0.45 else "#334"
                parts.append(f'<text x="{cx + cell / 2}" y="{cy + cell / 2 + 4}" class="cell" fill="{tcol}" text-anchor="middle">{v}</text>')
    parts.append("</svg>")
    return "".join(parts)


# -- report assembly ----------------------------------------------------------
_CSS = """
body{font-family:-apple-system,'Helvetica Neue',Arial,sans-serif;margin:0;
 background:#f4f6f8;color:#243342;line-height:1.55}
.wrap{max-width:960px;margin:0 auto;padding:32px 24px 64px}
header{border-bottom:3px solid #2c5f8a;padding-bottom:14px;margin-bottom:28px}
h1{font-size:26px;margin:0 0 4px;color:#1a3d5c}
h2{font-size:19px;color:#2c5f8a;margin:38px 0 6px}
.sub{color:#5a6b7a;font-size:13px}
.note{color:#5a6b7a;font-size:13px;margin:2px 0 12px}
.card{background:#fff;border-radius:12px;padding:18px 20px;margin:12px 0;
 box-shadow:0 1px 3px rgba(20,40,60,.08)}
.chart{width:100%;height:auto;display:block}
.grid{stroke:#e3e8ee;stroke-width:1}
.tick{font-size:11px;fill:#5a6b7a}
.legend{font-size:12px;fill:#243342}
.axis{font-size:12px;fill:#5a6b7a;font-weight:600}
.dot{font-size:11px;fill:#243342;font-weight:600}
.cell{font-size:11px;font-weight:600}
table{border-collapse:collapse;width:100%;font-size:13px}
th{background:#2c5f8a;color:#fff;padding:7px 9px;text-align:left}
td{padding:6px 9px;border-bottom:1px solid #e8edf2}
tr:nth-child(even) td{background:#f6f9fb}
.sig{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}
.sig .card{margin:0}
.sig h3{margin:0 0 6px;font-size:15px;color:#1a3d5c}
.sig .emoji{font-size:22px;letter-spacing:4px;margin:4px 0}
.sig .terms{font-size:12.5px;color:#3d4f60}
.peak{display:flex;gap:12px;align-items:baseline;padding:7px 0;
 border-bottom:1px solid #eef2f5}
.peak .d{font-weight:700;color:#2c5f8a;min-width:100px}
.peak .n{color:#5a6b7a;font-size:12px;min-width:78px}
.ai{white-space:pre-wrap;font-size:14px}
.ai h1,.ai h2{margin:14px 0 4px}
@media print{body{background:#fff}.card{box-shadow:none;border:1px solid #dde3e9}}
"""


def section(title: str, note: str, body: str) -> str:
    return f"<h2>{_e(title)}</h2><p class='note'>{_e(note)}</p><div class='card'>{body}</div>"


def build(title: str, subtitle: str, sections: list[str]) -> str:
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{_e(title)}</title><style>{_CSS}</style></head><body>"
        "<div class='wrap'><header>"
        f"<h1>{_e(title)}</h1><div class='sub'>{_e(subtitle)} · generated "
        f"{datetime.now():%b %d, %Y %H:%M} by imessage-insights · inferred from "
        "message text — a strong hypothesis, not a verdict</div></header>"
        + "".join(sections)
        + "</div></body></html>"
    )
