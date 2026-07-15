# tools

All scripts target `/dev/ttyUSB0`. Need `pyserial`; `dump_serial.py` also needs
`dnfile` + `dncil`; bootloader work needs `stcgal`.

```sh
python3 -m venv venv && ./venv/bin/pip install pyserial dnfile dncil stcgal
```

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
