# tools

All scripts target `/dev/ttyUSB0`. Need `pyserial`; `etch_image.py` also needs
`Pillow`; `dump_serial.py` needs `dnfile` + `dncil`; bootloader work needs
`stcgal`.

```sh
python3 -m venv venv && ./venv/bin/pip install pyserial pillow dnfile dncil stcgal
```

## Driving the machine (custom firmware)

- **plotter.py** — host driver for the replacement firmware. Subcommands:
  `home` (stall-home to the top-left corner — no endstops, it grinds
  harmlessly into the frame and backs off a margin), `move`, `pulse`,
  `mask`, `speed`, `circle`. Every command is acked; exit always sends
  reset (laser off, motors released).
- **write_text.py** — single-stroke vector text. Homes by default, then
  drops down by the cap height. Extend the `GLYPHS` table as needed.
  ```sh
  python3 write_text.py --text "Chr1x.com" --length-mm 25 --feed-ms 20
  ```
- **etch_image.py** — bitmap engraving, two modes: `raster` (scanline rows,
  for filled art/photos) and `outline` (Zhang-Suen thinning to centerlines,
  each stroke traced continuously — use this for line art). Homes by
  default so reruns land identically; `--dry-run` prints an ASCII preview.
  ```sh
  python3 etch_image.py --image logo.png --width-mm 30 --mode outline --dry-run
  ```

Calibration on this unit: 6.75 steps/mm; paper marks at 20 ms/step,
cardboard cuts at 50 ms/step × ~10 passes per 1.5 mm.

## Probing / reverse-engineering (kept for reference)

- **handshake.py** — open 57600/DTR-high, send `FF 09 00 00`, parse replies.
- **jog_dtr.py** — connect then jog the head (laser-off motion only).
- **listen_connect.py** — hold DTR, poll identify @2Hz, log all RX. Run it across
  a DC power-cycle to catch any boot-time identify frame.
- **dump_serial.py** — disassemble the vendor `NEJE_V4.2_EN.exe` IL and print every
  method that touches `SerialPort`. Put the exe next to the script first:
  `curl -O http://www.neje.club/download/NEJE_V4.2_EN.exe`
  (`monodis` segfaults on this binary — use this instead.)

Inspect the STC8 bootloader (safe, read-only), power-cycle the DC jack when asked:

```sh
./venv/bin/stcgal -P auto -p /dev/ttyUSB0
```
