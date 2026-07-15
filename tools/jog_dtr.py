#!/usr/bin/env python3
"""Jog test with DTR asserted (as official app does). New-protocol frames.
Laser stays OFF - these are motion-only commands."""
import serial, time

ser = serial.Serial()
ser.port="/dev/ttyUSB0"; ser.baudrate=57600; ser.timeout=0.1
ser.dtr=True; ser.rts=False
ser.open()
time.sleep(0.4); ser.reset_input_buffer()

def send(frame, label, n=1, gap=0.12):
    for _ in range(n):
        ser.write(frame); ser.flush(); time.sleep(gap)

# connect/identify first
send(bytes([0xFF,0x09,0x00,0x00]), "connect")
time.sleep(0.4)
rx = ser.read(ser.in_waiting) if ser.in_waiting else b""
print(f"connect RX: {rx.hex(' ') if rx else '-'}", flush=True)

print("JOG UP x40 (FF 03 01 00)", flush=True)
send(bytes([0xFF,0x03,0x01,0x00]), "up", 40)
time.sleep(1.5)
print("JOG DOWN x40 (FF 03 02 00)", flush=True)
send(bytes([0xFF,0x03,0x02,0x00]), "down", 40)
time.sleep(0.3)
rx2 = ser.read(ser.in_waiting) if ser.in_waiting else b""
print(f"after-jog RX: {rx2.hex(' ') if rx2 else '-'}")
ser.close()
