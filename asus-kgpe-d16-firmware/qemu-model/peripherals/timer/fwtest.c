/* Timer (FTTMR010) firmware test — AST2050 @ 0x1E782000.
 *
 * Three PCLK down-counters. Datasheet (see DATASHEET-TIMER.md): all registers
 * 0x00-0x30 reset to 0; control TMC30 has 4 bits/timer (timer1 = [2:0]):
 * [0]=enable, [1]=clock-select (0=PCLK, 1=1 MHz), [2]=overflow-IRQ-enable.
 * G3 has only 3 timers and a single control register (no 0x34+ block).
 *
 * This checks the reset state and that timer1 actually counts down when enabled
 * (the clockevent/clocksource path the culvert session cared about). The exact
 * PCLK tick RATE (66 MHz) depends on the SCU H-PLL post-divider, deferred to the
 * SCU clock-rate work (task #55) — here we only assert the counter moves.
 * Apache-2.0.
 */
#include "harness.h"
#include "ast2050.h"

const char fwtest_name[] = "timer";

#define T1_COUNT  0x00
#define T1_RELOAD 0x04
#define T1_MATCH1 0x08
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
}
