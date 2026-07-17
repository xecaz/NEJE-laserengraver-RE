/* Replacement firmware for the NEJE DK-8-KZ (STC8A4K16S2A12) controller.
 *
 * The original firmware on this unit was dead (bootloader reachable, app code
 * mute at every baud — see CLAUDE.md). This reimplements the NEJE "v3" 0xFF
 * frame protocol subset plus host-driven plotter primitives (v2).
 *
 * SAFETY MODEL: the laser is only ever energized inside an executing 0x21
 * (burn-move) or 0x22 (pulse) command; every exit path of those commands ends
 * in laser_off(). No command latches the laser. The push button aborts any
 * command, kills the laser, and replies with the NEJE e-stop code 0x0C.
 *
 * Clock: internal IRC trimmed to 24 MHz at flash time (stcgal -t 24000).
 * UART1 57600 8N1 on P3.0/P3.1, Timer1 mode0 1T as baud generator.
 *
 * Pin map (vrbadev/NEJE-KZ-Controller-Board schematic):
 *   P0.0-P0.3  X stepper: IC6 (coil A) INB/INA, IC7 (coil B) INB/INA
 *   P0.4-P0.7  Y stepper: IC9 (coil A) INB/INA, IC8 (coil B) INB/INA
 *   P2.0 LASER_G (power FET) / P1.6 ENDC (boost) / P1.7 LASER_T (TTL)
 *   TC118S truth table: INA=1,INB=0 forward; INA=0,INB=1 reverse;
 *                       0,0 coast; 1,1 brake.
 *
 * Protocol (PC->device FF <cmd> <a> <b>, device->PC FF <code> <b2> <b3>):
 *   FF 09 00 00        identify            -> FF 02 0B 02
 *   FF 03 0d 00        jog d=1..4 (U/D/L/R), laser never fires
 *   FF 04 01 00        reset: motors coast, laser off
 *   FF 21 <fl> <n>     move n steps; fl bits1..0 dir (0=Y+ 1=Y- 2=X- 3=X+),
 *                      bit2 laser on during the move; motors stay energized
 *                      after (holding) — release with FF 04
 *   FF 22 <n>  00      stationary laser pulse, n*10 ms, abortable
 *   FF 23 <ms> 00      set step period 1..50 ms (default 2)
 *   FF 25 <m>  00      laser line mask: bit0 LASER_G, bit1 ENDC, bit2 LASER_T
 *   Completed commands ack FF 00 00 00; button-aborted ones FF 0C 00 00.
 */
#include <stdint.h>
#include "stc8.h"

#define BAUD_RELOAD  (65536u - 24000000uL / 4 / 57600)  /* = 0xFF98 */
#define JOG_STEPS    160     /* steps per legacy jog command */

/* Full-step, two-phase-on. Nibble bits: [INA2 INB2 INA1 INB1] =
 * [P0.3 P0.2 P0.1 P0.0]. A+B+, A-B+, A-B-, A+B- */
static const uint8_t seq[4] = {0x0A, 0x09, 0x05, 0x06};
static uint8_t xphase, yphase;
static uint8_t step_ms = 2;
static uint8_t laser_mask = 0x05;   /* default: LASER_G + LASER_T */

/* EN_WDT | CLR_WDT | prescale 256 -> ~4.2 s timeout at 24 MHz */
#define WDT_FEED 0x37

static void delay_ms(uint16_t ms)
{
    while (ms--) {
        WDT_CONTR = WDT_FEED;
        TH0 = (65536u - 24000) >> 8;    /* 1 ms at 24 MHz, 1T */
        TL0 = (65536u - 24000) & 0xFF;
        TF0 = 0; TR0 = 1;
        while (!TF0)
            ;
        TR0 = 0; TF0 = 0;
    }
}

static void putb(uint8_t b)
{
    SBUF = b;
    while (!TI)
        ;
    TI = 0;
}

static void send4(uint8_t code, uint8_t b2, uint8_t b3)
{
    putb(0xFF); putb(code); putb(b2); putb(b3);
}

static void laser_off(void)
{
    LASER_G = 0; ENDC = 0; LASER_T = 0;
}

static void laser_on(void)
{
    FAN_G = 1;                  /* fume fan runs whenever the laser fires; */
    if (laser_mask & 1) LASER_G = 1;   /* stays on until reset (FF 04) or */
    if (laser_mask & 2) ENDC = 1;      /* explicit FF 26 00               */
    if (laser_mask & 4) LASER_T = 1;
}

static void motors_off(void)
{
    P0 = 0x00;  /* both TC118S pairs to coast */
}

static void step_x(__bit fwd)
{
    xphase = (xphase + (fwd ? 1 : 3)) & 3;
    P0 = (P0 & 0xF0) | seq[xphase];
}

static void step_y(__bit fwd)
{
    yphase = (yphase + (fwd ? 1 : 3)) & 3;
    P0 = (P0 & 0x0F) | (uint8_t)(seq[yphase] << 4);
}

static void step_dir(uint8_t dir)
{
    switch (dir) {
    case 0: step_y(1); break;   /* up    */
    case 1: step_y(0); break;   /* down  */
    case 2: step_x(0); break;   /* left  */
    case 3: step_x(1); break;   /* right */
    }
}

/* Move n steps in dir, laser optionally on for the duration.
 * Motors left energized (holding torque). Returns 1 if button-aborted. */
static __bit do_move(uint8_t dir, uint8_t n, __bit las)
{
    LED1 = 1;
    if (las)
        laser_on();
    while (n--) {
        if (!BTN) {
            laser_off();
            motors_off();
            return 1;
        }
        step_dir(dir);
        delay_ms(step_ms);
    }
    laser_off();
    return 0;
}

/* Stationary laser pulse, n*10 ms. Returns 1 if button-aborted. */
static __bit do_pulse(uint8_t n)
{
    LED1 = 1;
    laser_on();
    while (n--) {
        if (!BTN) {
            laser_off();
            return 1;
        }
        delay_ms(10);
    }
    laser_off();
    return 0;
}

static void jog(uint8_t dir)
{
    uint16_t i;

    if (dir < 1 || dir > 4)
        return;
    LED1 = 1;
    for (i = 0; i < JOG_STEPS; i++) {
        if (!BTN)
            break;
        step_dir(dir - 1);
        delay_ms(step_ms);
    }
    motors_off();
}

static void dispatch(const uint8_t *f)
{
    __bit aborted;

    switch (f[1]) {
    case 0x09:                       /* connect/identify */
        send4(0x02, 11, 2);          /* "production V2.0" identify */
        break;
    case 0x03:                       /* jog, laser never fires */
        jog(f[2]);
        send4(0x00, 0, 0);
        break;
    case 0x02:                       /* center / preview: not implemented */
    case 0x04:                       /* reset / all-off */
        laser_off();
        FAN_G = 0;
        motors_off();
        send4(0x00, 0, 0);
        break;
    case 0x05:                       /* set burn time: accepted, unused */
        send4(0x00, 0, 0);
        break;
    case 0x21:                       /* burn-move */
        aborted = do_move(f[2] & 3, f[3], (f[2] >> 2) & 1);
        send4(aborted ? 0x0C : 0x00, 0, 0);
        break;
    case 0x22:                       /* stationary pulse */
        aborted = do_pulse(f[2]);
        send4(aborted ? 0x0C : 0x00, 0, 0);
        break;
    case 0x23:                       /* set step period, 1..255 ms */
        if (f[2] >= 1)
            step_ms = f[2];
        send4(0x00, step_ms, 0);
        break;
    case 0x25:                       /* laser line mask */
        laser_mask = f[2] & 7;
        send4(0x00, laser_mask, 0);
        break;
    case 0x26:                       /* fan on/off */
        FAN_G = f[2] ? 1 : 0;
        send4(0x00, f[2] ? 1 : 0, 0);
        break;
    default:                         /* engrave/upload etc: refuse silently */
        break;
    }
}

void main(void)
{
    uint8_t buf[4];
    uint8_t n = 0;
    uint16_t cnt = 0;
    uint8_t cnt_hi = 0;

    /* Laser path safe before anything else (pins also have hw pulldowns) */
    laser_off();
    FAN_G = 0;
    motors_off();

    /* Port modes: M1,M0 per bit — 00 quasi, 01 push-pull, 10 input-only */
    P0M1 = 0x00; P0M0 = 0xFF;   /* motor drivers: push-pull        */
    P1M1 = 0x04; P1M0 = 0xC0;   /* P1.6/P1.7 push-pull low, P1.2 in */
    P2M1 = 0x02; P2M0 = 0x01;   /* P2.0 push-pull low, P2.1 input  */
    P3M1 = 0x01; P3M0 = 0x02;   /* P3.0 RX input, P3.1 TX push-pull */
    P4M1 = 0x00; P4M0 = 0x11;   /* P4.0 LED, P4.4 fan: push-pull   */
    P5M1 = 0x00; P5M0 = 0x00;   /* BTN quasi (weak pull-up)        */

    AUXR = 0xC0;                /* T0 + T1 in 1T mode              */
    TMOD = 0x00;                /* both timers 16-bit auto-reload  */
    TH1 = BAUD_RELOAD >> 8;
    TL1 = BAUD_RELOAD & 0xFF;
    TR1 = 1;
    SCON = 0x50;                /* mode 1, receive enabled         */
    TI = 0; RI = 0;
    WDT_CONTR = WDT_FEED;       /* watchdog on: hang -> reset (all off) */

    delay_ms(50);
    send4(0x02, 11, 2);         /* boot banner: identify frame     */

    for (;;) {
        WDT_CONTR = WDT_FEED;
        if (RI) {
            uint8_t c = SBUF;
            RI = 0;
            if (n == 0) {
                if (c == 0xFF)
                    buf[n++] = c;
            } else {
                buf[n++] = c;
                if (n == 4) {
                    n = 0;
                    dispatch(buf);
                }
            }
        }
        /* idle heartbeat: LED toggles every ~256k loop iterations */
        if (++cnt == 0 && ++cnt_hi == 4) {
            cnt_hi = 0;
            LED1 = !LED1;
        }
    }
}
