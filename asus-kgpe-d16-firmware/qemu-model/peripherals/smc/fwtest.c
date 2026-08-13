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

#define FLASH_CE0 0x10000000u   /* CE0 flash data window (ast2050_get_baddr) */

typedef unsigned char u8;

/* Byte-granular flash-window I/O (the UMA path is byte-banged: strb/ldrb). */
static inline u8 readb(u32 addr)             { return *(volatile u8 *)addr; }
static inline void writeb(u32 addr, u8 val)  { *(volatile u8 *)addr = val; }

const char fwtest_name[] = "smc";

void fwtest_run(void)
{
    u32 cfg = fwt_reg("smc00.config", SMC_BASE + SMC00);
    u8 j0, j1, j2;

    fwt_reg("smc04.ce0",  SMC_BASE + SMC04);
    /* flash data window (CE0) — first word of the boot flash image */
    fwt_reg("flash.ce0.word0", FLASH_CE0);

    /* datasheet SMC00 reset value */
    fwt_check("smc00.reset", cfg, 0x00000240u);

    /* SMC04 CE0 control should be RW */
    writel(SMC_BASE + SMC04, 0x00000700u);
    fwt_check("smc04.rw", readl(SMC_BASE + SMC04) & 0x00000700u, 0x00000700u);

    /*
     * UMA (user-mode) JEDEC-ID read — the exact sequence the vendor firmware uses
     * (ast2050_smc_cs_low -> byte-bang 0x9F + 3 reads -> cs_high). cs_low writes
     * (mode=user | CE#active) = 0x3 to the CE control reg (CS asserted); each
     * flash-window byte access is one SPI byte; cs_high writes 0x7 (CS deasserted).
     * The on-board flash is a Macronix MX25L12805D (JEDEC 0xC2 0x20 0x18). Only the
     * faithful G3 SMC model responds; an unmodelled window returns 0.
     */
    writel(SMC_BASE + SMC04, 0x00000003u);   /* CE0 user mode + CE# active = CS low */
    writeb(FLASH_CE0, 0x9Fu);                /* RDID command */
    j0 = readb(FLASH_CE0);                    /* manufacturer 0xC2 */
    j1 = readb(FLASH_CE0);                    /* memory type   0x20 */
    j2 = readb(FLASH_CE0);                    /* capacity      0x18 */
    writel(SMC_BASE + SMC04, 0x00000007u);   /* CE# inactive = CS high */
    fwt_check("smc.jedec.mx25l128",
              ((u32)j0 << 16) | ((u32)j1 << 8) | j2, 0x00c22018u);
}
