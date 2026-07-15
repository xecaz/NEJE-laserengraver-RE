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

## Current status / open question

**The unit answers nothing.** No reply to `FF 09 00 00` (or any command) at any
baud, DTR high or low; no physical motion on jog; solid power LED, head stays
put. Yet `stcgal` reaches the STC8 ISP bootloader after a power-cycle — so the
device→PC serial path physically works. The running application firmware is
either unresponsive/half-flashed or faulted. This matches the widely-reported
"NEJE verify fails" symptom where NEJE changed protocol in 2017 and newer apps
can't verify certain boards. Next avenues:
1. Confirm the app firmware actually runs (scope the MCU TX pin on power-up, or
   dump code flash via `stcgal` read — non-destructive).
2. Try the "NEJE Laser Engraver Extended" legacy path end-to-end.
3. Verify DC power rail actually reaches the motor drivers (TC118S) under load.

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
