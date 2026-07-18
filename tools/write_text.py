#!/usr/bin/env python3
"""Engrave single-stroke text with the custom DK-8-KZ firmware.

Uses plotter.py's Plotter. Glyphs are polylines in a unit box (y up,
baseline 0, cap height 1.0, x-height 0.55, advance 0.7). Only the glyphs
needed so far are defined — extend GLYPHS as required.

By default the head stall-homes to the machine's top-left corner first and
drops down by the cap height, so the text lands at an absolute, repeatable
position. With --no-home the head must START at the BOTTOM-LEFT of the text
area. X+ is 'r', Y+ is 'u' (flip with --flip-x/--flip-y if the machine's
axes are mirrored).

  write_text.py --text "Chr1x.com" --length-mm 25 --steps-per-mm 6.75 \
                --feed-ms 20 [--dry-run]
"""
import argparse, math, time
from plotter import Plotter, DIRS

ADV = 0.7   # per-character advance, font units

GLYPHS = {
    'C': [[(0.5,0.85),(0.35,1.0),(0.15,1.0),(0.0,0.85),(0.0,0.15),
           (0.15,0.0),(0.35,0.0),(0.5,0.15)]],
    'h': [[(0.0,1.0),(0.0,0.0)],
          [(0.0,0.4),(0.15,0.55),(0.35,0.55),(0.5,0.4),(0.5,0.0)]],
    'r': [[(0.0,0.55),(0.0,0.0)],
          [(0.0,0.35),(0.15,0.55),(0.35,0.55)]],
    '1': [[(0.1,0.8),(0.25,1.0),(0.25,0.0)],
          [(0.1,0.0),(0.4,0.0)]],
    'x': [[(0.0,0.55),(0.5,0.0)],
          [(0.0,0.0),(0.5,0.55)]],
    '.': [[(0.2,0.0),(0.3,0.0),(0.3,0.08),(0.2,0.08),(0.2,0.0)]],
    'c': [[(0.5,0.45),(0.35,0.55),(0.15,0.55),(0.0,0.4),(0.0,0.15),
           (0.15,0.0),(0.35,0.0),(0.5,0.1)]],
    'o': [[(0.15,0.0),(0.35,0.0),(0.5,0.15),(0.5,0.4),(0.35,0.55),
           (0.15,0.55),(0.0,0.4),(0.0,0.15),(0.15,0.0)]],
    'm': [[(0.0,0.55),(0.0,0.0)],
          [(0.0,0.4),(0.08,0.55),(0.17,0.55),(0.25,0.4),(0.25,0.0)],
          [(0.25,0.4),(0.33,0.55),(0.42,0.55),(0.5,0.4),(0.5,0.0)]],
}


class TextWriter:
    """Tracks head position in steps; converts target points into
    axis-aligned unit moves (Bresenham-style) via the plotter."""

    def __init__(self, plotter, flip_x=False, flip_y=False, dry=False):
        self.pl = plotter
        self.x = 0
        self.y = 0
        self.fx = -1 if flip_x else 1
        self.fy = -1 if flip_y else 1
        self.dry = dry

    def _burst(self, dir_key, n, laser):
        if n <= 0:
            return
        if not self.dry:
            self.pl.move(DIRS[dir_key], n, laser=laser)

    def goto(self, tx, ty, laser):
        """Move to (tx,ty) steps along a straight-ish staircase line."""
        dx, dy = tx - self.x, ty - self.y
        steps = max(abs(dx), abs(dy))
        if steps == 0:
            return
        px, py = self.x, self.y
        for i in range(1, steps + 1):
            nx = self.x + round(dx * i / steps)
            ny = self.y + round(dy * i / steps)
            if nx != px:
                self._burst('r' if (nx - px) * self.fx > 0 else 'l',
                            abs(nx - px), laser)
            if ny != py:
                self._burst('u' if (ny - py) * self.fy > 0 else 'd',
                            abs(ny - py), laser)
            px, py = nx, ny
        self.x, self.y = tx, ty

    def write(self, text, scale_steps):
        """scale_steps: steps per font unit. Origin = current head pos."""
        cx = 0.0
        for ch in text:
            strokes = GLYPHS.get(ch)
            if strokes is None:
                raise SystemExit(f"no glyph for {ch!r} — add it to GLYPHS")
            for stroke in strokes:
                x0, y0 = stroke[0]
                self.goto(round((cx + x0) * scale_steps),
                          round(y0 * scale_steps), laser=False)
                for (px, py) in stroke[1:]:
                    self.goto(round((cx + px) * scale_steps),
                              round(py * scale_steps), laser=True)
            cx += ADV
        self.goto(0, 0, laser=False)   # park back at origin


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--text", required=True)
    ap.add_argument("--length-mm", type=float, required=True)
    ap.add_argument("--steps-per-mm", type=float, default=6.75)
    ap.add_argument("--feed-ms", type=int, default=20)
    ap.add_argument("--flip-x", action="store_true")
    ap.add_argument("--flip-y", action="store_true")
    ap.add_argument("--home", action=argparse.BooleanOptionalAction, default=True,
                    help="stall-home to the top-left corner, then drop by the "
                         "cap height so the text lands at an absolute position "
                         "(--no-home: start at the current head position)")
    ap.add_argument("--home-margin", type=int, default=8,
                    help="steps to back off the corner after homing")
    ap.add_argument("--dry-run", action="store_true",
                    help="compute and print extents, move nothing")
    a = ap.parse_args()

    units = len(a.text) * ADV
    scale = a.length_mm * a.steps_per_mm / units      # steps per font unit
    w = round(units * scale)
    h = round(1.0 * scale)
    print(f"text {a.text!r}: {a.length_mm} mm = {w} steps wide, "
          f"cap height {h} steps ({h / a.steps_per_mm:.1f} mm), "
          f"feed {a.feed_ms} ms/step")
    if a.dry_run:
        return

    pl = Plotter(a.port)
    try:
        if a.home:
            print("homing (stall into top-left corner)")
            pl.home(a.home_margin)
            pl.speed(2)
            pl.move(DIRS["d"], h + 2, laser=False, step_ms=2)  # room for caps
        pl.speed(a.feed_ms)
        tw = TextWriter(pl, flip_x=a.flip_x, flip_y=a.flip_y)
        tw.write(a.text, scale)
        print("done")
    finally:
        pl.reset()

if __name__ == "__main__":
    main()
