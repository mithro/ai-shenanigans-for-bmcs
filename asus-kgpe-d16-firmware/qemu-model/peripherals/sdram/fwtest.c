/* SDRAM controller firmware test — AST2050 (DDR2) @ 0x1E6E0000.
 *
 * The AST2050 SDRAM controller is DDR2 (not the AST2400/G4 DDR3). Datasheet §17
 * (pp.183-203; see DATASHEET-SDRAM.md / DOC.md): MCR00 is a protection lock-latch
 * (unlock key 0xFC600309; reads 0=locked / 1=unlocked, resets locked); MCR04
 * config resets to 0 and is written by firmware (no SPD/strap/probe DRAM sizing);
 * MCR100 reads 0x000000A8. The stock QEMU aspeed_sdmc models DDR3 and *synthesises*
 * MCR04 from the machine RAM size, so several checks below FAIL and document the
 * gaps a DDR2 model closes. Apache-2.0.
 */
#include "harness.h"
#include "ast2050.h"

const char fwtest_name[] = "sdram";

#define SDMC_UNLOCK   0xFC600309u
/* Raptor 128 MB DDR2 geometry: 8-bank / 128 MB cap / 10-col (platform.S). */
#define G3_CONF_128M  0x00000D89u

void fwtest_run(void)
{
    /* --- reset-state observations --- */
    u32 prot  = fwt_reg("protect",  SDMC_BASE + 0x00);
    u32 conf  = fwt_reg("config",   SDMC_BASE + 0x04);
    u32 refr  = fwt_reg("refresh",  SDMC_BASE + 0x0C);
    fwt_reg("mode2c",  SDMC_BASE + 0x2C);   /* DDR-type / mode-set (X reset)  */
    u32 m100  = fwt_reg("compat100", SDMC_BASE + 0x100);  /* AST2000 shadow   */

    /* decode current config per the G3 DDR2 layout (§17): */
    fwt_kv("conf.cap",   (conf >> 2) & 0x3);   /* 00<=32M 01=64M 10=128M 11=256M */
    fwt_kv("conf.width", (conf >> 8) & 0x3);   /* 01 = 16-bit                    */
    fwt_kv("conf.bank",  (conf >> 11) & 0x1);  /* 0=4-bank 1=8-bank              */

    /* --- faithfulness checks (datasheet §17 reset values) --- */
    fwt_check("protect.reset", prot, 0);       /* MCR00 resets locked -> reads 0 */
    fwt_check("config.reset",  conf, 0);       /* MCR04 Init=0; firmware writes it */
    fwt_check("refresh.reset", refr, 0);       /* MCR0C Init=0 (refresh disabled) */
    fwt_check("compat100",     m100, 0x000000A8);

    /* --- behavioural: unlock (0xFC600309 -> MCR00 reads 1) + program config --- */
    writel(SDMC_BASE + 0x00, SDMC_UNLOCK);
    fwt_check("unlock", readl(SDMC_BASE + 0x00), 1);
    writel(SDMC_BASE + 0x04, G3_CONF_128M);
    fwt_check("config.rw", readl(SDMC_BASE + 0x04) & 0xFFF, G3_CONF_128M);
}
