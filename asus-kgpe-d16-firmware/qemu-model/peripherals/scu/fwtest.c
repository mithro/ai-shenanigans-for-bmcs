/* SCU (System Control Unit) firmware test — AST2050 @ 0x1E6E2000.
 *
 * Dumps the SCU register file, decodes the clock/strap fields, and asserts the
 * datasheet-golden reset values. The `reg`/`kv` lines are always-valid
 * observations (diffed QEMU vs real silicon); the `check` lines encode golden
 * values from the AST2050 A3 datasheet V1.05 §18 (see DOC.md / DATASHEET-SCU.md)
 * corroborated by Raptor platform.S and the culvert HW capture.
 *
 * Several checks are EXPECTED TO FAIL against the current AST2400-based model
 * (it carries AST2400 reset values); each failure documents a precise
 * faithfulness gap that the ast2050-scu model will close. integration/test_scu.py
 * marks those xfail until then. Apache-2.0.
 */
#include "harness.h"
#include "ast2050.h"

const char fwtest_name[] = "scu";

/* Datasheet §18 reset ("Init =") values for the real AST2050. */
#define G_PROTECT   0x00000000u  /* p205: locked, read-back 0            */
#define G_SYSRESET  0x000FFE5Cu  /* p205                                 */
#define G_CLKSEL    0xE3F00070u  /* p207                                 */
#define G_CLKSTOP   0x000C3E8Bu  /* p209                                 */
#define G_MPLL      0x00004291u  /* p212                                 */
#define G_HPLL      0x00004291u  /* p212                                 */
#define G_RESETFLAG 0x00000001u  /* SCU3C p215: power-on-reset flag      */
#define G_PINMUX1   0x40048000u  /* SCU74 p219                           */
#define G_REVID     0x00000202u  /* SCU7C p220: AST2050-A3               */

static void decode_pll(const char *tag, u32 v)
{
    /* AST2050 layout (DATASHEET-SCU.md §7/§8): N[10:5] OD[4] D[3:0]
     * PostDiv[14:12], H-PLL adds sel[18]. */
    fwt_kv(tag, v);
    fwt_kv("..N",       (v >> 5) & 0x3f);
    fwt_kv("..OD",      (v >> 4) & 0x1);
    fwt_kv("..D",       (v >> 0) & 0xf);
    fwt_kv("..postdiv", (v >> 12) & 0x7);
}

void fwtest_run(void)
{
    /* --- raw register file (observations) --- */
    u32 prot   = fwt_reg("protect",   SCU_BASE + 0x00);
    u32 srst   = fwt_reg("sysreset",  SCU_BASE + 0x04);
    u32 clksel = fwt_reg("clksel",    SCU_BASE + 0x08);
    u32 clkstp = fwt_reg("clkstop",   SCU_BASE + 0x0C);
    u32 mpll   = fwt_reg("mpll",      SCU_BASE + 0x20);
    u32 hpll   = fwt_reg("hpll",      SCU_BASE + 0x24);
    fwt_reg("misc2c",   SCU_BASE + 0x2C);   /* UART div13 at [12] */
    u32 rflags = fwt_reg("resetflag", SCU_BASE + 0x3C);
    fwt_reg("scratch1", SCU_BASE + 0x40);
    u32 pinmux = fwt_reg("pinmux1",   SCU_BASE + 0x74);
    u32 strap  = fwt_reg("strap",     SCU_BASE + 0x70);
    u32 rev    = fwt_reg("revid",     SCU_BASE + 0x7C);

    /* --- decoded fields (observations; G3 strap layout §14) --- */
    decode_pll("hpll.dec", hpll);
    fwt_kv("hpll.sel18", (hpll >> 18) & 0x1);
    decode_pll("mpll.dec", mpll);
    fwt_kv("strap.boot",     (strap >> 0)  & 0x3);   /* 10 = SPI flash    */
    fwt_kv("strap.vga_size", (strap >> 2)  & 0x3);   /* 8/16/32/64 MB     */
    fwt_kv("strap.mac_mode", (strap >> 6)  & 0x7);   /* 100 = RMII MAC1   */
    fwt_kv("strap.hpll_sel", (strap >> 9)  & 0x7);   /* 100 = 133 MHz     */
    fwt_kv("strap.cpu_ahb",  (strap >> 12) & 0x3);   /* 01 = 2:1          */
    fwt_kv("strap.fullspeed",(strap >> 16) & 0x1);
    fwt_kv("pclk.div_sel",   (clksel >> 23) & 0x7);  /* APB = HPLL/2(x+1) */

    /* --- faithfulness assertions (datasheet golden) --- */
    fwt_check("revid",      rev,    G_REVID);       /* fixed: passes      */
    fwt_check("sysreset",   srst,   G_SYSRESET);
    fwt_check("clksel",     clksel, G_CLKSEL);
    fwt_check("clkstop",    clkstp, G_CLKSTOP);
    fwt_check("mpll.reset", mpll,   G_MPLL);
    fwt_check("hpll.reset", hpll,   G_HPLL);
    fwt_check("resetflag",  rflags, G_RESETFLAG);
    fwt_check("pinmux1",    pinmux, G_PINMUX1);
    fwt_check("protect.locked", prot, G_PROTECT);
}
