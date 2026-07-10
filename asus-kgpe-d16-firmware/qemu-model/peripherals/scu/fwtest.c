/* SCU (System Control Unit) firmware test — AST2050 @ 0x1E6E2000.
 *
 * Dumps the identity/clock registers and asserts the datasheet+silicon-certain
 * facts. The register DUMP lines are always-valid observations (used to diff
 * QEMU vs real silicon); the CHECK lines encode golden values.
 *
 * Golden facts (see peripherals/scu/DOC.md, DATASHEET-SCU.md):
 *  - SCU7C silicon rev = 0x00000202 for AST2050-A3 (datasheet §18.2 p220; also
 *    read from real silicon over culvert P2A: SCU7C=0x202).
 *
 * HPLL/strap field decodes below use the AST2400 layout; DATASHEET-SCU.md
 * confirms whether the AST2050 shares it. They are emitted as observations
 * (kv), not asserted, until that is pinned. Apache-2.0.
 */
#include "harness.h"
#include "ast2050.h"

const char fwtest_name[] = "scu";

#define AST2050_A3_REVID 0x00000202u

void fwtest_run(void)
{
    /* --- raw register observations (always valid; diffed HW vs QEMU) --- */
    fwt_reg("protect",  SCU_BASE + 0x00);
    fwt_reg("sysreset", SCU_BASE + 0x04);
    u32 clksel = fwt_reg("clksel",  SCU_BASE + 0x08);
    fwt_reg("clkstop",  SCU_BASE + 0x0C);
    u32 mpll   = fwt_reg("mpll",    SCU_BASE + 0x20);
    u32 hpll   = fwt_reg("hpll",    SCU_BASE + 0x24);
    fwt_reg("freqcntr", SCU_BASE + 0x28);
    fwt_reg("scratch1", SCU_BASE + 0x40);
    u32 strap  = fwt_reg("strap",   SCU_BASE + 0x70);
    u32 rev    = fwt_reg("revid",   SCU_BASE + 0x7C);

    /* --- derived observations (AST2400 field layout; see DATASHEET-SCU.md) --- */
    /* H-PLL: multiplier = (2-OD) * ((N+2)/(D+1)); CPU clk = clkin * multiplier. */
    fwt_kv("hpll.N",  (hpll >> 5) & 0x3f);
    fwt_kv("hpll.OD", (hpll >> 4) & 0x1);
    fwt_kv("hpll.D",  (hpll >> 0) & 0xf);
    fwt_kv("mpll.N",  (mpll >> 5) & 0x3f);
    fwt_kv("mpll.OD", (mpll >> 4) & 0x1);
    fwt_kv("mpll.D",  (mpll >> 0) & 0xf);
    fwt_kv("clksel",  clksel);
    fwt_kv("strap",   strap);

    /* --- faithfulness assertions (datasheet + real-silicon golden) --- */
    fwt_check("revid.is_ast2050_a3", rev, AST2050_A3_REVID);
}
