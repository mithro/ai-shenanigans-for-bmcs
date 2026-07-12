/* SDRAM controller firmware test — AST2050 (DDR2) @ 0x1E6E0000.
 *
 * The AST2050 SDRAM controller is DDR2 (not the AST2400/G4 DDR3). Datasheet §17
 * (pp.183-203; see DATASHEET-SDRAM.md / DOC.md): MCR00 is a protection lock-latch
 * (unlock key 0xFC600309; reads 0=locked / 1=unlocked, resets locked); MCR04
 * config resets to 0 and is written by firmware (no SPD/strap/probe DRAM sizing);
 * MCR100 reads 0x000000A8. The faithful aspeed.sdmc-ast2050 model resets MCR04=0,
 * stores writes verbatim, and reports the real KGPE-D16 geometry when firmware
 * programs it. The stock DDR3 aspeed_sdmc *synthesises* MCR04 from the machine RAM
 * size and misses the AST2000 shadow, so on it the three DDR2 checks FAIL.
 * Apache-2.0.
 */
#include "harness.h"
#include "ast2050.h"

const char fwtest_name[] = "sdram";

#define SDMC_UNLOCK   0xFC600309u
/*
 * Real KGPE-D16 DDR2 geometry, captured live over JTAG (MCR04 = 0x00000585):
 * 4-bank / 64 MB total / 16-bit bus / BL4 / auto-precharge / 10 column bits.
 * asus-kgpe-d16-firmware/JTAG-USAGE-GUIDE.md (~line 302); DATASHEET-SDRAM.md §2.2.
 */
#define G3_CONF_64M   0x00000585u

void fwtest_run(void)
{
    /* --- reset-state observations --- */
    u32 prot  = fwt_reg("protect",  SDMC_BASE + 0x00);
    u32 conf  = fwt_reg("config",   SDMC_BASE + 0x04);
    u32 refr  = fwt_reg("refresh",  SDMC_BASE + 0x0C);
    fwt_reg("mode2c",  SDMC_BASE + 0x2C);   /* DDR-type / mode-set (X reset)  */
    u32 m100  = fwt_reg("compat100", SDMC_BASE + 0x100);  /* AST2000 shadow   */

    /* --- faithfulness checks (datasheet §17 reset values) --- */
    fwt_check("protect.reset", prot, 0);       /* MCR00 resets locked -> reads 0 */
    fwt_check("config.reset",  conf, 0);       /* MCR04 Init=0; firmware writes it */
    fwt_check("refresh.reset", refr, 0);       /* MCR0C Init=0 (refresh disabled) */
    fwt_check("compat100",     m100, 0x000000A8);

    /* --- behavioural: unlock (0xFC600309 -> MCR00 reads 1) + program config --- */
    writel(SDMC_BASE + 0x00, SDMC_UNLOCK);
    fwt_check("unlock", readl(SDMC_BASE + 0x00), 1);

    /* Firmware writes the real geometry; the controller stores it verbatim. */
    writel(SDMC_BASE + 0x04, G3_CONF_64M);
    u32 rb = readl(SDMC_BASE + 0x04);
    fwt_check("config.rw", rb & 0xFFF, G3_CONF_64M);

    /* Read MCR04 back and confirm it reports the real KGPE-D16 geometry (§17). */
    fwt_check("geom.cap64", (rb >> 2) & 0x3, 0x1);    /* [3:2]=01 -> 64 MB total */
    fwt_check("geom.w16",   (rb >> 8) & 0x3, 0x1);    /* [9:8]=01 -> 16-bit bus  */
    fwt_check("geom.bank4", (rb >> 11) & 0x1, 0x0);   /* [11]=0  -> 4-bank       */
}
