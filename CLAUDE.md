# CLAUDE.md

Reverse-engineering the serial control protocol of a cheap **NEJE** USB laser
engraver (DK-8-KZ class) so it can be driven from Linux without the vendor's
Windows-only software.

## Hardware under test

| Part | Detail |
|------|--------|
| USB bridge | QinHeng **CH340** (`1a86:7523`) → `/dev/ttyUSB0` |
| MCU | **STC8A4K16S2A12** (8051 core, 16 KB code flash, 48 KB EEPROM), mfg 2020-03-20, BSL v7.3.11U — read via `stcgal` |
| Frame | Tiny laser-cut acrylic, branded "NEJE", no model number. Matches the STC8-based "NEJE-KZ" board (see refs) |
| Power | Separate DC barrel jack **plus** USB data. USB alone does **not** power the logic/motors — the DC jack must be plugged in |

Access: user is in `dialout` (after `usermod`); the port also carries an ACL
granting `xecaz` rw. No `sudo` (password-gated).

## The protocol (from decompiling the official app)

The vendor app **`NEJE_V4.2_EN.exe`** is a 32-bit Mono/.NET assembly. It
decompiles cleanly — `monodis` segfaults on it, so use the Python
`dnfile` + `dncil` extractor in `tools/dump_serial.py`. Everything below came
out of `Form_Main.Send_CMD`, `Form_Main.decode`, and `InitializeComponent`.

- **Port:** 57600 baud, 8N1, **`DtrEnable = true`** (DTR asserted — easy to miss).
- **Command frame (PC→device):** 4 bytes `FF <cmd> <arg1> <arg2>`. A 7-byte
  variant exists for coordinates: `FF <a> <b> <c> <d> <e> <f>`.
- **Reply frame (device→PC):** starts with `0xFF`; length is **4 bytes if
  `byte[1] < 100`, else 8 bytes**. `decode` switches on `byte[1]`.

This is the same wire format the **EzGraver** project calls **protocol v3**
(a.k.a. NEJE "new" / V2.0 firmware). See `PROTOCOL.md` for the full command and
response tables.

Key commands: `FF 09 00 00` connect/identify · `FF 01 01 00` start engrave ·
`FF 02 01 00` center · `FF 02 02 00` preview box · `FF 03 0{1..4} 00` jog
U/D/L/R · `FF 04 01 00` reset · `FF 06 01 01` begin image upload (then raw
headerless BMP payload at **115200**).

Legacy single-byte protocol (older green-board NEJEs, documented by
`alexkuklin/neje-engraver`): `0xF1` start, `0xF2` pause, `0xF3` home,
`0xF5..0xF8` jog, `0xF9` reset, `0xFEx8` erase+upload. This unit is **not** that.

## Current status

**Running custom firmware (`firmware/`).** The original app firmware was
confirmed dead 2026-07-17: total serial silence at every baud/DTR/RTS combo,
no boot banner across a monitored power-cycle, no motion on either protocol's
jog commands — while the ISP bootloader answered fine on the same wires (also
under USB power, so the supply was never the problem). STC ISP cannot read
code flash back, so the dead firmware was unrecoverable; it was erased and
replaced with our own.

`firmware/main.c` (SDCC, ~1.1 KB) implements the v3 protocol subset — identify
`FF 09 00 00` → `FF 02 0B 02` (production V2.0), four jogs, reset — plus
host-driven plotter primitives (see the header comment for the full table):
`FF 21 <flags> <n>` burn-move (dir + optional laser), `FF 22` stationary
pulse, `FF 23` step period, `FF 25` laser line mask, `FF 26` fan. The laser
is only energized inside an executing 0x21/0x22 command — no command can
latch it on. Board button = e-stop (aborts, acks `FF 0C`). Hardware watchdog
(~4.2 s) resets the MCU on hang, which drops all outputs. Boot banner + idle
LED blink. Verified end-to-end: serial, motion, and laser cutting all work
(first successful cut 2026-07-17: 8 mm circle through 3 mm cardboard,
multi-pass).

`tools/plotter.py` is the host driver: `home`/`move`/`pulse`/`mask`/`speed`/
`circle` subcommands, ack-paced, always sends reset (laser off) on exit.
`speed()` verifies the firmware's echoed period — a rejected value once
silently ran a whole job at travel speed.
`home()` stall-homes: no endstops, so it drives 300 steps left then up —
the head grinds audibly-but-harmlessly into the top-left corner — then
backs off a margin (default 8 steps). Gives a repeatable absolute origin;
both engraving tools home by default (`--no-home` to start at the current
head position instead).
`tools/write_text.py` engraves single-stroke vector text on top of it
(unit-box glyph table `GLYPHS`, extend as needed; `--flip-x/--flip-y` for
mirrored axes — this unit needs neither: X+ = right, Y+ = up as the user
faces the machine).
`tools/etch_image.py` engraves bitmaps, two modes: `raster` (scanline rows —
for filled art/photos) and `outline` (Zhang-Suen thinning to centerlines,
each stroke traced continuously — for line art). Raster on line art comes
out as twitchy dashes; use outline. Thin antialiased strokes need
`--threshold 200`. The etch homes first by default, so the
image lands at an absolute machine position (top-left of image at the home
margin, extends right+down) and parks back at the image origin; reruns
overlay exactly even across power cycles. `--no-home` reverts to
current-head-position origin.

The board runs the latest build (auto-fan: fume fan starts with the laser,
stops on `FF 04` reset; `FF 26` manual override; watchdog; step period
1–255 ms).

**Calibration (measured):** 6.75 full steps/mm (0.148 mm/step); X travel
≈ 38 mm ≈ 256 steps, no endstops — running into the frame stalls audibly but
harmlessly. Laser fires with mask bit0 (LASER_G power FET, module on J9);
default mask 5 works. Cardboard cutting: feed 50 ms/step, ~10 passes per
1.5 mm of depth. Paper marking: 20 ms/step = clear dark line on white paper;
yellow post-its need much more dwell — 80 ms/step gives good contrast.
Always do a short test stroke first; paper chars easily.

**Safety rule:** before ANY firing command, re-confirm the workpiece is
loaded and the user is watching — users remove the piece to inspect between
runs. A user-side power cut mid-run looks exactly like an MCU hang (missing
ack, then silence); ask before diagnosing.

### Pin map (from vrbadev schematic, `eagle/NEJE-KZ-board.sch` nets)

| Pin | Net | Role |
|-----|-----|------|
| P0.0–P0.3 | MOTX INB1/INA1/INB2/INA2 | X stepper — IC6 coil A, IC7 coil B (TC118S) |
| P0.4–P0.7 | MOTY INB1/INA1/INB2/INA2 | Y stepper — IC9 coil A, IC8 coil B |
| P3.0/P3.1 | RX/TX | UART1 ↔ CH340 |
| P3.4 | DTR# | CH340 DTR |
| P1.6 | ENDC | TX4223 boost enable (laser supply), 270R pulldown |
| P2.0 | LASER_G | laser power N-FET gate, 3k3 pulldown |
| P1.7 | LASER_T | laser TTL, 10k pulldown |
| P4.0 / P4.4 | LED1 / FAN_G | status LED (high=on) / fan gate |
| P5.5 / P1.3 | BTN / SW_LED | button (low=pressed) / LED connector |

TC118S: INA=1,INB=0 fwd · 0,1 rev · 0,0 coast · 1,1 brake. Full-step nibble
sequence `0A 09 05 06`.

### Build & flash

`cd firmware && make && make flash` — SDCC lives in `tools/sdcc/` (binary
install, not committed), stcgal in `tools/venv/`. Flashing trims the IRC to
**24 MHz** (`-t 24000`); UART timing depends on it. Device must be
power-cycled when stcgal prompts.

### Next

1. Confirm/tune physical jog motion (direction mapping, step rate `STEP_MS`,
   `JOG_STEPS`).
2. Extend protocol: absolute moves, position reports (`0x03`/`0x04`).
3. Laser control — only with explicit user setup/supervision, hard-gated.

## Tools

Everything runs against `/dev/ttyUSB0`. Python `pyserial` 3.5 is available;
`stcgal` is in `tools/venv` (or `pip install stcgal`).

- `tools/handshake.py` — open at 57600/DTR-high, send `FF 09 00 00`, parse replies.
- `tools/jog_dtr.py` — connect then jog (laser-off motion only), DTR asserted.
- `tools/listen_connect.py` — hold DTR, poll identify @2Hz, log all RX (run this
  across a power-cycle to catch a boot-time identify frame).
- `tools/dump_serial.py` — disassemble the .NET exe's IL and dump every method
  that touches `SerialPort` (how the protocol above was recovered).

## Conventions & safety

- **Laser safety:** only ever send motion/identify/reset commands while probing.
  Never send `FF 01 01 00` (start engrave) or `FF 06 …` (upload+burn) unless the
  user has explicitly set up the machine and is watching it. Assume the laser can
  fire the instant an engrave command lands.
- The device only talks after a **power-cycle of the DC jack** (USB stays
  connected) — many probes need the user to pull DC power for ~2 s mid-capture.
- `monodis` segfaults on the vendor exe; use the `dnfile`/`dncil` extractor, not
  Mono's disassembler.

## References

- `camrein/EzGraver` — protocol v1/v2/v3 C++ (`EzGraverCore/ezgraver_v3.cpp` ≈ this device).
- `alexkuklin/neje-engraver`, `mrehqe/pyneje` — legacy single-byte protocol notes.
- `vrbadev/NEJE-KZ-Controller-Board` — reverse-engineered schematic; confirms STC8A4K16S2A12.
