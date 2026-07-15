#!/usr/bin/env python3
import serial, time

def parse(buf):
    out, i = [], 0
    while i < len(buf):
        if buf[i] != 0xFF: i += 1; continue
        if i+1 >= len(buf): break
        n = 8 if buf[i+1] >= 100 else 4
        if i+n > len(buf): break
        out.append(buf[i:i+n]); i += n
    return out

ser = serial.Serial()
ser.port="/dev/ttyUSB0"; ser.baudrate=57600; ser.timeout=0.1
ser.dtr=True; ser.rts=False
ser.open()
print("port open (DTR high), 25s: sending FF 09 00 00 @2Hz, logging all RX", flush=True)
buf=b""; last_tx=0; end=time.time()+25
while time.time()<end:
    now=time.time()
    if now-last_tx>0.5:
        ser.write(bytes([0xFF,0x09,0x00,0x00])); ser.flush(); last_tx=now
    if ser.in_waiting:
        chunk=ser.read(ser.in_waiting); buf+=chunk
        print(f"  [{time.strftime('%H:%M:%S')}] RX {chunk.hex(' ')}", flush=True)
    time.sleep(0.02)
ser.close()
print(f"\nTOTAL RX: {buf.hex(' ') if buf else '(nothing)'}")
for f in parse(buf):
    print(f"  frame {f.hex(' ')}  code=0x{f[1]:02x}")
