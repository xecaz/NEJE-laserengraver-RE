# NEJE-laserengraver-RE

Reverse-engineering a cheap NEJE (DK-8-KZ class) USB laser engraver and
bringing it back to life with custom firmware, driven entirely from Linux.

The unit arrived with dead application firmware (bootloader alive, app code
mute). Since STC8 flash can't be read back, the original firmware was erased
and replaced with our own — see `firmware/`. First successful cut: an 8 mm
circle through 3 mm cardboard.

![the machine](IMG_20260717_165333729.jpg)

## What's here

- **`PROTOCOL.md`** — the NEJE "v3" serial protocol (57600 8N1, DTR asserted,
  `FF <cmd> <a> <b>` frames), recovered by decompiling the vendor's .NET app.
- **`firmware/`** — replacement firmware for the STC8A4K16S2A12 MCU (SDCC).
  Implements a v3 subset (identify, jog, reset) plus safe host-driven plotter
  primitives: burn-moves, stationary pulses, step period, laser line mask,
  fan. The laser can only be energized *inside* an executing move/pulse
  command; the board button is an emergency stop; a hardware watchdog kills
  all outputs on hang. `cd firmware && make && make flash`.
- **`tools/`** — host-side Python: the `plotter.py` driver, single-stroke
  text engraving (`write_text.py`), bitmap etching in raster or
  centerline-outline mode (`etch_image.py`), plus the probes and the
  decompiler script used for the original protocol recovery. See
  [tools/README.md](tools/README.md).

## Hardware

| Part | Detail |
|------|--------|
| USB bridge | CH340 (`1a86:7523`) → `/dev/ttyUSB0` |
| MCU | STC8A4K16S2A12 (8051), flashed with `stcgal`, IRC trimmed to 24 MHz |
| Steppers | 2× geared steppers via TC118S H-bridges, 6.75 full steps/mm |
| Travel | ~38 mm per axis, no endstops — homing stalls gently into the frame |
| Power | DC barrel jack for logic/motors/laser; USB is data only |

## Positioning

There are no endstops, so `plotter.py home` stall-homes: it drives past the
frame limit into the top-left corner (audible, harmless), then backs off a
small margin. Both engraving tools home by default, so jobs land at the same
absolute position on every run, even across power cycles.

## Safety

The firmware never latches the laser on, but treat every engraving command
as if the laser fires immediately: workpiece loaded, eyes on the machine,
board button = e-stop. The fume fan starts automatically whenever the laser
fires.

## References

- [camrein/EzGraver](https://github.com/camrein/EzGraver) — protocol v1/v2/v3.
- [vrbadev/NEJE-KZ-Controller-Board](https://github.com/vrbadev/NEJE-KZ-Controller-Board)
  — reverse-engineered schematic of this exact board.
- [alexkuklin/neje-engraver](https://github.com/alexkuklin/neje-engraver),
  [mrehqe/pyneje](https://github.com/mrehqe/pyneje) — legacy protocol notes.
