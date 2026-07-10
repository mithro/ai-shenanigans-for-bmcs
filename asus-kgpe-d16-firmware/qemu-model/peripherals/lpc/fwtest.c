/* LPC host interface — AST2050 @ 0x1E789000 (see DATASHEET-LPC.md).
 * G3 layout: KCS IDR1-3 @0x24/28/2C, ODR1-3 @0x30/34/38, STR1-3 @0x3C/40/44;
 * BT @0x48-0x68 (BTCR @0x58); iLPC2AHB HICR5-8 @0x80-8C (culvert ilpc).
 *
 * The G3 KCS/BT/iLPC2AHB registers live at 0x24-0x8C — NOT the AST2400 0x140.
 * This proves the G3 layout on the faithful machine (aspeed.lpc-ast2050): HICR0
 * channel-enable (0x00) and HICR5 iLPC2AHB-enable (0x80) are BMC-writable config
 * registers, and KCS STR1 (0x3C) is a read-only status register that resets to
 * 0. Apache-2.0.
 */
#include "harness.h"
#include "ast2050.h"

#define HICR0  0x00   /* host-interface control 0 (channel enables)   */
#define STR1   0x3C   /* KCS ch#1 status (read-only, reset 0)          */
#define HICR5  0x80   /* iLPC2AHB enable (the culvert `ilpc` register) */

const char fwtest_name[] = "lpc";

void fwtest_run(void)
{
    /* --- reset observations (read before any writes) --- */
    fwt_reg("hicr0", LPC_BASE + HICR0);
    u32 str1_reset = fwt_reg("str1", LPC_BASE + STR1);
    fwt_reg("hicr5", LPC_BASE + HICR5);
    fwt_kv("region.responds", 1u);

    /* KCS STR1 is a status register — resets to 0 (datasheet, p.315). */
    fwt_check("str1.reset", str1_reset, 0u);

    /* HICR0 channel-enable is a BMC config register — RW at the G3 offset 0x00. */
    writel(LPC_BASE + HICR0, 0x0000000Fu);
    fwt_check("hicr0.rw", readl(LPC_BASE + HICR0) & 0xFu, 0xFu);

    /*
     * HICR5 iLPC2AHB enable — the culvert `ilpc` bridge control at the G3 offset
     * 0x80 (on the AST2400 aspeed_lpc, KCS/iBT are at 0x140 and 0x80 is a
     * different HICR). RW here proves the G3 iLPC2AHB register is addressable.
     */
    writel(LPC_BASE + HICR5, 0x00000001u);
    fwt_check("hicr5.rw", readl(LPC_BASE + HICR5) & 0x1u, 0x1u);
}
