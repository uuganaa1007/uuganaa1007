#!/usr/bin/env python3
"""Generate a Bomberman-style animated SVG from a GitHub contribution calendar.

Usage: python3 scripts/bomberman.py <github-user> <out-dir>
Writes <out-dir>/bomberman.svg (light) and <out-dir>/bomberman-dark.svg.
"""
import os
import re
import sys
import urllib.request

PITCH = 14  # distance between cell origins
CELL = 11  # cell size
MARGIN = 2  # columns/rows of free space around the grid
STEP = 0.11  # seconds per cell walked
DROP = 0.12  # pause while dropping a bomb
FUSE = 0.9  # seconds from drop to explosion
FLAME = 0.35  # how long flames stay on screen
START_HOLD = 1.0
END_HOLD = 2.5

PALETTES = {
    "dark": {
        "empty": "#161b22",
        "levels": ["#1e2c4f", "#2f4a8a", "#4f73c9", "#7aa2f7"],
        "flame": "#ff9e64",
        "core": "#ffe08a",
        "bomb": "#0b0d12",
        "bomb_shine": "#565f89",
        "bomb_edge": "#c0caf5",
    },
    "light": {
        "empty": "#ebedf0",
        "levels": ["#c6d4f5", "#93aff0", "#5d84e6", "#2f5bd3"],
        "flame": "#ff7a33",
        "core": "#ffd24a",
        "bomb": "#1a1b26",
        "bomb_shine": "#7a82a8",
        "bomb_edge": "#1a1b26",
    },
}

# 7x7 Bomberman sprite, drawn at 2px per pixel.
SPRITE = [
    "...P...",
    ".WWWWW.",
    "WWFFFWW",
    "WWEFEWW",
    ".BBBBB.",
    ".WBBBW.",
    ".P...P.",
]
SPRITE_COLORS = {
    "P": "#f7768e",
    "W": "#f5f5f5",
    "F": "#f7c6a3",
    "E": "#1a1b26",
    "B": "#3d6fe0",
}


def fetch_grid(user):
    req = urllib.request.Request(
        f"https://github.com/users/{user}/contributions",
        headers={"User-Agent": "bomberman-contrib"},
    )
    html = urllib.request.urlopen(req, timeout=30).read().decode()
    cells = {}
    for td in re.findall(r"<td[^>]*ContributionCalendar-day[^>]*>", html):
        pos = re.search(r'id="contribution-day-component-(\d+)-(\d+)"', td)
        level = re.search(r'data-level="(\d)"', td)
        if pos and level:
            row, col = int(pos.group(1)), int(pos.group(2))
            cells[(col, row)] = int(level.group(1))
    if not cells:
        sys.exit("no contribution cells found")
    return cells


def simulate(cells):
    """Walk the bomber to each remaining cell, dropping bombs as it goes."""
    alive = {c for c, lvl in cells.items() if lvl > 0}
    cols = max(c for c, _ in cells) + 1
    pos = (-1, 3)
    t = START_HOLD
    waypoints = [(0.0, pos), (t, pos)]
    bombs = []  # (cell, drop_time, explode_time)
    destroyed = {}  # cell -> time

    def walk_to(target):
        nonlocal pos, t
        x, y = pos
        tx, ty = target
        while (x, y) != (tx, ty):
            if x != tx:
                x += 1 if tx > x else -1
            else:
                y += 1 if ty > y else -1
            t += STEP
            waypoints.append((t, (x, y)))
        pos = (x, y)

    while alive:
        target = min(alive, key=lambda c: (abs(c[0] - pos[0]) + abs(c[1] - pos[1]), c))
        walk_to(target)
        drop = t
        t += DROP
        waypoints.append((t, pos))
        boom = drop + FUSE
        bombs.append((target, drop, boom))
        x, y = target
        for c in [(x, y), (x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]:
            if c in alive:
                alive.discard(c)
                destroyed[c] = boom

    walk_to((cols, pos[1]))
    end = max([t] + [b[2] + FLAME for b in bombs]) + END_HOLD
    waypoints.append((end, pos))
    return waypoints, bombs, destroyed, end, cols


def kt(t, total):
    return f"{min(max(t / total, 0.0), 1.0):.5f}"


def render(cells, sim, palette):
    waypoints, bombs, destroyed, total, cols = sim
    p = PALETTES[palette]
    width = (cols + 2 * MARGIN) * PITCH
    height = (7 + 2 * MARGIN) * PITCH
    ox = oy = MARGIN * PITCH
    dur = f"{total:.2f}s"

    def cx(col):
        return ox + col * PITCH + CELL / 2

    def cy(row):
        return oy + row * PITCH + CELL / 2

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">',
        "<title>Bomberman contribution graph</title>",
    ]

    # Cells
    for (col, row), lvl in sorted(cells.items()):
        x, y = ox + col * PITCH, oy + row * PITCH
        color = p["levels"][lvl - 1] if lvl else p["empty"]
        rect = f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{color}"'
        if (col, row) in destroyed:
            out.append(
                rect + f'><animate attributeName="fill" calcMode="discrete" '
                f'values="{color};{p["empty"]}" keyTimes="0;{kt(destroyed[(col, row)], total)}" '
                f'dur="{dur}" repeatCount="indefinite"/></rect>'
            )
        else:
            out.append(rect + "/>")

    # Bombs
    for (col, row), drop, boom in bombs:
        x, y = cx(col), cy(row)
        out.append(
            f'<g opacity="0"><animate attributeName="opacity" calcMode="discrete" values="0;1;0" '
            f'keyTimes="0;{kt(drop, total)};{kt(boom, total)}" dur="{dur}" repeatCount="indefinite"/>'
            f'<circle cx="{x}" cy="{y + 0.5}" r="4.6" fill="{p["bomb"]}" stroke="{p["bomb_edge"]}" stroke-width="1">'
            f'<animate attributeName="r" values="4.6;5.4;4.6" dur="0.3s" repeatCount="indefinite"/></circle>'
            f'<circle cx="{x - 1.6}" cy="{y - 1.2}" r="1.2" fill="{p["bomb_shine"]}"/>'
            f'<rect x="{x + 2}" y="{y - 6}" width="2" height="2" fill="{p["flame"]}">'
            f'<animate attributeName="fill" values="{p["flame"]};{p["core"]};{p["flame"]}" '
            f'dur="0.2s" repeatCount="indefinite"/></rect></g>'
        )

    # Flames: a plus-shaped blast clipped to the grid
    for (col, row), _, boom in bombs:
        x0, x1 = max(col - 1, 0), min(col + 1, cols - 1)
        y0, y1 = max(row - 1, 0), min(row + 1, 6)
        h = (ox + x0 * PITCH - 1.5, oy + row * PITCH - 1.5, (x1 - x0) * PITCH + CELL + 3, CELL + 3)
        v = (ox + col * PITCH - 1.5, oy + y0 * PITCH - 1.5, CELL + 3, (y1 - y0) * PITCH + CELL + 3)
        rects = "".join(
            f'<rect x="{a:.1f}" y="{b:.1f}" width="{w:.1f}" height="{hh:.1f}" rx="4" fill="{p["flame"]}"/>'
            for a, b, w, hh in (h, v)
        )
        core = (
            f'<rect x="{h[0] + 3:.1f}" y="{h[1] + 3:.1f}" width="{h[2] - 6:.1f}" height="{h[3] - 6:.1f}" rx="3" fill="{p["core"]}"/>'
            f'<rect x="{v[0] + 3:.1f}" y="{v[1] + 3:.1f}" width="{v[2] - 6:.1f}" height="{v[3] - 6:.1f}" rx="3" fill="{p["core"]}"/>'
        )
        out.append(
            f'<g opacity="0"><animate attributeName="opacity" calcMode="discrete" values="0;1;0" '
            f'keyTimes="0;{kt(boom, total)};{kt(boom + FLAME, total)}" dur="{dur}" repeatCount="indefinite"/>'
            f"{rects}{core}</g>"
        )

    # Bomber
    times, values = [], []
    for t, (col, row) in waypoints:
        k = kt(t, total)
        if times and k <= times[-1]:
            continue
        times.append(k)
        values.append(f"{cx(col) - 7:.1f} {cy(row) - 8:.1f}")
    times[0], times[-1] = "0", "1"
    pixels = "".join(
        f'<rect x="{i * 2}" y="{j * 2}" width="2" height="2" fill="{SPRITE_COLORS[ch]}"/>'
        for j, line in enumerate(SPRITE)
        for i, ch in enumerate(line)
        if ch != "."
    )
    out.append(
        f'<g><animateTransform attributeName="transform" type="translate" values="{";".join(values)}" '
        f'keyTimes="{";".join(times)}" dur="{dur}" repeatCount="indefinite"/>'
        f'<g><animateTransform attributeName="transform" type="translate" values="0 0;0 -1;0 0" '
        f'dur="0.22s" repeatCount="indefinite"/>{pixels}</g></g>'
    )

    out.append("</svg>")
    return "\n".join(out)


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    user, out_dir = sys.argv[1], sys.argv[2]
    cells = fetch_grid(user)
    sim = simulate(cells)
    os.makedirs(out_dir, exist_ok=True)
    for palette, name in (("light", "bomberman.svg"), ("dark", "bomberman-dark.svg")):
        with open(os.path.join(out_dir, name), "w") as f:
            f.write(render(cells, sim, palette))
    print(f"{len(sim[1])} bombs, {sim[3]:.1f}s loop -> {out_dir}")


if __name__ == "__main__":
    main()
