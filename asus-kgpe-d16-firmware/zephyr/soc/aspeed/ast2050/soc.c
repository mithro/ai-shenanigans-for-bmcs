/*
 * ASPEED AST2050 (G3) SoC init — ARM926EJ-S.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Minimal Milestone-0 SoC layer: an MMU flat-map for the UART SFR window so
 * the NS16550 console is reachable, plus the vector page. The DRAM/console
 * are already brought up by the JTAG/U-Boot bring-up (silicon) or the QEMU
 * machine, so no clock/DDR init is needed here for M0.
 */

#include <soc.h>
#include <zephyr/arch/arm/mmu/arm_mmu.h>
#include <zephyr/init.h>
#include <zephyr/kernel.h>

static const struct arm_mmu_region mmu_regions[] = {
	MMU_REGION_ENTRY("vectors", CONFIG_KERNEL_VM_BASE, 0, 0x1000,
			 MT_STRONGLY_ORDERED | MPERM_R | MPERM_X),

	/* AST2050 APB peripheral window covering UART2/SCU/timer/VIC. */
	MMU_REGION_FLAT_ENTRY("apb", 0x1e600000, 0x00200000,
			      MT_STRONGLY_ORDERED | MPERM_R | MPERM_W),
};

const struct arm_mmu_config mmu_config = {
	.num_regions = ARRAY_SIZE(mmu_regions),
	.mmu_regions = mmu_regions,
};

void soc_early_init_hook(void)
{
	/* AST2050 SCU/DDR/console are pre-initialised by the loader (U-Boot on
	 * silicon, the machine in QEMU); nothing to do at M0.
	 */
}
