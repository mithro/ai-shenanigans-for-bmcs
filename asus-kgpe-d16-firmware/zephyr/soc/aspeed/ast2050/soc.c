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

	/* Whole 64 MB DDR2 window, flat-mapped cacheable-normal, so the kernel
	 * image + stacks are reachable once the MMU turns on. */
	MMU_REGION_FLAT_ENTRY("dram", 0x40000000, 0x04000000,
			      MT_NORMAL | MPERM_R | MPERM_W | MPERM_X),

	/*
	 * Do NOT flat-map the 0x1e600000 APB window here: Zephyr's device-MMIO
	 * virtual allocator (used by the ns16550 DEVICE_MMIO_MAP) hands out
	 * virtual addresses inside that same range, so a flat identity region
	 * collides with it and the UART access lands on the raw virtual==phys
	 * address (0x1e7ff000, unimplemented) instead of translating to the
	 * real UART at 0x1e784000. Each peripheral driver maps its own reg via
	 * DEVICE_MMIO instead.
	 */
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

/* Called from reset.S before prep_c. MMU/caches are still off here. */
void soc_reset_hook(void)
{
}
