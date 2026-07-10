/* SMC (Static Memory / SPI flash Controller) firmware test — AST2050.
 *
 * Legacy SMC: control registers @ 0x16000000, flash data mapped at 0x10000000
 * (CE0), 0x12000000 (CE1), 0x14000000 (CE2) (datasheet §11; see DATASHEET-SMC.md).
 * SMC00 reset 0x00000240 (CE0=NOR/CE1=NAND/CE2=SPI, 32 MB segments); SMC04/08/0C
 * per-CE control. Boot CE aliased to 0x0 until the AHBC remap (0x1E60008C). This is
 * NOT the AST2400 FMC (0x1E620000, data 0x20000000) that mainline QEMU's aspeed_smc
 * models — so on this machine the legacy SMC is likely unmodelled. Apache-2.0.
 */
#include "harness.h"
#include "ast2050.h"

#define SMC00 0x00   /* config / CE type + segment */
#define SMC04 0x04   /* CE0 control */

const char fwtest_name[] = "smc";

void fwtest_run(void)
{
    u32 cfg = fwt_reg("smc00.config", SMC_BASE + SMC00);
    fwt_reg("smc04.ce0",  SMC_BASE + SMC04);
    /* flash data window (CE0) — first word of the boot flash image */
    fwt_reg("flash.ce0.word0", 0x10000000u);

    /* datasheet SMC00 reset value */
    fwt_check("smc00.reset", cfg, 0x00000240u);

    /* SMC04 CE0 control should be RW */
    writel(SMC_BASE + SMC04, 0x00000700u);
    fwt_check("smc04.rw", readl(SMC_BASE + SMC04) & 0x00000700u, 0x00000700u);
}
