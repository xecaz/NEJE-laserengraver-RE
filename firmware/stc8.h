/* Minimal SFR definitions for STC8A4K16S2A12 (SDCC mcs51).
 * Only what this firmware touches. Addresses from the STC8A series manual. */
#ifndef STC8_H
#define STC8_H

__sfr __at(0x80) P0;
__sfr __at(0x87) PCON;
__sfr __at(0x88) TCON;
__sfr __at(0x89) TMOD;
__sfr __at(0x8A) TL0;
__sfr __at(0x8B) TL1;
__sfr __at(0x8C) TH0;
__sfr __at(0x8D) TH1;
__sfr __at(0x8E) AUXR;
__sfr __at(0x90) P1;
__sfr __at(0x91) P1M1;
__sfr __at(0x92) P1M0;
__sfr __at(0x93) P0M1;
__sfr __at(0x94) P0M0;
__sfr __at(0x95) P2M1;
__sfr __at(0x96) P2M0;
__sfr __at(0x98) SCON;
__sfr __at(0x99) SBUF;
__sfr __at(0xA0) P2;
__sfr __at(0xA8) IE;
__sfr __at(0xB0) P3;
__sfr __at(0xB1) P3M1;
__sfr __at(0xB2) P3M0;
__sfr __at(0xB3) P4M1;
__sfr __at(0xB4) P4M0;
__sfr __at(0xC0) P4;
__sfr __at(0xC1) WDT_CONTR;
__sfr __at(0xC8) P5;
__sfr __at(0xC9) P5M1;
__sfr __at(0xCA) P5M0;

/* TCON bits */
__sbit __at(0x8C) TR0;
__sbit __at(0x8D) TF0;
__sbit __at(0x8E) TR1;
__sbit __at(0x8F) TF1;

/* SCON bits */
__sbit __at(0x98) RI;
__sbit __at(0x99) TI;

/* Board signals (nets per vrbadev/NEJE-KZ-Controller-Board schematic) */
__sbit __at(0x90 + 2) LASER_S;  /* P1.2  LASER-ST connector sense      */
__sbit __at(0x90 + 3) SW_LED;   /* P1.3  LED-SW connector              */
__sbit __at(0x90 + 6) ENDC;     /* P1.6  TX4223 boost enable (laser V) */
__sbit __at(0x90 + 7) LASER_T;  /* P1.7  laser TTL                     */
__sbit __at(0xA0 + 0) LASER_G;  /* P2.0  laser power N-FET gate        */
__sbit __at(0xB0 + 4) DTR_N;    /* P3.4  CH340 DTR#                    */
__sbit __at(0xC0 + 0) LED1;     /* P4.0  status LED (high = on)        */
__sbit __at(0xC0 + 4) FAN_G;    /* P4.4  fan N-FET gate                */
__sbit __at(0xC8 + 5) BTN;      /* P5.5  push button (low = pressed)   */

#endif
