/* LPC host interface — AST2050 @ 0x1E789000 (see DATASHEET-LPC.md).
 * G3 layout: KCS IDR1-3 @0x24/28/2C, ODR1-3 @0x30/34/38, STR1-3 @0x3C/40/44;
 * BT @0x48-0x68 (BTCR @0x58); iLPC2AHB HICR5-8 @0x80-8C (culvert ilpc).
 *
 * QEMU aspeed_lpc models KCS/iBT at the AST2400 0x140 offsets, NOT the G3 layout —
 * so the G3 KCS/BT are unmodelled here and 0x80 holds an AST2400 HICR (not the G3
 * iLPC2AHB). These are OBSERVATIONS documenting the layout gap; the region responds
 * with AST2400 semantics. Apache-2.0. */
#include "harness.h"
#include "ast2050.h"
const char fwtest_name[] = "lpc";
void fwtest_run(void)
{
    /* G3 KCS status/data registers — expected 0 (aspeed_lpc puts KCS at 0x140). */
    fwt_reg("kcs.str1", LPC_BASE + 0x3C);
    fwt_reg("kcs.idr1", LPC_BASE + 0x24);
    fwt_reg("bt.btcr",  LPC_BASE + 0x58);
    fwt_reg("hicr5",    LPC_BASE + 0x80);
    fwt_kv("region.responds", 1u);   /* the LPC MMIO region exists (aspeed_lpc) */
    /* No golden checks: the G3 KCS/BT/iLPC2AHB layout is not modelled (see DOC.md). */
}
