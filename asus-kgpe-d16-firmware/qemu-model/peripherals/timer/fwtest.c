/* Timer (FTTMR010) firmware test — AST2050 @ 0x1E782000.
 *
 * Three PCLK down-counters. Datasheet (see DATASHEET-TIMER.md): all registers
 * 0x00-0x30 reset to 0; control TMC30 has 4 bits/timer (timer1 = [2:0]):
 * [0]=enable, [1]=clock-select (0=PCLK, 1=1 MHz), [2]=overflow-IRQ-enable.
 * G3 has only 3 timers and a single control register (no 0x34+ block).
 *
 * This checks the reset state, that timer1 counts down when enabled, AND the
 * absolute PCLK rate (#142, was task #55): timer1 runs off PCLK while timer2
 * runs off the 1 MHz external clock, so their count deltas over the same virtual
 * interval give the exact ratio PCLK/1MHz, independent of spin length. The G3
 * H-PLL strap-fallback = 166 MHz and CLK_SEL=0xF3F40000 → PCLK_DIV=7, so
 * PCLK = 166/(7+1)/2 = 10.375 MHz → ratio ≈ 10. The old mis-decoded 25 MHz-CLKIN
 * / [9:8] H-PLL (~375 MHz) would give ~23, so this assertion catches a regression
 * to the wrong clkin/calc_hpll. Apache-2.0.
 */
#include "harness.h"
#include "ast2050.h"

const char fwtest_name[] = "timer";

#define T1_COUNT  0x00
#define T1_RELOAD 0x04
#define T1_MATCH1 0x08
#define T2_COUNT  0x10
#define T2_RELOAD 0x14
#define T2_MATCH1 0x18
#define TCTRL     0x30

static void spin(void)
{
    volatile u32 i;
    for (i = 0; i < 3000000u; i++) {
    }
}

void fwtest_run(void)
{
    /* --- reset state (datasheet: all 0) --- */
    u32 ctrl = fwt_reg("ctrl",   TIMER_BASE + TCTRL);
    u32 cnt0 = fwt_reg("count0", TIMER_BASE + T1_COUNT);
    fwt_check("ctrl.reset",  ctrl, 0);
    fwt_check("count.reset", cnt0, 0);

    /* --- functional: load reload, enable timer1 from PCLK, confirm down-count --- */
    writel(TIMER_BASE + T1_MATCH1, 0);                 /* no match IRQ           */
    writel(TIMER_BASE + T1_RELOAD, 0xFFFFFFFFu);
    writel(TIMER_BASE + TCTRL, 0x1);                   /* timer1 enable, PCLK    */
    spin();
    u32 a = fwt_reg("count.a", TIMER_BASE + T1_COUNT);
    spin();
    u32 b = fwt_reg("count.b", TIMER_BASE + T1_COUNT);
    fwt_kv("count.delta", a - b);

    /* it must have loaded from reload and be decrementing */
    fwt_check("loaded",      (a != 0 && a <= 0xFFFFFFFFu) ? 1u : 0u, 1u);
    fwt_check("counts_down", (b < a) ? 1u : 0u, 1u);

    /*
     * --- absolute rate (#142): PCLK-timer vs 1 MHz-external-timer ratio ---
     * timer2 = 1 MHz external clock reference; timer1 = PCLK. delta1/delta2 is
     * PCLK/1MHz regardless of the spin length. Expect ~10 (166 MHz H-PLL /8 /2 =
     * 10.375 MHz); the old wrong ~375 MHz H-PLL would give ~23.
     */
    writel(TIMER_BASE + T2_MATCH1, 0);
    writel(TIMER_BASE + T2_RELOAD, 0xFFFFFFFFu);
    writel(TIMER_BASE + T1_RELOAD, 0xFFFFFFFFu);
    writel(TIMER_BASE + TCTRL, 0x31);  /* timer1 PCLK-en | timer2 en+ext(1MHz) */
    u32 t1a = fwt_reg("rate.t1a", TIMER_BASE + T1_COUNT);
    u32 t2a = fwt_reg("rate.t2a", TIMER_BASE + T2_COUNT);
    spin();
    u32 t1b = fwt_reg("rate.t1b", TIMER_BASE + T1_COUNT);
    u32 t2b = fwt_reg("rate.t2b", TIMER_BASE + T2_COUNT);
    /*
     * Log the raw down-count deltas (no division here — the bare-metal fwtest is
     * -nostdlib, so __aeabi_uidiv is unavailable). test_timer.py asserts the
     * ratio d1/d2 == PCLK/1MHz ≈ 10 (the correct 166 MHz H-PLL), not ~23 (wrong).
     */
    fwt_kv("rate.d1_pclk", t1a - t1b);
    fwt_kv("rate.d2_1mhz", t2a - t2b);
}
