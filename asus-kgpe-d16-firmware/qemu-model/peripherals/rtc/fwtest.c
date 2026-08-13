/* RTC firmware test — AST2050 @ 0x1E781000.
 *
 * Counter-style RTC (datasheet §24; see DATASHEET-RTC.md): RTC00 counter status
 * (R: [5:0]sec [11:6]min [16:12]hour [31:17]day), RTC08 reload, RTC0C control
 * ([0]enable), RTC10 restart (write 0x5A to load the counter from reload), RTC14
 * reset (write 0x99). All reset values are undefined (volatile, no battery).
 * SecCnt ticks at 1 Hz off CLK32K. This is NOT the AST2400 BCD/CMOS RTC.
 *
 * Tests the load path (reload -> restart 0x5A -> counter) and control RW.
 * Apache-2.0.
 */
#include "harness.h"
#include "ast2050.h"

#define RTC_COUNTER 0x00
#define RTC_RELOAD  0x08
#define RTC_CONTROL 0x0C
#define RTC_RESTART 0x10
#define RTC_MAGIC   0x5Au

const char fwtest_name[] = "rtc";

void fwtest_run(void)
{
    fwt_reg("counter.initial", RTC_BASE + RTC_COUNTER);
    fwt_reg("control.initial", RTC_BASE + RTC_CONTROL);

    /* load the counter to 12:30:45 via reload + restart magic */
    u32 want = (12u << 12) | (30u << 6) | 45u;
    writel(RTC_BASE + RTC_RELOAD, want);
    writel(RTC_BASE + RTC_RESTART, RTC_MAGIC);
    u32 c = fwt_reg("counter.after_load", RTC_BASE + RTC_COUNTER);
    fwt_kv("sec",  c & 0x3fu);
    fwt_kv("min",  (c >> 6) & 0x3fu);
    fwt_kv("hour", (c >> 12) & 0x1fu);

    /* control register is RW (enable bit) */
    writel(RTC_BASE + RTC_CONTROL, 1u);
    fwt_check("control.rw", readl(RTC_BASE + RTC_CONTROL) & 1u, 1u);

    /* the loaded seconds field should read back 45 */
    fwt_check("counter.loaded_sec", c & 0x3fu, 45u);
}
