# NEJE serial protocol (0xFF-framed "new" / EzGraver v3)

Recovered by decompiling the official Windows app `NEJE_V4.2_EN.exe` (32-bit
Mono/.NET). Source of truth: methods `Form_Main.Send_CMD`, `Form_Main.decode`,
`Form_Main.<...>g__GetNextCmd`, and `Form_SendingPicture.InitializeComponent`.

## Link settings

- Baud **57600**, **8N1**, `DtrEnable = true` (RTS left low).
- Image payload phase switches the port to **115200** (see `FF 06 …`).
- RX/TX buffers set to 512000 bytes by the app.

## Framing

**PC → device** — fixed 4-byte frame:

```
FF <cmd> <arg1> <arg2>
```

A 7-byte variant `FF <a> <b> <c> <d> <e> <f>` is used for coordinate pairs
(box/preview corners), values sent as decimal-hundreds + remainder.

**Device → PC** — variable frame, first byte `0xFF`, dispatched on `byte[1]`:

```
byte[1] < 100  -> 4-byte frame   FF <code> <b2> <b3>
byte[1] >= 100 -> 8-byte frame   FF <code> <b2..b7>
```

## Commands (PC → device)

`Send_CMD(cmd, a, b)` emits `FF cmd a b`.

| Frame          | Meaning                                             |
|----------------|-----------------------------------------------------|
| `FF 09 00 00`  | Connect / identify (sent right after port open)     |
| `FF 01 01 00`  | Start engraving from memory                         |
| `FF 01 02 00`  | Pause engraving                                     |
| `FF 02 01 00`  | Move to center                                      |
| `FF 02 02 00`  | Preview / draw bounding box                         |
| `FF 03 01 00`  | Jog up                                              |
| `FF 03 02 00`  | Jog down                                            |
| `FF 03 03 00`  | Jog left                                            |
| `FF 03 04 00`  | Jog right                                           |
| `FF 04 01 00`  | Reset                                               |
| `FF 05 <t> 00` | Set burn time (`t` = 0x01..0xF0)                    |
| `FF 06 01 01`  | Begin image upload (then switch to 115200 and stream a **headerless** 1-bpp 512×512 BMP body) |
| `FF 0E 00 04`  | Sent after a "DK-Master" (V3.0) machine is detected |

Legacy single-byte protocol (a *different*, older NEJE — not this frame format):
`F1` start, `F2` pause, `F3` home, `F5..F8` jog, `F9` reset, `FE`×8 erase+upload.

## Responses (device → PC), dispatched on `byte[1]`

| `byte[1]` | Meaning |
|-----------|---------|
| `0x00` | Heartbeat |
| `0x02` | **Identify.** Sub-type in `byte[2],byte[3]`: `11,2`=production ("量产版") V2.0 · `13,2`=lite ("精简版") V2.0 · `1,10`=Bluetooth V2.0 · `14,*`=NEJE-DK-Master V3.0. Sets `CONNECTED`/`MACHINE_MODE` → app shows "Verify OK". |
| `0x03` | Report X position: `x = b2*100 + b3` |
| `0x04` | Report Y position: `y = b2*100 + b3` (appended to point buffer) |
| `0x05` | "Quit this software when operating the mobile APP" |
| `0x06`–`0x09` | Engrave progress / completion count, low-battery notice, battery level (0/25/50/75/100 %) |
| `0x0A` | Burning time report (`… mS`) |
| `0x0B` | Verify OK, or flash/command buffer-overflow errors (`CODE:12.1/12.2`) |
| `0x0C` | Emergency stop |
| `0x0D` | Laser power `%` |
| `0x0E` | Laser temperature `℃` (also a heartbeat) |
| `0x0F` | Charging current `mA` |
| `0x10` | "Laser initialization error, unrecognized laser type" |
| `0x65` ('e') | Heartbeat/verify token (also referenced by `sthysel/nejemojo`) |

> Note: not every tiny DK-8-KZ exposes the battery/temperature/charging codes —
> those belong to later battery-equipped NEJE units that share this framing.

## Minimal connect sequence

1. Open `/dev/ttyUSB0` at 57600 8N1, assert DTR.
2. Send `FF 09 00 00`.
3. Read frames; on `FF 02 <11|13|1|14> …` the machine is identified and the
   session is "verified". Absence of this reply is the well-known
   NEJE "Verify Failed" condition.
