/* VIC (interrupt controller) firmware test — AST2050 @ 0x1E6C0000.
 *
 * The AST2050 VIC is a SINGLE 32-bit bank of 13 registers (0x00..0x38), 32
 * sources, all reset to 0 (datasheet §16 p180-182; source table §10 Table 36 p99;
 * see DATASHEET-VIC.md / DOC.md). This is unlike the AST2400 (G4) two-bank,
 * 64-source VIC that stock QEMU aspeed_vic.c models with hardwired non-zero
 * sense/dual/event registers — so several checks below FAIL against the current
 * model and document the gaps the ast2050-vic model closes.
 *
 * The firmware-programmed trigger words are known from real silicon (culvert
 * session) and reconstructed bit-for-bit from Table 36's per-source attributes.
 * Apache-2.0.
 */
#include "harness.h"
#include "ast2050.h"

const char fwtest_name[] = "vic";

/* Firmware-programmed trigger config (culvert HW capture == datasheet Table 36). */
#define FW_SENSE 0x903897FEu   /* VIC24: 1=level, 0=edge, per source            */
#define FW_DUAL  0x07C00000u   /* VIC28: 1=both-edge (RTC sources 22-26)        */
#define FW_EVENT 0x983F97FEu   /* VIC2C: 1=high/rising                          */

void fwtest_run(void)
{
    /* --- reset-state register file (datasheet §16: every reg resets to 0) --- */
    u32 irqs = fwt_reg("irqstat", VIC_BASE + 0x00);
    u32 fiqs = fwt_reg("fiqstat", VIC_BASE + 0x04);
    u32 raw  = fwt_reg("rawstat", VIC_BASE + 0x08);
    u32 sel  = fwt_reg("select",  VIC_BASE + 0x0C);
    u32 en   = fwt_reg("enable",  VIC_BASE + 0x10);
    u32 soft = fwt_reg("softint", VIC_BASE + 0x18);
    u32 prot = fwt_reg("protect", VIC_BASE + 0x20);
    u32 sense = fwt_reg("sense",  VIC_BASE + 0x24);
    u32 dual  = fwt_reg("dual",   VIC_BASE + 0x28);
    u32 event = fwt_reg("event",  VIC_BASE + 0x2C);

    fwt_check("irqstat.reset", irqs,  0);
    fwt_check("fiqstat.reset", fiqs,  0);
    fwt_check("rawstat.reset", raw,   0);
    fwt_check("select.reset",  sel,   0);
    fwt_check("enable.reset",  en,    0);
    fwt_check("softint.reset", soft,  0);
    fwt_check("protect.reset", prot,  0);
    fwt_check("sense.reset",   sense, 0);   /* G4 hardwires this non-zero */
    fwt_check("dual.reset",    dual,  0);
    fwt_check("event.reset",   event, 0);

    /* --- behavioural: the trigger-config regs must be fully writable (RW) on
     *     G3. Program the real firmware words and read them back. On the G4
     *     model these writes are masked, so the read-back differs. --- */
    writel(VIC_BASE + 0x24, FW_SENSE);
    writel(VIC_BASE + 0x28, FW_DUAL);
    writel(VIC_BASE + 0x2C, FW_EVENT);
    fwt_check("sense.rw",  readl(VIC_BASE + 0x24), FW_SENSE);
    fwt_check("dual.rw",   readl(VIC_BASE + 0x28), FW_DUAL);
    fwt_check("event.rw",  readl(VIC_BASE + 0x2C), FW_EVENT);
}
