/*
 * AST2050 (G3) SCU (System Control Unit) smoke test — row 35.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Validates that the SoC's SCU block (0x1E6E2000) is present, mapped and
 * readable from Zephyr, and that its identifying register matches the REAL
 * silicon. The SCU page is flat-mapped as device memory in
 * soc/aspeed_g3/ast2050/soc.c ("scu" MMU region), so we read its registers
 * directly at their physical addresses with sys_read32().
 *
 * The keystone check is the silicon-revision register SCU7C. On this AST2050 it
 * reads 0x00000202, INDEPENDENTLY confirmed three ways on the real board:
 *   - culvert over P2A (SCU7C=0x202, LOG culvert-g3-port-status),
 *   - JTAG AHB mdw over OpenOCD (SCU7C=0x202, jtag-bringup-status),
 *   - the faithful QEMU model's P2A back-door (SCU7C=0x0202, ast2050-faithful-qemu).
 * So a Zephyr read that returns 0x0202 on BOTH QEMU and silicon is a true
 * both-sides faithfulness cross-check of the SCU device, not just "a register
 * responded". A wrong value (or a bus error / hang) would mean the SCU mapping
 * or the model is wrong.
 *
 * Read-only: the SCU controls clocks/reset/pinmux and is already driven by the
 * SoC init + the I2C driver (SCU00 unlock, SCU04[2] reset-release, SCU74 mux);
 * this smoke deliberately does not write, so it is safe to run at any point in
 * the boot and on silicon without perturbing a live system.
 */

#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <zephyr/sys/sys_io.h>

#define SCU_BASE        0x1E6E2000U
#define SCU_SYSRST      (SCU_BASE + 0x04U) /* System Reset Control */
#define SCU_HWSTRAP     (SCU_BASE + 0x70U) /* Hardware strapping / boot control */
#define SCU_REV         (SCU_BASE + 0x7CU) /* Silicon Revision ID */

#define AST2050_G3_REV  0x00000202U        /* golden value (P2A + JTAG + QEMU) */

int main(void)
{
	uint32_t rev    = sys_read32(SCU_REV);
	uint32_t strap  = sys_read32(SCU_HWSTRAP);
	uint32_t sysrst = sys_read32(SCU_SYSRST);

	printk("SCU smoke: boot\n");
	printk("SCU7C (silicon rev) = 0x%08x  (expect 0x%08x)\n", rev, AST2050_G3_REV);
	printk("SCU70 (hw strap)    = 0x%08x\n", strap);
	printk("SCU04 (sys rst ctrl)= 0x%08x\n", sysrst);

	if (rev == AST2050_G3_REV) {
		printk("SCU RESULT: PASS\n");
	} else {
		printk("SCU RESULT: FAIL (rev mismatch)\n");
	}
	return 0;
}
