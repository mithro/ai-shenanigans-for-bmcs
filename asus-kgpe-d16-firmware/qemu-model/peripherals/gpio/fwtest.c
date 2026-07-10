/* GPIO firmware test — AST2050 @ 0x1E780000.
 *
 * Banks A-H (max 64 pins), register window 0x00-0x58 (datasheet §23; see
 * DATASHEET-GPIO.md). 0x00 data (banks A-D), 0x04 direction (0=in,1=out), 0x08
 * int-enable, 0x0C/0x10/0x14 sensitivity, 0x18 int-status (W1C); 0x20.. repeats
 * for E-H. Read = (latch & dir) | (input & ~dir). GPIO IRQ = VIC source 20.
 *
 * This checks reset state + that an output pin latches: set a bank to output,
 * write a pattern, read it back. (For OpenBMC this is the power-control / LED /
 * presence path.) Apache-2.0.
 */
#include "harness.h"
#include "ast2050.h"

#define GPIO_DATA_AD 0x00
#define GPIO_DIR_AD  0x04
#define GPIO_INTEN   0x08
#define GPIO_DATA_EH 0x20
#define GPIO_DIR_EH  0x24

const char fwtest_name[] = "gpio";

void fwtest_run(void)
{
    /* --- reset state (datasheet: all 0) --- */
    u32 dir0 = fwt_reg("dir_ad.reset", GPIO_BASE + GPIO_DIR_AD);
    u32 ien  = fwt_reg("inten.reset",  GPIO_BASE + GPIO_INTEN);
    fwt_reg("data_ad.reset", GPIO_BASE + GPIO_DATA_AD);
    fwt_check("dir_ad.reset",  dir0, 0);
    fwt_check("inten.reset",   ien, 0);

    /* --- direction register is RW --- */
    writel(GPIO_BASE + GPIO_DIR_AD, 0xFFFFFFFFu);   /* banks A-D all output */
    u32 dmask = fwt_reg("dir_ad.mask", GPIO_BASE + GPIO_DIR_AD);
    fwt_kv("dir_ad.wr_all1s", dmask);   /* which bits are implemented pins */

    /* --- an output pin latches the written value (read-back on outputs) --- */
    writel(GPIO_BASE + GPIO_DATA_AD, 0xA5A5A5A5u);
    u32 rb = fwt_reg("data_ad.latch", GPIO_BASE + GPIO_DATA_AD);
    /* the read-back (masked to output pins) must equal the pattern on those bits */
    fwt_check("data_ad.output_latch", rb & dmask, 0xA5A5A5A5u & dmask);

    /* --- banks E-H direction is RW too (G3 has E-H) --- */
    writel(GPIO_BASE + GPIO_DIR_EH, 0xFFFFFFFFu);
    fwt_reg("dir_eh.mask", GPIO_BASE + GPIO_DIR_EH);
    writel(GPIO_BASE + GPIO_DATA_EH, 0x5A5A5A5Au);
    u32 eh_dir = readl(GPIO_BASE + GPIO_DIR_EH);
    fwt_check("data_eh.output_latch",
              readl(GPIO_BASE + GPIO_DATA_EH) & eh_dir, 0x5A5A5A5Au & eh_dir);
}
