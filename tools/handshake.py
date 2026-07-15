#!/usr/bin/env python3
"""NEJE new-protocol handshake, reconstructed from decompiled official V4.2 app.
Frame = FF <cmd> <arg1> <arg2>. Connect cmd = FF 09 00 00.
Device replies with FF-framed packets; code 0x65='e' is heartbeat/identify."""
import serial, time

def frame(cmd, a=0, b=0):
    return bytes([0xFF, cmd, a, b])

def parse(buf):
    out = []
    i = 0
    while i < len(buf):
        if buf[i] != 0xFF:
            i += 1; continue
        if i + 1 >= len(buf): break
        code = buf[i+1]
        n = 8 if code >= 100 else 4
        if i + n > len(buf): break
        out.append(buf[i:i+n]); i += n
    return out

ser = serial.Serial()
ser.port = "/dev/ttyUSB0"; ser.baudrate = 57600; ser.timeout = 0.3
ser.dtr = True   # official app: serialPort1.DtrEnable = true
ser.open()
time.sleep(0.5)
ser.reset_input_buffer()

print("TX connect: FF 09 00 00")
ser.write(frame(0x09)); ser.flush()

buf = b""
end = time.time() + 3
while time.time() < end:
    if ser.in_waiting:
        buf += ser.read(ser.in_waiting); end = time.time() + 0.5
    time.sleep(0.03)

print(f"RX raw: {buf.hex(' ') if buf else '(nothing)'}")
for f in parse(buf):
    print(f"  frame: {f.hex(' ')}  code=0x{f[1]:02x}({f[1]})")

# If nothing, retry a few times (device may need a beat)
if not buf:
    for _ in range(5):
        ser.write(frame(0x09)); ser.flush()
        time.sleep(0.4)
        if ser.in_waiting:
            r = ser.read(ser.in_waiting)
            print(f"retry RX: {r.hex(' ')}")
            buf += r
ser.close()
print("HANDSHAKE " + ("SUCCESS" if buf else "NO RESPONSE"))
