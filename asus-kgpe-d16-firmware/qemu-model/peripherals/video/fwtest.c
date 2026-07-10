/* Video engine (KVM capture) — AST2050 @ 0x1E700000 (see DATASHEET-VIDEO.md).
 * VR000 protection key (unlock 0x1A038AA8), VR004 capture trigger/status, VR008 source.
 * Not modelled in mainline QEMU. OpenBMC aspeed-video / KVM path. Apache-2.0. */
#include "harness.h"
#include "ast2050.h"
const char fwtest_name[] = "video";
void fwtest_run(void)
{
    fwt_reg("vr000.protect", VIDEO_BASE + 0x000);
    fwt_reg("vr008.source",  VIDEO_BASE + 0x008);
    writel(VIDEO_BASE + 0x000, 0x1A038AA8u);        /* unlock key */
    fwt_check("vr000.unlock", readl(VIDEO_BASE + 0x000), 0x00000001u); /* unlocked reads 1 */
}
