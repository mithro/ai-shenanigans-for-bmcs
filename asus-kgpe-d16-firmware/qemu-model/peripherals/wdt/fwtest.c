/* Watchdog Timer (WDT) firmware test — AST2050 @ 0x1E785000.
 *
 * Datasheet (see ../timer/DATASHEET-TIMER.md): WDT00 counter/status, WDT04
 * reload (Init 0x03EF1480 = 66,000,000 = 1s @66MHz PCLK), WDT08 restart (write
 * the magic 0x4755 to reload the counter), WDT0C control ([0]enable,
 * [1]reset-system, [2]interrupt, [4]clock 0=PCLK/1=1MHz; reset 0). WDT18 reset
 * 0xFF. The absolute timeout RATE depends on PCLK (SCU post-divider, task #55);
 * QEMU currently hardcodes 24 MHz -- a rate issue, not a register one.
 *
 * SAFETY: this test must NOT set the reset-system bit (WDT0C[1]) or the machine
 * would reset mid-test and the [FWT] transcript would never halt. It only checks
 * reset values + that the restart magic reloads the counter. Apache-2.0.
 */
#include "harness.h"
#include "ast2050.h"

const char fwtest_name[] = "wdt";

#define WDT_STATUS  0x00
#define WDT_RELOAD  0x04
#define WDT_RESTART 0x08
#define WDT_CONTROL 0x0C
#define WDT_MAGIC   0x4755u

void fwtest_run(void)
{
    /* --- reset state --- */
    u32 rel  = fwt_reg("reload",  WDT_BASE + WDT_RELOAD);
    u32 ctrl = fwt_reg("control", WDT_BASE + WDT_CONTROL);
    fwt_reg("status", WDT_BASE + WDT_STATUS);

    fwt_check("control.reset", ctrl, 0);          /* disabled at reset      */
    fwt_check("reload.reset",  rel, 0x03EF1480);  /* 1s @66MHz (datasheet)  */

    /* --- functional (SAFE: never enable reset-system): set a new reload, then
     *     write the restart magic and confirm the counter reloads from it. --- */
    writel(WDT_BASE + WDT_RELOAD, 0x00100000u);
    writel(WDT_BASE + WDT_RESTART, WDT_MAGIC);
    u32 cnt = fwt_reg("status.reloaded", WDT_BASE + WDT_STATUS);
    /* counter should now be at/near the new reload (down-counter), not the old
     * 0x03EF1480 and not 0. */
    fwt_check("restart.reloads",
              (cnt != 0 && cnt <= 0x00100000u) ? 1u : 0u, 1u);
}
