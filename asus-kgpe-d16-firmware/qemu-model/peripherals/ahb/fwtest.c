/* AHB controller probe — AST2050 @ 0x1E600000 (hwreg.h: prot 0x00, prio 0x80,
 * intr 0x88, addr-remap 0x8C). Observation-level: is the AHBC modelled? Datasheet
 * chapter still to be extracted; values recorded to diff QEMU vs silicon. Apache-2.0. */
#include "harness.h"
#include "ast2050.h"
const char fwtest_name[] = "ahb";
void fwtest_run(void)
{
    fwt_reg("prot",  AHBC_BASE + 0x00);
    fwt_reg("prio",  AHBC_BASE + 0x80);
    fwt_reg("intr",  AHBC_BASE + 0x88);
    fwt_reg("remap", AHBC_BASE + 0x8C);
    writel(AHBC_BASE + 0x80, 0x12345678u);
    fwt_kv("prio.after_wr", readl(AHBC_BASE + 0x80));
}
