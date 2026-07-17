SDCC    := ../tools/sdcc/bin/sdcc
PACKIHX := ../tools/sdcc/bin/packihx
STCGAL  := ../tools/venv/bin/stcgal
PORT    := /dev/ttyUSB0

CFLAGS  := -mmcs51 --model-small --iram-size 256 --xram-size 4096 --code-size 16384

all: build/firmware.hex

build/firmware.hex: main.c stc8.h
	mkdir -p build
	$(SDCC) $(CFLAGS) -o build/main.ihx main.c
	$(PACKIHX) build/main.ihx > $@

# Trims the internal RC oscillator to 24 MHz (firmware timing depends on it).
# Requires a power-cycle of the engraver's supply when prompted.
flash: build/firmware.hex
	$(STCGAL) -P stc8 -p $(PORT) -t 24000 build/firmware.hex

clean:
	rm -rf build

.PHONY: all flash clean
