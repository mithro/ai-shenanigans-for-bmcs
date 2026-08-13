/* smoke test: prove the harness runs on the machine and read SoC identity.
 *
 * Doubles as the first faithfulness probe: SCU7C (silicon revision id). The
 * AST2050 A3 datasheet §18.2 (p220) documents the init/reset value as
 * 0x00000202 ("AST2050-A3 0x00000202"; "2: Represent A2/A3 silicon"), and this
 * matches the value read from real silicon over culvert P2A (SCU7C=0x202). The
 * current QEMU ast2050-a1 SoC returns AST2050_A1_SILICON_REV=0x01000303, an
 * AST2400-class value -> this check is EXPECTED TO FAIL until the SCU model is
 * made faithful (see peripherals/scu/). Apache-2.0.
 */
#include "harness.h"
#include "ast2050.h"

const char fwtest_name[] = "smoke";

#define AST2050_A3_REVID 0x00000202u   /* datasheet §18.2 p220 + HW capture */

void fwtest_run(void)
{
    /* SoC identity + clock config (read-only). */
    fwt_reg("scu.protect", SCU_BASE + SCU_PROTECT);
    fwt_reg("scu.revid",   SCU_BASE + SCU_REVID);
    fwt_reg("scu.strap",   SCU_BASE + SCU_STRAP);
    fwt_reg("scu.clksel",  SCU_BASE + SCU_CLK_SEL);
    fwt_reg("scu.hpll",    SCU_BASE + SCU_HPLL);
    fwt_reg("scu.mpll",    SCU_BASE + SCU_MPLL);

    /* A few block reset values, to confirm the harness reaches each. */
    fwt_reg("vic.irqstat", VIC_BASE + 0x00);
    fwt_reg("vic.rawstat", VIC_BASE + 0x08);
    fwt_reg("sdmc.config", SDMC_BASE + 0x04);

    /* Faithfulness assertion: rev-id must be the real AST2050-A3 value. */
    fwt_check("scu.revid.is_ast2050_a3", readl(SCU_BASE + SCU_REVID),
              AST2050_A3_REVID);
}
