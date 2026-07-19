#!/usr/bin/env python3
"""
Render data/contributions.json (produced by fetch_contributions.py) as a GitHub-style
contribution heatmap SVG: a 53-week x 7-day grid of rounded BOXES that pop into place
(scale + fade) with a bright color "flash" on filled cells, revealed once in a
diagonal sweep -- left to right across weeks, cascading top to bottom within each
week (CSS keyframes, plays on load then freezes -- no looping). Minimal footer with
just the total-contributions line, no border/title-bar/legend chrome.

Run by .github/workflows/update-profile-art.yml after fetch_contributions.py.
"""
import datetime
import json
import os

HERE = os.path.dirname(__file__)
IN_PATH = os.path.join(HERE, "..", "data", "contributions.json")
OUT_PATH = os.path.join(HERE, "..", "contrib-heatmap.svg")

# GitHub's actual dark-mode contribution palette: empty -> brightest (5 levels, 0-4).
PALETTE = ["#161b22", "#15663e", "#039145", "#23bb44", "#36e152"]

CELL = 13
GAP = 3
STEP = CELL + GAP  # 16

GRID_LEFT = 34          # leaves room for the Mon/Wed/Fri labels at x=2
GRID_TOP = 24           # leaves room for the month labels at y=16
DOW_LABEL_X = 2
DOW_ROW_OFFSET = 11     # baseline offset inside a row for the Mon/Wed/Fri labels
MONTH_LABEL_Y = GRID_TOP - 8  # 16
RIGHT_PAD = 9           # canvas margin to the right of the last column
FOOTER_GAP = 19         # gap from grid bottom to the total-contributions baseline
BOTTOM_MARGIN = 6       # gap from that baseline to the canvas bottom edge

MUTED = "#7d8590"
TEXT = "#e6edf3"
FONT_FAMILY = "-apple-system,Segoe UI,Helvetica,Arial,sans-serif"

# reveal timing (one-shot, diagonal sweep: left->right across weeks + top->bottom
# cascade within a week)
COL_T = 0.0651      # per-column (week) delay contribution
ROW_T = 0.0358      # per-row (weekday) delay contribution
POP_DUR = 0.55      # scale+fade "pop" duration
FLASH_DUR = POP_DUR + 0.15  # brightness "flash" duration on filled cells


def level_for(count):
    if count == 0:
        return 0
    if count <= 5:
        return 1
    if count <= 15:
        return 2
    if count <= 30:
        return 3
    return 4


def build_grid(days):
    first = datetime.date.fromisoformat(days[0]["date"])
    lead_pad = (first.weekday() + 1) % 7  # sunday=0
    grid = []
    col = [None] * lead_pad
    for d in days:
        date = datetime.date.fromisoformat(d["date"])
        weekday = (date.weekday() + 1) % 7
        while len(col) < weekday:
            col.append(None)
        col.append((d["date"], d["count"], level_for(d["count"])))
        if len(col) == 7:
            grid.append(col)
            col = []
    if col:
        while len(col) < 7:
            col.append(None)
        grid.append(col)
    return grid


def fmt_delay(seconds):
    # Compact formatting (no padded trailing zeros) to match a JS-style number-to-string.
    return f"{round(seconds, 3):g}"


def render(data):
    days = data["days"]
    grid = build_grid(days)
    n_cols = len(grid)
    art_h = 7 * STEP - GAP

    month_labels = []
    seen_months = set()
    for ci, column in enumerate(grid):
        for cell in column:
            if cell is None:
                continue
            date = datetime.date.fromisoformat(cell[0])
            key = (date.year, date.month)
            if key not in seen_months and date.day <= 7:
                seen_months.add(key)
                month_labels.append((ci, date.strftime("%b")))
            break

    canvas_w = GRID_LEFT + (n_cols - 1) * STEP + CELL + RIGHT_PAD
    footer_y = GRID_TOP + art_h + FOOTER_GAP
    canvas_h = footer_y + BOTTOM_MARGIN

    css = (
        f'\n  text.lbl {{ fill:{MUTED}; font-size:13px; font-weight:600; }}'
        f'\n  text.total {{ fill:{TEXT}; font-size:15px; font-weight:700; }}'
        f'\n  .c {{ transform-box:fill-box; transform-origin:center; opacity:0; '
        f'animation:pop {POP_DUR}s ease-out both; }}'
        f'\n  .g {{ animation:pop {POP_DUR}s ease-out both, flash {FLASH_DUR}s ease-out both; }}'
        f'\n  @keyframes pop {{ 0%{{opacity:0;transform:scale(.2)}} '
        f'60%{{opacity:1;transform:scale(1.1)}} 100%{{opacity:1;transform:scale(1)}} }}'
        f'\n  @keyframes flash {{ 0%{{filter:brightness(2.4)}} 45%{{filter:brightness(2.4)}} '
        f'100%{{filter:brightness(1)}} }}'
        f'\n  @media (prefers-reduced-motion: reduce) {{ .c {{ opacity:1 !important; '
        f'animation:none !important; }} }}\n'
    )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" '
        f'viewBox="0 0 {canvas_w} {canvas_h}" font-family="{FONT_FAMILY}">',
        f'<style>{css}</style>',
        f'<rect width="{canvas_w}" height="{canvas_h}" fill="none"/>',
    ]

    for ci, label in month_labels:
        x = GRID_LEFT + ci * STEP
        parts.append(f'<text class="lbl" x="{x}" y="{MONTH_LABEL_Y}">{label}</text>')

    for ri, wname in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        y = GRID_TOP + ri * STEP + DOW_ROW_OFFSET
        parts.append(f'<text class="lbl" x="{DOW_LABEL_X}" y="{y}">{wname}</text>')

    # the boxes -- each a rounded rect that pops in (scale+fade), filled cells also
    # get a brightness "flash"; diagonal reveal via per-column + per-row delay.
    for ci, column in enumerate(grid):
        gx = GRID_LEFT + ci * STEP
        for ri, cell in enumerate(column):
            if cell is None:
                continue
            date_s, count, lvl = cell
            gy = GRID_TOP + ri * STEP
            delay = fmt_delay(ci * COL_T + ri * ROW_T)
            cls = "c g" if lvl > 0 else "c e"
            parts.append(
                f'<rect class="{cls}" x="{gx}" y="{gy}" width="{CELL}" height="{CELL}" rx="2.5" '
                f'fill="{PALETTE[lvl]}" style="animation-delay:{delay}s"/>'
            )

    total = data["total_contributions"]
    parts.append(
        f'<text class="total" x="{GRID_LEFT}" y="{footer_y}">'
        f'{total:,} contributions in the last year</text>'
    )

    parts.append("</svg>")
    return "".join(parts)


if __name__ == "__main__":
    data = json.load(open(IN_PATH))
    svg = render(data)
    with open(OUT_PATH, "w") as f:
        f.write(svg)
    print(f"wrote {OUT_PATH} ({len(svg)} bytes)")