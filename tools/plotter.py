#!/usr/bin/env python3
"""Host-side driver for the custom DK-8-KZ firmware (firmware/main.c v2).

The firmware is a dumb, safe plotter: single-axis burn-moves, stationary
pulses, everything acked. The laser is only on inside an executing command
and the board button is an emergency stop (ack 0x0C).

Subcommands:
  move  --dir u|d|l|r --steps N            travel, laser OFF (calibration)
  pulse --ms N                             stationary laser pulse (10ms units)
  mask  --value N                          laser lines: 1=LASER_G 2=ENDC 4=LASER_T
  speed --ms N                             step period in ms
  circle --radius-mm R --steps-per-mm S --passes P [--feed-ms F] [--travel-ms F]
        cut a circle centered on the CURRENT head position
"""
import argparse, math, sys, time
import serial

DIRS = {"u": 0, "d": 1, "l": 2, "r": 3}   # firmware dir codes (0x21 flags)
LASER_BIT = 4

class Plotter:
    def __init__(self, port="/dev/ttyUSB0"):
        self.ser = serial.Serial(port, 57600, timeout=2)
        self.ser.dtr = True
        time.sleep(0.4)
        self.ser.reset_input_buffer()
        self.cmd(0x09, 0, 0, expect=0x02)   # identify

    def cmd(self, c, a, b, expect=0x00, timeout=None):
        """Send FF c a b, wait for the 4-byte ack. Raises on e-stop."""
        self.ser.write(bytes([0xFF, c, a, b]))
        self.ser.flush()
        old = self.ser.timeout
        if timeout is not None:
            self.ser.timeout = timeout
        try:
            r = self.ser.read(4)
        finally:
            self.ser.timeout = old
        if len(r) < 4 or r[0] != 0xFF:
            raise IOError(f"bad/missing ack for cmd {c:02x}: {r.hex(' ')}")
        if r[1] == 0x0C:
            raise KeyboardInterrupt("EMERGENCY STOP (button pressed)")
        if r[1] != expect:
            raise IOError(f"unexpected ack {r.hex(' ')} for cmd {c:02x}")
        return r

    def reset(self):
        try:
            self.cmd(0x04, 1, 0)
        except Exception:
            pass

    def speed(self, ms):
        r = self.cmd(0x23, ms, 0)
        if r[2] != ms:   # firmware echoes the period actually in effect
            raise IOError(f"firmware rejected step period {ms} ms "
                          f"(still at {r[2]} ms)")

    def mask(self, m):
        self.cmd(0x25, m, 0)

    def move(self, dir_code, steps, laser=False, step_ms=2):
        """Move up to 255 steps per frame; laser optionally on throughout."""
        while steps > 0:
            n = min(steps, 255)
            flags = dir_code | (LASER_BIT if laser else 0)
            # ack arrives after the motion: allow n*step_ms plus slack
            self.cmd(0x21, flags, n, timeout=n * step_ms / 1000 + 2)
            steps -= n

    def pulse(self, ms):
        n = max(1, min(255, ms // 10))
        self.cmd(0x22, n, 0, timeout=n * 0.01 + 2)

    def trace_circle(self, radius_steps, laser, step_ms, segments=720):
        """Walk the circle from (R,0) around, as short axis-aligned runs.
        Head must already BE at (R,0) relative to center."""
        x, y = radius_steps, 0
        for i in range(1, segments + 1):
            th = 2 * math.pi * i / segments
            tx = round(radius_steps * math.cos(th))
            ty = round(radius_steps * math.sin(th))
            dx, dy = tx - x, ty - y
            if dx:
                self.move(DIRS["r"] if dx > 0 else DIRS["l"], abs(dx),
                          laser=laser, step_ms=step_ms)
            if dy:
                self.move(DIRS["u"] if dy > 0 else DIRS["d"], abs(dy),
                          laser=laser, step_ms=step_ms)
            x, y = tx, ty


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default="/dev/ttyUSB0")
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("move");  m.add_argument("--dir", choices="udlr", required=True)
    m.add_argument("--steps", type=int, required=True)
    p = sub.add_parser("pulse"); p.add_argument("--ms", type=int, required=True)
    k = sub.add_parser("mask");  k.add_argument("--value", type=int, required=True)
    s = sub.add_parser("speed"); s.add_argument("--ms", type=int, required=True)
    c = sub.add_parser("circle")
    c.add_argument("--radius-mm", type=float, required=True)
    c.add_argument("--steps-per-mm", type=float, required=True)
    c.add_argument("--passes", type=int, default=1)
    c.add_argument("--feed-ms", type=int, default=8, help="step period while cutting")
    c.add_argument("--travel-ms", type=int, default=2, help="step period while travelling")
    a = ap.parse_args()

    pl = Plotter(a.port)
    try:
        if a.cmd == "move":
            pl.speed(2)
            pl.move(DIRS[a.dir], a.steps, laser=False)
            print(f"moved {a.steps} steps {a.dir}")
        elif a.cmd == "pulse":
            pl.pulse(a.ms)
            print(f"pulsed {a.ms} ms")
        elif a.cmd == "mask":
            pl.mask(a.value)
            print(f"laser mask set to {a.value}")
        elif a.cmd == "speed":
            pl.speed(a.ms)
            print(f"step period set to {a.ms} ms")
        elif a.cmd == "circle":
            r = round(a.radius_mm * a.steps_per_mm)
            print(f"circle: r={a.radius_mm} mm = {r} steps, {a.passes} passes, "
                  f"feed {a.feed_ms} ms/step")
            pl.speed(a.travel_ms)
            pl.move(DIRS["r"], r, laser=False)          # center -> (R,0)
            for n in range(a.passes):
                print(f"  pass {n+1}/{a.passes}")
                pl.speed(a.feed_ms)
                pl.trace_circle(r, laser=True, step_ms=a.feed_ms)
            pl.speed(a.travel_ms)
            pl.move(DIRS["l"], r, laser=False)          # back to center
            print("done")
    finally:
        pl.reset()   # laser off, motors released — always

if __name__ == "__main__":
    main()
