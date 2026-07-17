#!/usr/bin/env python3
"""Raster-etch a bitmap with the custom DK-8-KZ firmware.

Thresholds the image to 1-bit, resamples to the step grid (0.148 mm/step),
and burns dark-pixel runs row by row, boustrophedon. Travel moves run fast
and laser-off; burn runs at --feed-ms. Rows advance downward (Y-) from the
starting head position, image extends rightward (X+).

  etch_image.py --image ../chrixlogo.png --width-mm 30 [--feed-ms 20]
                [--travel-ms 2] [--threshold 128] [--dry-run]
"""
import argparse
from PIL import Image
from plotter import Plotter, DIRS


def thin(grid, w, h):
    """Zhang-Suen thinning: reduce strokes to 1-px centerlines."""
    g = [row[:] for row in grid]
    def nbrs(x, y):
        return [g[(y-1) % h][x], g[(y-1) % h][(x+1) % w], g[y][(x+1) % w],
                g[(y+1) % h][(x+1) % w], g[(y+1) % h][x], g[(y+1) % h][(x-1) % w],
                g[y][(x-1) % w], g[(y-1) % h][(x-1) % w]]
    changed = True
    while changed:
        changed = False
        for phase in (0, 1):
            kill = []
            for y in range(1, h - 1):
                for x in range(1, w - 1):
                    if not g[y][x]:
                        continue
                    p = nbrs(x, y)
                    b = sum(p)
                    if not (2 <= b <= 6):
                        continue
                    a = sum(1 for i in range(8) if not p[i] and p[(i+1) % 8])
                    if a != 1:
                        continue
                    if phase == 0:
                        if (p[0] and p[2] and p[4]) or (p[2] and p[4] and p[6]):
                            continue
                    else:
                        if (p[0] and p[2] and p[6]) or (p[0] and p[4] and p[6]):
                            continue
                    kill.append((x, y))
            for (x, y) in kill:
                g[y][x] = 0
            changed = changed or bool(kill)
    return g


def skeleton_paths(g, w, h):
    """Walk the 1-px skeleton into polylines (8-connected)."""
    pts = {(x, y) for y in range(h) for x in range(w) if g[y][x]}
    def neighbors(p):
        x, y = p
        return [(x+dx, y+dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                if (dx or dy) and (x+dx, y+dy) in pts]
    deg = {p: len(neighbors(p)) for p in pts}
    unvisited = set(pts)
    paths = []
    # trace from endpoints first, then whatever loops remain
    for seed_deg in (1, None):
        for p in sorted(unvisited):
            if p not in unvisited:
                continue
            if seed_deg and deg[p] != seed_deg:
                continue
            path = [p]
            unvisited.discard(p)
            cur = p
            while True:
                nxt = [q for q in neighbors(cur) if q in unvisited]
                if not nxt:
                    break
                # prefer straight-ish continuation
                cur = nxt[0]
                unvisited.discard(cur)
                path.append(cur)
            if len(path) > 1:
                paths.append(path)
    return paths


def rasterize(path, width_steps, threshold):
    im = Image.open(path).convert("L")
    h = max(1, round(im.height * width_steps / im.width))
    im = im.resize((width_steps, h), Image.LANCZOS)
    px = im.load()
    rows = []
    for y in range(h):
        runs, x = [], 0
        while x < width_steps:
            if px[x, y] < threshold:
                x0 = x
                while x < width_steps and px[x, y] < threshold:
                    x += 1
                runs.append((x0, x))     # [x0, x) dark
            else:
                x += 1
        rows.append(runs)
    return rows, h


def outline_main(a):
    w = round(a.width_mm * a.steps_per_mm)
    im = Image.open(a.image).convert("L")
    h = max(1, round(im.height * w / im.width))
    im = im.resize((w, h), Image.LANCZOS)
    px = im.load()
    grid = [[1 if px[x, y] < a.threshold else 0 for x in range(w)]
            for y in range(h)]
    grid = thin(grid, w, h)
    paths = skeleton_paths(grid, w, h)
    total = sum(len(p) for p in paths)
    print(f"{a.image}: {w}x{h} steps = {a.width_mm:.1f}x{h/a.steps_per_mm:.1f} mm, "
          f"{len(paths)} strokes, {total} burn steps, "
          f"~{total*a.feed_ms/60000:.1f} min burning")
    if a.dry_run:
        for y in range(0, h, max(1, h // 24)):
            print("".join("#" if grid[y][x] else " " for x in range(0, w, 2)))
        return

    pl = Plotter(a.port)
    cx, cy = 0, 0     # head position, steps from image top-left (y down)
    def goto(tx, ty, laser, ms):
        nonlocal cx, cy
        dx, dy = tx - cx, ty - cy
        if dx:
            pl.move(DIRS["r"] if dx > 0 else DIRS["l"], abs(dx),
                    laser=laser, step_ms=ms)
        if dy:
            pl.move(DIRS["d"] if dy > 0 else DIRS["u"], abs(dy),
                    laser=laser, step_ms=ms)
        cx, cy = tx, ty
    try:
        # greedy nearest-first stroke order to minimize travel
        remaining = list(paths)
        while remaining:
            remaining.sort(key=lambda p: abs(p[0][0]-cx) + abs(p[0][1]-cy))
            path = remaining.pop(0)
            print(f"  stroke ({len(path)} steps), {len(remaining)} left")
            pl.speed(a.travel_ms)
            goto(path[0][0], path[0][1], laser=False, ms=a.travel_ms)
            pl.speed(a.feed_ms)
            for (x, y) in path[1:]:
                goto(x, y, laser=True, ms=a.feed_ms)
        pl.speed(a.travel_ms)
        goto(0, 0, laser=False, ms=a.travel_ms)   # park at origin
        print("done")
    finally:
        pl.reset()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--image", required=True)
    ap.add_argument("--width-mm", type=float, required=True)
    ap.add_argument("--steps-per-mm", type=float, default=6.75)
    ap.add_argument("--feed-ms", type=int, default=20)
    ap.add_argument("--travel-ms", type=int, default=2)
    ap.add_argument("--threshold", type=int, default=128)
    ap.add_argument("--mode", choices=["raster", "outline"], default="raster",
                    help="raster: scanline rows (filled art/photos); "
                         "outline: thin to centerlines and trace each stroke "
                         "continuously (line art)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.mode == "outline":
        return outline_main(a)

    w = round(a.width_mm * a.steps_per_mm)
    rows, h = rasterize(a.image, w, a.threshold)
    burn = sum(x1 - x0 for r in rows for (x0, x1) in r)
    est = (burn * a.feed_ms + (h * w // 2) * a.travel_ms) / 1000
    print(f"{a.image}: {w}x{h} steps = {a.width_mm:.1f}x{h/a.steps_per_mm:.1f} mm, "
          f"{burn} burn steps, ~{est/60:.1f} min")
    if a.dry_run:
        for y in range(0, h, max(1, h // 24)):   # coarse preview
            line = [" "] * w
            for (x0, x1) in rows[y]:
                for x in range(x0, x1):
                    line[x] = "#"
            print("".join(line[::2]))
        return

    pl = Plotter(a.port)
    x = 0                     # current head x, in steps from image left
    try:
        for y, runs in enumerate(rows):
            if y % max(1, h // 10) == 0:
                print(f"  row {y}/{h}")
            if runs:
                if y % 2:     # boustrophedon: odd rows right-to-left
                    runs = [(x0, x1) for (x0, x1) in reversed(runs)]
                    order = [(x1, x0) for (x0, x1) in runs]
                else:
                    order = runs
                for (sx, ex) in order:
                    if sx != x:                       # travel to run start
                        pl.speed(a.travel_ms)
                        d = "r" if sx > x else "l"
                        pl.move(DIRS[d], abs(sx - x), laser=False,
                                step_ms=a.travel_ms)
                        x = sx
                    pl.speed(a.feed_ms)               # burn the run
                    d = "r" if ex > x else "l"
                    pl.move(DIRS[d], abs(ex - x), laser=True,
                            step_ms=a.feed_ms)
                    x = ex
            if y < h - 1:
                pl.speed(a.travel_ms)
                pl.move(DIRS["d"], 1, laser=False, step_ms=a.travel_ms)
        # park back at image origin (top-left)
        pl.speed(a.travel_ms)
        if x:
            pl.move(DIRS["l"], x, laser=False, step_ms=a.travel_ms)
        pl.move(DIRS["u"], h - 1, laser=False, step_ms=a.travel_ms)
        print("done")
    finally:
        pl.reset()

if __name__ == "__main__":
    main()
